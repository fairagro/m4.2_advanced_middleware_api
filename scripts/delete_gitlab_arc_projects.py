#!/usr/bin/env python3
r"""Delete ARC-hash GitLab projects from a middleware group.

Lists projects in a GitLab group and deletes those whose repository path is a
64-character SHA256 hex string (the middleware ``arc_id``). Other projects in
the group are skipped unless ``--all-projects`` is passed.

Dry-run is the default. Pass ``--execute`` to perform deletions.

Environment:
    GITLAB_TOKEN: Personal access token with ``api`` scope (used when ``--token``
        is omitted).

Examples:
    # Production (https://datahub.ipk-gatersleben.de/fairagro-advanced-middleware)
    uv run python scripts/delete_gitlab_arc_projects.py \\
        --url https://datahub.ipk-gatersleben.de \\
        --group fairagro-advanced-middleware

    # Fast dry-run: count only (no full target list in memory)
    uv run python scripts/delete_gitlab_arc_projects.py --count-only

    # Development
    uv run python scripts/delete_gitlab_arc_projects.py \\
        --url https://datahub-dev.ipk-gatersleben.de \\
        --group FAIRagro-advanced-middleware-dev

    # Actually delete (stop middleware/Celery first)
    uv run python scripts/delete_gitlab_arc_projects.py --execute --workers 5
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from http import HTTPStatus
from typing import TYPE_CHECKING

import gitlab
from gitlab.exceptions import GitlabDeleteError, GitlabError

if TYPE_CHECKING:
    from gitlab.v4.objects import Group, GroupProject

# Production defaults; see module docstring for dev alternatives.
DEFAULT_GITLAB_URL = "https://datahub.ipk-gatersleben.de"
DEFAULT_GROUP = "fairagro-advanced-middleware"

ARC_PATH_RE = re.compile(r"^[a-f0-9]{64}$")
LOG_FILE = "gitlab-delete.log"
DRY_RUN_PREVIEW_LIMIT = 20
LIST_PROGRESS_INTERVAL = 1000


@dataclass(frozen=True)
class ScanResult:
    """Outcome of scanning group projects."""

    targets: list[tuple[int, str]]
    scanned: int
    skipped_non_arc: int
    matches: int


def _configure_logging() -> logging.Logger:
    log = logging.getLogger("delete_gitlab_arc_projects")
    log.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(formatter)
    log.addHandler(stream_handler)
    log.addHandler(file_handler)
    return log


def _project_matches(project: GroupProject, *, all_projects: bool) -> bool:
    return all_projects or ARC_PATH_RE.fullmatch(project.path) is not None


def _iter_group_projects(
    group: Group,
    log: logging.Logger,
    *,
    include_subgroups: bool,
) -> Iterator[GroupProject]:
    """Iterate group projects using a lighter, keyset-paginated listing."""
    list_kwargs = {
        "iterator": True,
        "get_all": False,
        "include_subgroups": include_subgroups,
        "simple": True,
        "per_page": 100,
    }
    try:
        yield from group.projects.list(
            **list_kwargs,
            pagination="keyset",
            order_by="id",
            sort="asc",
        )
    except GitlabError as exc:
        log.warning("Keyset pagination unavailable (%s); falling back to offset pagination", exc)
        yield from group.projects.list(**list_kwargs)


def _scan_group_projects(
    group: Group,
    log: logging.Logger,
    *,
    all_projects: bool,
    include_subgroups: bool,
    collect_targets: bool,
) -> ScanResult:
    targets: list[tuple[int, str]] = [] if collect_targets else []
    preview: list[tuple[int, str]] = []
    scanned = 0
    skipped_non_arc = 0
    matches = 0
    start = time.monotonic()

    log.info(
        "Listing projects (simple=keyset, include_subgroups=%s)...",
        include_subgroups,
    )

    for project in _iter_group_projects(group, log, include_subgroups=include_subgroups):
        scanned += 1
        if _project_matches(project, all_projects=all_projects):
            matches += 1
            entry = (project.id, project.path_with_namespace)
            if collect_targets:
                targets.append(entry)
            elif len(preview) < DRY_RUN_PREVIEW_LIMIT:
                preview.append(entry)
        else:
            skipped_non_arc += 1

        if scanned % LIST_PROGRESS_INTERVAL == 0:
            elapsed = time.monotonic() - start
            rate = scanned / elapsed if elapsed else 0.0
            log.info(
                "Scanned %d projects (%.0f/s, %d matches, %d skipped)...",
                scanned,
                rate,
                matches,
                skipped_non_arc,
            )

    if not collect_targets:
        targets = preview

    return ScanResult(
        targets=targets,
        scanned=scanned,
        skipped_non_arc=skipped_non_arc,
        matches=matches,
    )


def _candidate_full_paths(attributes: dict[str, object]) -> list[str]:
    """Build ordered, unique full_path candidates for permanently_remove."""
    candidates: list[str] = []

    namespace = attributes.get("namespace")
    project_path = attributes.get("path")
    if isinstance(namespace, dict):
        namespace_full_path = namespace.get("full_path")
        if namespace_full_path and project_path:
            candidates.append(f"{namespace_full_path}/{project_path}")

    explicit = attributes.get("full_path")
    if explicit:
        candidates.append(str(explicit))

    path_with_namespace = attributes.get("path_with_namespace")
    if path_with_namespace:
        candidates.append(str(path_with_namespace))

    unique: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate not in seen:
            seen.add(candidate)
            unique.append(candidate)
    return unique


def _resolve_project_full_path(gl: gitlab.Gitlab, project_id: int) -> list[str]:
    """Return GitLab full_path candidates for permanently_remove."""
    project = gl.projects.get(project_id)
    candidates = _candidate_full_paths(project.attributes)
    if not candidates:
        msg = f"Could not resolve full_path for project {project_id}"
        raise ValueError(msg)
    return candidates


def _permanently_remove_project(
    gl: gitlab.Gitlab,
    project_id: int,
    full_path_candidates: list[str],
    log: logging.Logger,
) -> bool:
    last_error: GitlabError | None = None
    for full_path in full_path_candidates:
        try:
            gl.http_delete(
                f"/projects/{project_id}",
                query_data={
                    "permanently_remove": "true",
                    "full_path": full_path,
                },
            )
            if full_path != full_path_candidates[0]:
                log.info(
                    "Permanent delete succeeded for %s (%s) using alternate full_path",
                    full_path,
                    project_id,
                )
            return True
        except GitlabError as exc:
            if exc.response_code == HTTPStatus.BAD_REQUEST and "full_path" in str(exc):
                last_error = exc
                continue
            raise

    if last_error is not None:
        log.warning(
            "Permanent delete skipped for %s (%s); project is scheduled for deletion: %s",
            full_path_candidates[0],
            project_id,
            last_error,
        )
        return True
    return False


def _delete_project(
    gitlab_url: str,
    token: str,
    project_id: int,
    listed_path: str,
    log: logging.Logger,
) -> bool:
    gl = gitlab.Gitlab(gitlab_url, private_token=token, per_page=100)
    try:
        full_path_candidates = _resolve_project_full_path(gl, project_id)
        primary_path = full_path_candidates[0]
        if primary_path != listed_path:
            log.debug(
                "Resolved full_path candidates %s for project %s (listed as %s)",
                full_path_candidates,
                project_id,
                listed_path,
            )
        gl.http_delete(f"/projects/{project_id}")
        _permanently_remove_project(gl, project_id, full_path_candidates, log)
        return True
    except GitlabDeleteError as exc:
        if exc.response_code == HTTPStatus.NOT_FOUND:
            return True
        log.error("DELETE failed %s (%s): %s", listed_path, project_id, exc)
        return False
    except GitlabError as exc:
        log.error("DELETE failed %s (%s): %s", listed_path, project_id, exc)
        return False
    except ValueError as exc:
        log.error("DELETE failed %s (%s): %s", listed_path, project_id, exc)
        return False


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Delete middleware ARC-hash projects from a GitLab group.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Stop middleware API and Celery workers before running with --execute.\n"
            "Large groups (~30k projects) need several minutes to list; use --count-only\n"
            "for a faster dry-run. See the script docstring for examples."
        ),
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_GITLAB_URL,
        help=f"GitLab base URL (default: {DEFAULT_GITLAB_URL})",
    )
    parser.add_argument(
        "--group",
        default=DEFAULT_GROUP,
        help=f"Group path or ID (default: {DEFAULT_GROUP})",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("GITLAB_TOKEN"),
        help="GitLab personal access token (default: $GITLAB_TOKEN)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=5,
        help="Parallel delete workers when --execute is set (default: 5)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Delete projects (default: dry-run only)",
    )
    parser.add_argument(
        "--count-only",
        action="store_true",
        help="Dry-run: scan and print counts without building the full target list",
    )
    parser.add_argument(
        "--include-subgroups",
        action="store_true",
        help="Include projects from subgroups (slower; default: group only)",
    )
    parser.add_argument(
        "--all-projects",
        action="store_true",
        help="Delete every project in the group, not only ARC-hash paths (dangerous)",
    )
    return parser.parse_args(argv)


def _run_deletes(
    args: argparse.Namespace,
    targets: list[tuple[int, str]],
    log: logging.Logger,
) -> int:
    ok = 0
    failed = 0
    start = time.monotonic()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(
                _delete_project,
                args.url,
                args.token,
                project_id,
                path,
                log,
            ): path
            for project_id, path in targets
        }
        for index, future in enumerate(as_completed(futures), start=1):
            if future.result():
                ok += 1
            else:
                failed += 1
            if index % 100 == 0:
                elapsed = time.monotonic() - start
                rate = index / elapsed if elapsed else 0.0
                log.info(
                    "Progress: %d/%d (%.1f/s, ok=%d, failed=%d)",
                    index,
                    len(targets),
                    rate,
                    ok,
                    failed,
                )

    log.info("Done: ok=%d failed=%d (see %s for errors)", ok, failed, LOG_FILE)
    return 1 if failed else 0


def _report_dry_run(scan: ScanResult, args: argparse.Namespace, log: logging.Logger) -> None:
    match_count = scan.matches
    log.info("Found %d projects to dry-run", match_count)
    for _project_id, path in scan.targets:
        log.info("would delete: %s", path)
    remaining = match_count - len(scan.targets)
    if remaining > 0:
        log.info("... and %d more", remaining)
    if args.count_only:
        log.info("Use without --count-only before --execute to build the full target list")
    else:
        log.info("Re-run with --execute to delete. Log file: %s", LOG_FILE)


def main(argv: list[str] | None = None) -> int:
    """Run project listing and optional bulk deletion."""
    args = _parse_args(argv)
    log = _configure_logging()

    if not args.token:
        log.error("GitLab token required: pass --token or set GITLAB_TOKEN")
        return 1
    if args.workers < 1:
        log.error("--workers must be at least 1")
        return 1
    if args.count_only and args.execute:
        log.error("--count-only cannot be combined with --execute")
        return 1

    gl = gitlab.Gitlab(args.url, private_token=args.token, per_page=100)
    gl.auth()

    group = gl.groups.get(args.group)
    log.info("Group: %s (id=%s)", group.full_path, group.id)

    collect_targets = args.execute or not args.count_only
    scan = _scan_group_projects(
        group,
        log,
        all_projects=args.all_projects,
        include_subgroups=args.include_subgroups,
        collect_targets=collect_targets,
    )

    log.info(
        "Scan complete: %d projects scanned, %d matches, %d skipped (non-ARC)",
        scan.scanned,
        scan.matches,
        scan.skipped_non_arc,
    )

    if not args.execute:
        _report_dry_run(scan, args, log)
        return 0

    return _run_deletes(args, scan.targets, log)


if __name__ == "__main__":
    sys.exit(main())
