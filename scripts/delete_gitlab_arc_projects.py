#!/usr/bin/env python3
r"""Delete ARC-hash GitLab projects from a middleware group.

Lists projects in a GitLab group and deletes those whose repository path is a
64-character SHA256 hex string (the middleware ``arc_id``). Projects already
marked for deletion use the path ``{hash}-deletion_scheduled-{id}`` and are
matched for the purge phase.

Deletion is two-step on GitLab:

1. **Mark** — schedule active projects for deletion (``--mark``).
2. **Purge** — permanently remove marked projects (``--purge``).

Some projects can end up in an inconsistent state: the path still contains
``-deletion_scheduled-{id}`` (often after a restore), but GitLab no longer
lists them as pending deletion. ``--purge`` repairs that automatically by
marking the project again before retrying permanent deletion.

Dry-run is the default (no flags). Pass ``--mark`` and/or ``--purge`` to run phases:

| Flags | Mark | Purge |
|-------|------|-------|
| *(none)* | no | no |
| ``--mark`` | yes | no |
| ``--purge`` | no | yes |
| ``--mark --purge`` | yes | yes |

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

    # Phase 1: mark active ARC projects for deletion
    uv run python scripts/delete_gitlab_arc_projects.py --mark --workers 5

    # Phase 2: permanently remove inactive / pending-deletion projects
    uv run python scripts/delete_gitlab_arc_projects.py --purge --workers 5

    # Both phases in one run (mark all, re-scan, then purge all pending)
    uv run python scripts/delete_gitlab_arc_projects.py --mark --purge --workers 5
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
import time
from collections.abc import Callable, Iterator
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from enum import Enum
from http import HTTPStatus
from typing import TYPE_CHECKING, Any

import gitlab
from gitlab.exceptions import GitlabDeleteError, GitlabError

if TYPE_CHECKING:
    from gitlab.v4.objects import Group, GroupProject

# Production defaults; see module docstring for dev alternatives.
DEFAULT_GITLAB_URL = "https://datahub.ipk-gatersleben.de"
DEFAULT_GROUP = "fairagro-advanced-middleware"

ARC_PATH_RE = re.compile(r"^[a-f0-9]{64}$")
ARC_PENDING_DELETION_RE = re.compile(r"^[a-f0-9]{64}-deletion_scheduled-\d+$")
LOG_FILE = "gitlab-delete.log"
DRY_RUN_PREVIEW_LIMIT = 20
LIST_PROGRESS_INTERVAL = 1000
PURGE_PATH_RESOLVE_RETRIES = 3
PURGE_PATH_RESOLVE_DELAY_S = 0.5


class ArcProjectPhase(Enum):
    """Whether a listed project is active or pending permanent deletion."""

    ACTIVE = "active"
    PENDING_DELETION = "pending_deletion"


@dataclass(frozen=True)
class ProjectJob:
    """Parameters for a mark or purge operation on one GitLab project."""

    gitlab_url: str
    token: str
    project_id: int
    listed_path: str


@dataclass(frozen=True)
class PhaseRunConfig:
    """Parameters for running one mark or purge phase in parallel."""

    workers: int
    targets: list[tuple[int, str]]
    gitlab_url: str
    token: str
    phase_name: str


@dataclass(frozen=True)
class PurgeResult:
    """Outcome of a permanent-delete API attempt."""

    success: bool
    needs_mark_first: bool = False


@dataclass(frozen=True)
class ScanResult:
    """Outcome of scanning group projects."""

    mark_targets: list[tuple[int, str]]
    purge_targets: list[tuple[int, str]]
    scanned: int
    skipped_non_arc: int
    active_matches: int
    pending_matches: int
    zombie_matches: int


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


def _is_marked_for_deletion(project: GroupProject) -> bool:
    """Return whether GitLab considers the project scheduled for deletion."""
    attributes = project.attributes
    if attributes.get("marked_for_deletion_on"):
        return True
    return bool(attributes.get("marked_for_deletion_at"))


def _git_error_needs_mark_first(exc: GitlabError) -> bool:
    return "must be marked for deletion first" in str(exc).lower()


def _classify_arc_project(path: str, *, all_projects: bool) -> ArcProjectPhase | None:
    if all_projects:
        if ARC_PENDING_DELETION_RE.fullmatch(path):
            return ArcProjectPhase.PENDING_DELETION
        return ArcProjectPhase.ACTIVE
    if ARC_PATH_RE.fullmatch(path):
        return ArcProjectPhase.ACTIVE
    if ARC_PENDING_DELETION_RE.fullmatch(path):
        return ArcProjectPhase.PENDING_DELETION
    return None


def _iter_group_projects(
    group: Group,
    log: logging.Logger,
    *,
    include_subgroups: bool,
) -> Iterator[GroupProject]:
    """Iterate group projects using a lighter, keyset-paginated listing."""
    list_kwargs: dict[str, Any] = {
        "get_all": False,
        "include_subgroups": include_subgroups,
        "simple": True,
        "per_page": 100,
        "include_pending_delete": True,
    }
    try:
        yield from group.projects.list(
            iterator=True,
            pagination="keyset",
            order_by="id",
            sort="asc",
            **list_kwargs,
        )
    except GitlabError as exc:
        log.warning("Keyset pagination unavailable (%s); falling back to offset pagination", exc)
        yield from group.projects.list(iterator=True, **list_kwargs)


def _append_scan_target(
    project: GroupProject,
    targets: list[tuple[int, str]],
    preview: list[tuple[int, str]],
    *,
    collect_targets: bool,
) -> None:
    entry = (project.id, project.path_with_namespace)
    if collect_targets:
        targets.append(entry)
    elif len(preview) < DRY_RUN_PREVIEW_LIMIT:
        preview.append(entry)


def _scan_group_projects(
    group: Group,
    log: logging.Logger,
    *,
    all_projects: bool,
    include_subgroups: bool,
    collect_targets: bool,
) -> ScanResult:
    mark_targets: list[tuple[int, str]] = []
    purge_targets: list[tuple[int, str]] = []
    mark_preview: list[tuple[int, str]] = []
    purge_preview: list[tuple[int, str]] = []
    scanned = 0
    skipped_non_arc = 0
    active_matches = 0
    pending_matches = 0
    zombie_matches = 0
    start = time.monotonic()

    log.info(
        "Listing projects (simple=keyset, include_subgroups=%s, include_pending_delete=True)...",
        include_subgroups,
    )

    for project in _iter_group_projects(group, log, include_subgroups=include_subgroups):
        scanned += 1
        phase = _classify_arc_project(project.path, all_projects=all_projects)
        if phase is ArcProjectPhase.ACTIVE:
            active_matches += 1
            _append_scan_target(
                project,
                mark_targets,
                mark_preview,
                collect_targets=collect_targets,
            )
        elif phase is ArcProjectPhase.PENDING_DELETION:
            pending_matches += 1
            if not _is_marked_for_deletion(project):
                zombie_matches += 1
            _append_scan_target(
                project,
                purge_targets,
                purge_preview,
                collect_targets=collect_targets,
            )
        else:
            skipped_non_arc += 1

        if scanned % LIST_PROGRESS_INTERVAL == 0:
            elapsed = time.monotonic() - start
            rate = scanned / elapsed if elapsed else 0.0
            log.info(
                "Scanned %d projects (%.0f/s, %d active, %d pending, %d skipped)...",
                scanned,
                rate,
                active_matches,
                pending_matches,
                skipped_non_arc,
            )

    if not collect_targets:
        mark_targets = mark_preview
        purge_targets = purge_preview

    return ScanResult(
        mark_targets=mark_targets,
        purge_targets=purge_targets,
        scanned=scanned,
        skipped_non_arc=skipped_non_arc,
        active_matches=active_matches,
        pending_matches=pending_matches,
        zombie_matches=zombie_matches,
    )


def _deletion_scheduled_path_candidates(
    attributes: dict[str, object],
    project_id: int,
) -> list[str]:
    """Build ``{hash}-deletion_scheduled-{id}`` paths when GitLab has not renamed yet."""
    project_path = attributes.get("path")
    if not isinstance(project_path, str) or ARC_PENDING_DELETION_RE.fullmatch(project_path):
        return []

    if ARC_PATH_RE.fullmatch(project_path):
        namespace = attributes.get("namespace")
        if isinstance(namespace, dict):
            namespace_full_path = namespace.get("full_path")
            if namespace_full_path:
                return [f"{namespace_full_path}/{project_path}-deletion_scheduled-{project_id}"]
    return []


def _candidate_full_paths(attributes: dict[str, object], project_id: int) -> list[str]:
    """Build ordered, unique full_path candidates for permanently_remove.

    After a project is marked for deletion GitLab renames its path, e.g.
    ``{hash}-deletion_scheduled-{id}``. The permanently_remove call must use
    that post-mark path, not the original listing path.
    """
    candidates: list[str] = []

    path_with_namespace = attributes.get("path_with_namespace")
    if path_with_namespace:
        candidates.append(str(path_with_namespace))

    namespace = attributes.get("namespace")
    project_path = attributes.get("path")
    if isinstance(namespace, dict):
        namespace_full_path = namespace.get("full_path")
        if namespace_full_path and project_path:
            candidates.append(f"{namespace_full_path}/{project_path}")

    explicit = attributes.get("full_path")
    if explicit:
        candidates.append(str(explicit))

    candidates.extend(_deletion_scheduled_path_candidates(attributes, project_id))

    unique: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate not in seen:
            seen.add(candidate)
            unique.append(candidate)
    return unique


def _resolve_project_full_path(
    gl: gitlab.Gitlab,
    project_id: int,
    log: logging.Logger,
) -> list[str]:
    """Return GitLab full_path candidates for permanently_remove."""
    last_candidates: list[str] = []
    for attempt in range(1, PURGE_PATH_RESOLVE_RETRIES + 1):
        project = gl.projects.get(project_id)
        candidates = _candidate_full_paths(project.attributes, project_id)
        if not candidates:
            msg = f"Could not resolve full_path for project {project_id}"
            raise ValueError(msg)

        if any(ARC_PENDING_DELETION_RE.search(candidate) for candidate in candidates):
            return candidates

        last_candidates = candidates
        if attempt < PURGE_PATH_RESOLVE_RETRIES:
            log.debug(
                "Project %s not renamed yet (attempt %d/%d); waiting %.1fs",
                project_id,
                attempt,
                PURGE_PATH_RESOLVE_RETRIES,
                PURGE_PATH_RESOLVE_DELAY_S,
            )
            time.sleep(PURGE_PATH_RESOLVE_DELAY_S)

    return last_candidates


def _permanently_remove_project(
    gl: gitlab.Gitlab,
    project_id: int,
    full_path_candidates: list[str],
    log: logging.Logger,
) -> PurgeResult:
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
            return PurgeResult(success=True)
        except GitlabError as exc:
            if _git_error_needs_mark_first(exc):
                return PurgeResult(success=False, needs_mark_first=True)
            if exc.response_code == HTTPStatus.BAD_REQUEST and "full_path" in str(exc):
                last_error = exc
                continue
            raise

    if last_error is not None:
        log.error(
            "Permanent delete failed for %s (%s): %s",
            full_path_candidates[0],
            project_id,
            last_error,
        )
    return PurgeResult(success=False)


def _schedule_project_for_deletion(
    gl: gitlab.Gitlab,
    project_id: int,
    listed_path: str,
    log: logging.Logger,
) -> bool:
    try:
        gl.http_delete(f"/projects/{project_id}")
        return True
    except GitlabDeleteError as exc:
        if exc.response_code == HTTPStatus.NOT_FOUND:
            return True
        log.error("MARK failed %s (%s): %s", listed_path, project_id, exc)
        return False
    except GitlabError as exc:
        log.error("MARK failed %s (%s): %s", listed_path, project_id, exc)
        return False


def _mark_project(job: ProjectJob, log: logging.Logger) -> bool:
    gl = gitlab.Gitlab(job.gitlab_url, private_token=job.token, per_page=100)
    return _schedule_project_for_deletion(gl, job.project_id, job.listed_path, log)


def _attempt_purge(
    gl: gitlab.Gitlab,
    project_id: int,
    listed_path: str,
    log: logging.Logger,
) -> PurgeResult:
    full_path_candidates = _resolve_project_full_path(gl, project_id, log)
    if full_path_candidates[0] != listed_path:
        log.debug(
            "Resolved full_path candidates %s for project %s (listed as %s)",
            full_path_candidates,
            project_id,
            listed_path,
        )
    return _permanently_remove_project(gl, project_id, full_path_candidates, log)


def _repair_and_purge(
    gl: gitlab.Gitlab,
    job: ProjectJob,
    log: logging.Logger,
) -> bool:
    log.warning(
        "Repairing inconsistent deletion state for %s (%s): "
        "deletion_scheduled path but not marked for deletion",
        job.listed_path,
        job.project_id,
    )
    if not _schedule_project_for_deletion(gl, job.project_id, job.listed_path, log):
        return False
    time.sleep(PURGE_PATH_RESOLVE_DELAY_S)
    repair_result = _attempt_purge(gl, job.project_id, job.listed_path, log)
    if not repair_result.success:
        log.error(
            "PURGE repair failed %s (%s) after re-marking",
            job.listed_path,
            job.project_id,
        )
    return repair_result.success


def _purge_with_gitlab(gl: gitlab.Gitlab, job: ProjectJob, log: logging.Logger) -> bool:
    result = _attempt_purge(gl, job.project_id, job.listed_path, log)
    if result.success:
        return True
    if result.needs_mark_first:
        return _repair_and_purge(gl, job, log)
    return False


def _purge_project(job: ProjectJob, log: logging.Logger) -> bool:
    gl = gitlab.Gitlab(job.gitlab_url, private_token=job.token, per_page=100)
    try:
        return _purge_with_gitlab(gl, job, log)
    except GitlabDeleteError as exc:
        if exc.response_code == HTTPStatus.NOT_FOUND:
            return True
        log.error("PURGE failed %s (%s): %s", job.listed_path, job.project_id, exc)
        return False
    except GitlabError as exc:
        log.error("PURGE failed %s (%s): %s", job.listed_path, job.project_id, exc)
        return False
    except ValueError as exc:
        log.error("PURGE failed %s (%s): %s", job.listed_path, job.project_id, exc)
        return False


def _resolve_execution_phases(args: argparse.Namespace) -> tuple[bool, bool]:
    """Return (do_mark, do_purge) from CLI flags."""
    return args.mark, args.purge


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Delete middleware ARC-hash projects from a GitLab group.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Stop middleware API and Celery workers before running with --mark or --purge.\n"
            "Phase 1 (mark):  --mark\n"
            "Phase 2 (purge): --purge\n"
            "Both phases:     --mark --purge\n"
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
        help="Parallel workers when --mark or --purge is set (default: 5)",
    )
    parser.add_argument(
        "--mark",
        action="store_true",
        help="Mark active ARC projects for deletion (phase 1)",
    )
    parser.add_argument(
        "--purge",
        action="store_true",
        help="Permanently remove projects already marked for deletion (phase 2)",
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


def _run_parallel_jobs(
    config: PhaseRunConfig,
    worker_fn: Callable[[ProjectJob, logging.Logger], bool],
    log: logging.Logger,
) -> int:
    if not config.targets:
        log.info("Phase %s: no targets", config.phase_name)
        return 0

    log.info(
        "Phase %s: processing %d projects with %d workers",
        config.phase_name,
        len(config.targets),
        config.workers,
    )
    ok = 0
    failed = 0
    start = time.monotonic()
    with ThreadPoolExecutor(max_workers=config.workers) as pool:
        futures: dict[Future[bool], str] = {
            pool.submit(
                worker_fn,
                ProjectJob(
                    gitlab_url=config.gitlab_url,
                    token=config.token,
                    project_id=project_id,
                    listed_path=path,
                ),
                log,
            ): path
            for project_id, path in config.targets
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
                    "Phase %s progress: %d/%d (%.1f/s, ok=%d, failed=%d)",
                    config.phase_name,
                    index,
                    len(config.targets),
                    rate,
                    ok,
                    failed,
                )

    log.info("Phase %s done: ok=%d failed=%d", config.phase_name, ok, failed)
    return 1 if failed else 0


@dataclass(frozen=True)
class PhaseExecution:
    """Which deletion phases to run and their shared scan context."""

    args: argparse.Namespace
    group: Group
    scan: ScanResult
    do_mark: bool
    do_purge: bool


def _run_phases(execution: PhaseExecution, log: logging.Logger) -> int:
    exit_code = 0
    args = execution.args

    if execution.do_mark:
        exit_code = max(
            exit_code,
            _run_parallel_jobs(
                PhaseRunConfig(
                    workers=args.workers,
                    targets=execution.scan.mark_targets,
                    gitlab_url=args.url,
                    token=args.token,
                    phase_name="mark",
                ),
                _mark_project,
                log,
            ),
        )

    purge_scan = execution.scan
    if execution.do_mark and execution.do_purge:
        log.info("Re-scanning group before purge phase...")
        purge_scan = _scan_group_projects(
            execution.group,
            log,
            all_projects=args.all_projects,
            include_subgroups=args.include_subgroups,
            collect_targets=True,
        )
        log.info(
            "Re-scan complete: %d active, %d pending, %d inconsistent",
            purge_scan.active_matches,
            purge_scan.pending_matches,
            purge_scan.zombie_matches,
        )

    if execution.do_purge:
        exit_code = max(
            exit_code,
            _run_parallel_jobs(
                PhaseRunConfig(
                    workers=args.workers,
                    targets=purge_scan.purge_targets,
                    gitlab_url=args.url,
                    token=args.token,
                    phase_name="purge",
                ),
                _purge_project,
                log,
            ),
        )

    log.info("All phases complete (see %s for errors)", LOG_FILE)
    return exit_code


def _report_dry_run(scan: ScanResult, args: argparse.Namespace, log: logging.Logger) -> None:
    log.info("Active ARC projects (phase mark: --mark): %d", scan.active_matches)
    for _project_id, path in scan.mark_targets:
        log.info("would mark: %s", path)
    remaining_mark = scan.active_matches - len(scan.mark_targets)
    if remaining_mark > 0:
        log.info("... and %d more active projects", remaining_mark)

    log.info("Pending deletion (phase purge: --purge): %d", scan.pending_matches)
    if scan.zombie_matches:
        log.info(
            "Inconsistent deletion_scheduled paths (repair during --purge): %d",
            scan.zombie_matches,
        )
    for _project_id, path in scan.purge_targets:
        log.info("would purge: %s", path)
    remaining_purge = scan.pending_matches - len(scan.purge_targets)
    if remaining_purge > 0:
        log.info("... and %d more pending projects", remaining_purge)

    if args.count_only:
        log.info("Use without --count-only before --mark/--purge to build the full target list")
    else:
        log.info("Re-run with --mark, --purge, or both. Log file: %s", LOG_FILE)


def _validate_args(args: argparse.Namespace, log: logging.Logger) -> int | None:
    """Return an exit code when arguments are invalid, else None."""
    if not args.token:
        log.error("GitLab token required: pass --token or set GITLAB_TOKEN")
        return 1
    if args.workers < 1:
        log.error("--workers must be at least 1")
        return 1
    if args.count_only and (args.mark or args.purge):
        log.error("--count-only cannot be combined with --mark or --purge")
        return 1
    return None


def main(argv: list[str] | None = None) -> int:
    """Run project listing and optional bulk deletion."""
    args = _parse_args(argv)
    log = _configure_logging()
    do_mark, do_purge = _resolve_execution_phases(args)

    validation_error = _validate_args(args, log)
    if validation_error is not None:
        return validation_error

    gl = gitlab.Gitlab(args.url, private_token=args.token, per_page=100)
    gl.auth()

    group = gl.groups.get(args.group)
    log.info("Group: %s (id=%s)", group.full_path, group.id)

    collect_targets = args.mark or args.purge or not args.count_only
    scan = _scan_group_projects(
        group,
        log,
        all_projects=args.all_projects,
        include_subgroups=args.include_subgroups,
        collect_targets=collect_targets,
    )

    log.info(
        "Scan complete: %d projects scanned, %d active ARC, %d pending deletion, "
        "%d inconsistent, %d skipped",
        scan.scanned,
        scan.active_matches,
        scan.pending_matches,
        scan.zombie_matches,
        scan.skipped_non_arc,
    )

    if not do_mark and not do_purge:
        _report_dry_run(scan, args, log)
        return 0

    return _run_phases(
        PhaseExecution(args=args, group=group, scan=scan, do_mark=do_mark, do_purge=do_purge),
        log,
    )


if __name__ == "__main__":
    sys.exit(main())
