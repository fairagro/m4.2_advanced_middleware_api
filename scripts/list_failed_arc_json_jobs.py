#!/usr/bin/env python3
r"""List group projects with failed CI jobs and summarize error causes.

Scans projects in a GitLab group, finds recent **failed** CI jobs via the
project jobs API (``scope=failed``), extracts a root-cause message from each
job log, and prints:

* how often each **classified** cause occurs (with project list)
* a **remainder** bucket for failures that could not be classified, with a
  short concrete excerpt per project (not the full log)

ARC pipelines use stage ``arc_json``; the job *name* is typically
``ARC RO-Crate`` (not ``arc_json``). Default filter is ``--stage arc_json``.

By default only middleware ARC-hash projects are considered (64-character
SHA256 path). Use ``--all-projects`` to include every project in the group.

``--project`` resolves a single project via the projects API and does **not**
list the whole group (fast path for debugging).

Environment:
    GITLAB_TOKEN: Personal access token with ``api`` / ``read_api`` scope
        (used when ``--token`` is omitted).

Examples:
    # Fast group scan: only projects active in the last 90 days, more workers
    uv run python scripts/list_failed_arc_json_jobs.py --active-since-days 90 --workers 20

    # Reuse cached project list from a previous run (skips the slow group listing)
    uv run python scripts/list_failed_arc_json_jobs.py --project-cache \\
        gitlab-failed-arc-json-projects.cache.json

    # Reports are written to markdown/JSON files (stdout stays short)
    # default: gitlab-failed-arc-json-report.md / .json
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import threading
import time
from collections import defaultdict
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

import gitlab
from gitlab.exceptions import GitlabError

if TYPE_CHECKING:
    from gitlab.v4.objects import Group, GroupProject, Project

DEFAULT_GITLAB_URL = "https://datahub.ipk-gatersleben.de"
DEFAULT_GROUP = "fairagro-advanced-middleware"
DEFAULT_STAGE = "arc_json"
DEFAULT_FAILED_JOB_LIMIT = 50
DEFAULT_WORKERS = 20
JOB_LIST_PAGE_SIZE = 100
DEFAULT_PROJECT_CACHE = "gitlab-failed-arc-json-projects.cache.json"
DEFAULT_REPORT_FILE = "gitlab-failed-arc-json-report.md"
DEFAULT_REPORT_JSON = "gitlab-failed-arc-json-report.json"
CACHE_PROJECT_ENTRY_LEN = 2

LOG_FILE = "gitlab-failed-arc-json.log"
LIST_PROGRESS_INTERVAL = 1000
CHECK_PROGRESS_INTERVAL = 100

_THREAD_LOCAL = threading.local()

ARC_PATH_RE = re.compile(r"^[a-f0-9]{64}$")
ARC_PENDING_DELETION_RE = re.compile(r"^[a-f0-9]{64}-deletion_scheduled-\d+$")
INTERNAL_ERROR_MAX_FOLLOW_LINES = 3
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
INTERNAL_ERROR_HEADER_RE = re.compile(r"^Internal Error:\s*$", re.IGNORECASE)
NOISE_LINE_RE = re.compile(
    r"(?i)^(?:"
    r"section_(?:start|end):|"
    r"Running with gitlab-runner|"
    r"Preparing |Using |Pulling |Getting source|"
    r"Fetching changes|Initialized empty|Created fresh|"
    r"Checking out |Skipping Git|Gitaly correlation|"
    r"Executing |Uploading artifacts|"
    r"WARNING: |"
    r"Cleaning up |"
    r"ERROR: No files to upload|"
    r"ERROR: Job failed|"
    r"Job succeeded|"
    r"Start arc-export|"
    r"Loading ARC from|"
    r"It is writing here|"
    r"Writing ARC RO-Crate metadata to|"
    r"\$ |"
    r"curl:"
    r")"
)
SECONDARY_FAILURE_RE = re.compile(
    r"(?i)^(?:"
    r"curl:|"
    r"WARNING: .*no matching files|"
    r"ERROR: No files to upload|"
    r"ERROR: Job failed"
    r")"
)
CAUSE_HINT_RE = re.compile(
    r"(?i)(?:\berror\b|\bexception\b|\bfatal\b|\bfailed\b|\bmust have\b|"
    r"\binvalid\b|\bmissing\b|\bnot found\b|\bunable to\b|\bcannot\b)"
)
UNKNOWN_CAUSE = "(no usable log lines)"
REMAINDER_BUCKET_LABEL = "(remainder — not classified)"
EXCERPT_MAX_LINES = 3
EXCERPT_MAX_CHARS = 240


@dataclass(frozen=True)
class ExtractedCause:
    """Parsed failure message and whether it is a classified cause."""

    cause: str
    classified: bool
    excerpt: str


@dataclass(frozen=True)
class FailedJobMatch:
    """One project with a failed CI job matching the filter."""

    project_id: int
    path_with_namespace: str
    pipeline_id: int | None
    pipeline_web_url: str | None
    job_id: int
    job_name: str
    job_web_url: str | None
    finished_at: str | None
    stage: str | None
    trace: str | None
    cause: str
    classified: bool
    excerpt: str


@dataclass(frozen=True)
class ProjectCheckJob:
    """Parameters for inspecting one GitLab project."""

    gitlab_url: str
    token: str
    project_id: int
    path_with_namespace: str
    stage: str | None
    job_name: str | None
    job_name_contains: str | None
    failed_job_limit: int
    keep_trace: bool


def _thread_gitlab(url: str, token: str) -> gitlab.Gitlab:
    """Reuse one Gitlab client per worker thread (keeps HTTP connections warm)."""
    cached_url = getattr(_THREAD_LOCAL, "url", None)
    cached_token = getattr(_THREAD_LOCAL, "token", None)
    client: gitlab.Gitlab | None = getattr(_THREAD_LOCAL, "client", None)
    if client is None or cached_url != url or cached_token != token:
        client = gitlab.Gitlab(url, private_token=token, per_page=100)
        _THREAD_LOCAL.client = client
        _THREAD_LOCAL.url = url
        _THREAD_LOCAL.token = token
    return client


def _configure_logging() -> logging.Logger:
    log = logging.getLogger("list_failed_arc_json_jobs")
    log.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(formatter)
    log.addHandler(stream_handler)
    log.addHandler(file_handler)
    return log


def _is_arc_project_path(path: str) -> bool:
    return bool(ARC_PATH_RE.fullmatch(path) or ARC_PENDING_DELETION_RE.fullmatch(path))


def _job_matches(
    job: Any,
    *,
    stage: str | None,
    job_name: str | None,
    job_name_contains: str | None,
) -> bool:
    if stage is not None and getattr(job, "stage", None) != stage:
        return False
    name = job.name
    if job_name is not None and name != job_name:
        return False
    return job_name_contains is None or job_name_contains in name


@dataclass(frozen=True)
class CollectConfig:
    """Options for selecting which group projects to inspect."""

    all_projects: bool
    include_subgroups: bool
    max_projects: int | None
    active_since: datetime | None


def _parse_last_activity(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def _resolve_single_project(
    gl: gitlab.Gitlab,
    group: Group,
    project_ref: str,
    log: logging.Logger,
) -> list[tuple[int, str]]:
    """Resolve ``--project`` via the projects API (no full group listing)."""
    candidates: list[str | int] = []
    if project_ref.isdigit():
        candidates.append(int(project_ref))
    candidates.append(project_ref)
    if "/" not in project_ref:
        candidates.append(f"{group.full_path}/{project_ref}")

    seen: set[str | int] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        try:
            project = gl.projects.get(candidate, lazy=False)
        except GitlabError:
            continue
        log.info(
            "Resolved --project %r -> %s (id=%s) without listing the group",
            project_ref,
            project.path_with_namespace,
            project.id,
        )
        return [(project.id, project.path_with_namespace)]

    log.error(
        "Could not resolve --project %r (tried id/path and %s/<path>)",
        project_ref,
        group.full_path,
    )
    return []


def _iter_group_projects(
    group: Group,
    log: logging.Logger,
    *,
    include_subgroups: bool,
    order_by_activity: bool,
) -> Any:
    """Iterate group projects using a lighter listing."""
    list_kwargs: dict[str, Any] = {
        "get_all": False,
        "include_subgroups": include_subgroups,
        "simple": True,
        "per_page": 100,
        "include_pending_delete": True,
    }
    if order_by_activity:
        # Offset pagination: allows early-stop once activity falls below --active-since-days.
        yield from group.projects.list(
            iterator=True,
            order_by="last_activity_at",
            sort="desc",
            **list_kwargs,
        )
        return

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


def _collect_projects(
    group: Group,
    log: logging.Logger,
    config: CollectConfig,
) -> list[tuple[int, str]]:
    """Return ``(project_id, path_with_namespace)`` entries to inspect."""
    targets: list[tuple[int, str]] = []
    scanned = 0
    skipped = 0
    skipped_inactive = 0
    start = time.monotonic()
    order_by_activity = config.active_since is not None
    log.info(
        "Listing projects (simple, include_subgroups=%s, order_by_activity=%s)...",
        config.include_subgroups,
        order_by_activity,
    )
    for project in _iter_group_projects(
        group,
        log,
        include_subgroups=config.include_subgroups,
        order_by_activity=order_by_activity,
    ):
        scanned += 1
        group_project: GroupProject = project
        path = group_project.path
        path_with_namespace = group_project.path_with_namespace
        activity = _parse_last_activity(group_project.attributes.get("last_activity_at"))

        if config.active_since is not None and activity is not None and activity < config.active_since:
            skipped_inactive += 1
            # Newest-first listing: once we hit older activity, remaining rows are older.
            if order_by_activity:
                log.info(
                    "Stopping listing early: last_activity_at %s is older than cutoff %s",
                    activity.isoformat(),
                    config.active_since.isoformat(),
                )
                break
            skipped += 1
            continue

        if not config.all_projects and not _is_arc_project_path(path):
            skipped += 1
            continue

        targets.append((group_project.id, path_with_namespace))
        if config.max_projects is not None and len(targets) >= config.max_projects:
            log.info("Reached --max-projects=%d; stopping project listing", config.max_projects)
            break

        if scanned % LIST_PROGRESS_INTERVAL == 0:
            elapsed = time.monotonic() - start
            rate = scanned / elapsed if elapsed else 0.0
            log.info(
                "Scanned %d projects (%.0f/s, %d selected, %d skipped, %d inactive)...",
                scanned,
                rate,
                len(targets),
                skipped,
                skipped_inactive,
            )

    log.info(
        "Listing complete: scanned=%d selected=%d skipped=%d inactive=%d",
        scanned,
        len(targets),
        skipped,
        skipped_inactive,
    )
    return targets


def _load_project_cache(path: Path, group_full_path: str, log: logging.Logger) -> list[tuple[int, str]] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("Ignoring unreadable project cache %s (%s)", path, exc)
        return None
    if payload.get("group") != group_full_path:
        log.warning(
            "Ignoring project cache %s (group mismatch: cache=%r current=%r)",
            path,
            payload.get("group"),
            group_full_path,
        )
        return None
    projects = payload.get("projects")
    if not isinstance(projects, list):
        log.warning("Ignoring project cache %s (invalid projects payload)", path)
        return None
    targets: list[tuple[int, str]] = []
    for entry in projects:
        if (
            isinstance(entry, list)
            and len(entry) == CACHE_PROJECT_ENTRY_LEN
            and isinstance(entry[0], int)
            and isinstance(entry[1], str)
        ):
            targets.append((entry[0], entry[1]))
    log.info(
        "Loaded %d projects from cache %s (generated_at=%s)",
        len(targets),
        path,
        payload.get("generated_at"),
    )
    return targets


def _save_project_cache(
    path: Path,
    group_full_path: str,
    targets: list[tuple[int, str]],
    log: logging.Logger,
) -> None:
    payload = {
        "group": group_full_path,
        "generated_at": datetime.now(UTC).isoformat(),
        "projects": [[project_id, project_path] for project_id, project_path in targets],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    log.info("Wrote project cache %s (%d projects)", path, len(targets))


def _decode_trace(raw: bytes | str) -> str:
    if isinstance(raw, bytes):
        return raw.decode("utf-8", errors="replace")
    return raw


def _clean_log_line(line: str) -> str:
    line = ANSI_ESCAPE_RE.sub("", line)
    return line.replace("\r", "").strip()


def _truncate_excerpt(text: str, *, max_chars: int = EXCERPT_MAX_CHARS) -> str:
    text = " ".join(text.split())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def _build_short_excerpt(lines: list[str]) -> str:
    """Build a short concrete snippet from the last non-noise log lines."""
    useful: list[str] = []
    for line in reversed(lines):
        if NOISE_LINE_RE.match(line) or SECONDARY_FAILURE_RE.match(line):
            continue
        useful.append(line)
        if len(useful) >= EXCERPT_MAX_LINES:
            break
    if not useful:
        return UNKNOWN_CAUSE
    useful.reverse()
    return _truncate_excerpt(" | ".join(useful))


def _extract_after_internal_error(lines: list[str]) -> str | None:
    """Prefer the message immediately following an ``Internal Error:`` header."""
    for index, line in enumerate(lines):
        if not INTERNAL_ERROR_HEADER_RE.fullmatch(line):
            continue
        collected: list[str] = []
        for follower in lines[index + 1 :]:
            if not follower or follower.startswith("$") or NOISE_LINE_RE.match(follower):
                break
            if SECONDARY_FAILURE_RE.match(follower):
                break
            collected.append(follower)
            if len(collected) >= INTERNAL_ERROR_MAX_FOLLOW_LINES:
                break
        if collected:
            return " | ".join(collected)
    return None


def _extract_error_cause(trace: str | None) -> ExtractedCause:
    """Heuristically pick a classified cause or a remainder excerpt."""
    if not trace:
        return ExtractedCause(
            cause=REMAINDER_BUCKET_LABEL,
            classified=False,
            excerpt=UNKNOWN_CAUSE,
        )

    lines = [_clean_log_line(line) for line in trace.splitlines()]
    lines = [line for line in lines if line]

    internal = _extract_after_internal_error(lines)
    if internal:
        message = _truncate_excerpt(internal)
        return ExtractedCause(cause=message, classified=True, excerpt=message)

    # Prefer substantive error-like lines; skip runner / curl / artifact noise.
    candidates: list[str] = []
    for line in lines:
        if NOISE_LINE_RE.match(line) or SECONDARY_FAILURE_RE.match(line):
            continue
        if CAUSE_HINT_RE.search(line):
            candidates.append(line)

    if candidates:
        message = _truncate_excerpt(candidates[-1])
        return ExtractedCause(cause=message, classified=True, excerpt=message)

    # Remainder: keep a short concrete snippet so the failure stays visible.
    excerpt = _build_short_excerpt(lines)
    return ExtractedCause(
        cause=REMAINDER_BUCKET_LABEL,
        classified=False,
        excerpt=excerpt,
    )


@dataclass(frozen=True)
class JobMatchFilter:
    """Which failed jobs count as a match."""

    stage: str | None
    job_name: str | None
    job_name_contains: str | None
    failed_job_limit: int
    keep_trace: bool
    project_id: int
    path_with_namespace: str


def _job_trace(project: Project, job: Any) -> str:
    """Fetch a job trace with as few API round-trips as possible."""
    try:
        return _decode_trace(job.trace())
    except (GitlabError, AttributeError, TypeError):
        return _decode_trace(project.jobs.get(job.id, lazy=True).trace())


def _pipeline_fields(job: Any) -> tuple[int | None, str | None]:
    pipeline_id = getattr(job, "pipeline", None)
    if isinstance(pipeline_id, dict):
        raw_id = pipeline_id.get("id")
        pipeline_id_value = int(raw_id) if raw_id is not None else None
        return pipeline_id_value, pipeline_id.get("web_url")
    if pipeline_id is None:
        return None, None
    return int(pipeline_id), None


def _find_failed_job(project: Project, filters: JobMatchFilter) -> FailedJobMatch | None:
    """Return the newest failed job matching stage/name filters.

    Scans newest-first through failed jobs (paginated). Newer failures in other
    stages do not hide an older matching ``arc_json`` failure within the scan
    budget (``failed_job_limit``).
    """
    failed_jobs = project.jobs.list(
        iterator=True,
        per_page=min(JOB_LIST_PAGE_SIZE, filters.failed_job_limit),
        scope=["failed"],
        order_by="id",
        sort="desc",
    )
    inspected = 0
    for job in failed_jobs:
        inspected += 1
        if inspected > filters.failed_job_limit:
            break
        if not _job_matches(
            job,
            stage=filters.stage,
            job_name=filters.job_name,
            job_name_contains=filters.job_name_contains,
        ):
            continue
        trace = _job_trace(project, job)
        extracted = _extract_error_cause(trace)
        pipeline_id_value, pipeline_url = _pipeline_fields(job)
        return FailedJobMatch(
            project_id=filters.project_id,
            path_with_namespace=filters.path_with_namespace,
            pipeline_id=pipeline_id_value,
            pipeline_web_url=pipeline_url,
            job_id=int(job.id),
            job_name=job.name,
            job_web_url=getattr(job, "web_url", None),
            finished_at=getattr(job, "finished_at", None),
            stage=getattr(job, "stage", None),
            trace=trace if filters.keep_trace else None,
            cause=extracted.cause,
            classified=extracted.classified,
            excerpt=extracted.excerpt,
        )
    return None


def _check_project(job: ProjectCheckJob, log: logging.Logger) -> FailedJobMatch | None:
    """Inspect one project; return a match or None. Errors are logged and skipped."""
    try:
        gl = _thread_gitlab(job.gitlab_url, job.token)
        # lazy=True avoids an extra GET /projects/:id before listing jobs.
        project = gl.projects.get(job.project_id, lazy=True)
        return _find_failed_job(
            project,
            JobMatchFilter(
                stage=job.stage,
                job_name=job.job_name,
                job_name_contains=job.job_name_contains,
                failed_job_limit=job.failed_job_limit,
                keep_trace=job.keep_trace,
                project_id=job.project_id,
                path_with_namespace=job.path_with_namespace,
            ),
        )
    except GitlabError as exc:
        log.error("Project %s (id=%s): %s", job.path_with_namespace, job.project_id, exc)
        return None


def _print_match(match: FailedJobMatch, log: logging.Logger, *, show_logs: bool) -> None:
    separator = "=" * 72
    log.info(separator)
    log.info("FAILED %s", match.path_with_namespace)
    log.info("  project_id=%s", match.project_id)
    log.info("  pipeline_id=%s", match.pipeline_id)
    if match.pipeline_web_url:
        log.info("  pipeline_url=%s", match.pipeline_web_url)
    log.info(
        "  job_id=%s name=%r stage=%s finished_at=%s",
        match.job_id,
        match.job_name,
        match.stage,
        match.finished_at,
    )
    if match.job_web_url:
        log.info("  job_url=%s", match.job_web_url)
    log.info("  cause=%s", match.cause)
    if not match.classified:
        log.info("  excerpt=%s", match.excerpt)
    if show_logs and match.trace is not None:
        log.info("  ----- job log begin -----")
        for line in match.trace.splitlines():
            log.info("  | %s", line)
        log.info("  ----- job log end -----")
    log.info(separator)


def _share(count: int, total: int) -> str:
    if total == 0:
        return "0.0%"
    return f"{(100.0 * count / total):.1f}%"


def _match_to_json(item: FailedJobMatch, *, include_excerpt: bool = False) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "project_id": item.project_id,
        "path_with_namespace": item.path_with_namespace,
        "job_id": item.job_id,
        "job_url": item.job_web_url,
        "pipeline_id": item.pipeline_id,
        "finished_at": item.finished_at,
    }
    if include_excerpt:
        payload["excerpt"] = item.excerpt
    return payload


def _build_ranked_causes(
    matches: list[FailedJobMatch],
) -> tuple[list[tuple[str, list[FailedJobMatch]]], list[FailedJobMatch]]:
    classified = [match for match in matches if match.classified]
    remainder = [match for match in matches if not match.classified]
    by_cause: dict[str, list[FailedJobMatch]] = defaultdict(list)
    for match in classified:
        by_cause[match.cause].append(match)
    ranked = sorted(by_cause.items(), key=lambda item: (-len(item[1]), item[0].lower()))
    return ranked, remainder


def _render_markdown_report(
    *,
    generated_at: str,
    total: int,
    ranked: list[tuple[str, list[FailedJobMatch]]],
    remainder: list[FailedJobMatch],
) -> str:
    lines: list[str] = [
        "# Failed `arc_json` job report",
        "",
        f"Generated: `{generated_at}`",
        "",
        f"- Failed projects: **{total}**",
        f"- Classified causes: **{len(ranked)}**",
        f"- Remainder (unclassified): **{len(remainder)}**",
        "",
        "## Summary",
        "",
        "| # | Count | Share | Cause |",
        "| --: | --: | --: | --- |",
    ]
    for rank, (cause, group) in enumerate(ranked, start=1):
        safe_cause = cause.replace("|", "\\|")
        lines.append(f"| {rank} | {len(group)} | {_share(len(group), total)} | `{safe_cause}` |")
    lines.append(f"| remainder | {len(remainder)} | {_share(len(remainder), total)} | `{REMAINDER_BUCKET_LABEL}` |")
    lines.extend(["", "## Cause details", ""])

    for rank, (cause, group) in enumerate(ranked, start=1):
        project_rows = sorted(group, key=lambda item: item.path_with_namespace)
        lines.extend([
            f"### {rank}. `{cause}`",
            "",
            f"Count: **{len(project_rows)}** ({_share(len(project_rows), total)})",
            "",
            "| Project | Job |",
            "| --- | --- |",
        ])
        for item in project_rows:
            lines.append(f"| `{item.path_with_namespace}` | {item.job_web_url or ''} |")
        lines.append("")

    lines.extend([
        f"### remainder. `{REMAINDER_BUCKET_LABEL}`",
        "",
        f"Count: **{len(remainder)}** ({_share(len(remainder), total)})",
        "",
    ])
    if not remainder:
        lines.extend(["_No unclassified failures._", ""])
    else:
        lines.extend(["| Project | Excerpt | Job |", "| --- | --- | --- |"])
        for item in sorted(remainder, key=lambda match: match.path_with_namespace):
            excerpt = item.excerpt.replace("|", "\\|")
            lines.append(f"| `{item.path_with_namespace}` | {excerpt} | {item.job_web_url or ''} |")
        lines.append("")
    return "\n".join(lines) + "\n"


def _build_json_report(
    *,
    generated_at: str,
    total: int,
    ranked: list[tuple[str, list[FailedJobMatch]]],
    remainder: list[FailedJobMatch],
) -> dict[str, Any]:
    causes = [
        {
            "rank": rank,
            "cause": cause,
            "count": len(group),
            "projects": [_match_to_json(item) for item in sorted(group, key=lambda row: row.path_with_namespace)],
        }
        for rank, (cause, group) in enumerate(ranked, start=1)
    ]
    return {
        "generated_at": generated_at,
        "total_failed_projects": total,
        "classified_cause_count": len(ranked),
        "remainder_count": len(remainder),
        "causes": causes,
        "remainder": [
            _match_to_json(item, include_excerpt=True)
            for item in sorted(remainder, key=lambda row: row.path_with_namespace)
        ],
    }


def _report_cause_statistics(
    matches: list[FailedJobMatch],
    *,
    report_md: Path,
    report_json: Path,
    log: logging.Logger,
) -> None:
    """Write a readable markdown + JSON report; log only a short stdout summary."""
    ranked, remainder = _build_ranked_causes(matches)
    total = len(matches)
    generated_at = datetime.now(UTC).isoformat()

    report_md.write_text(
        _render_markdown_report(
            generated_at=generated_at,
            total=total,
            ranked=ranked,
            remainder=remainder,
        ),
        encoding="utf-8",
    )
    report_json.write_text(
        json.dumps(
            _build_json_report(
                generated_at=generated_at,
                total=total,
                ranked=ranked,
                remainder=remainder,
            ),
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    log.info(
        "Report written: %s (%d failed, %d causes, %d remainder)",
        report_md,
        total,
        len(ranked),
        len(remainder),
    )
    log.info("JSON report written: %s", report_json)
    if ranked:
        top_cause, top_group = ranked[0]
        log.info("Top cause (%d / %d): %s", len(top_group), total, top_cause)
    elif remainder:
        log.info("All failures are in the remainder bucket (%d)", len(remainder))


def _filter_description(args: argparse.Namespace) -> str:
    parts: list[str] = []
    if args.stage:
        parts.append(f"stage={args.stage!r}")
    else:
        parts.append("any stage")
    if args.job_name:
        parts.append(f"exact name {args.job_name!r}")
    elif args.job_name_contains:
        parts.append(f"name contains {args.job_name_contains!r}")
    else:
        parts.append("any job name")
    return ", ".join(parts)


def _check_projects(
    targets: list[tuple[int, str]],
    args: argparse.Namespace,
    log: logging.Logger,
) -> list[FailedJobMatch]:
    if not targets:
        log.info("No projects to inspect")
        return []

    log.info(
        "Checking %d projects for %s (failed_job_limit=%d, workers=%d)...",
        len(targets),
        _filter_description(args),
        args.failed_job_limit,
        args.workers,
    )
    matches: list[FailedJobMatch] = []
    errors = 0
    checked = 0
    start = time.monotonic()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures: dict[Future[FailedJobMatch | None], str] = {
            pool.submit(
                _check_project,
                ProjectCheckJob(
                    gitlab_url=args.url,
                    token=args.token,
                    project_id=project_id,
                    path_with_namespace=path,
                    stage=args.stage,
                    job_name=args.job_name,
                    job_name_contains=args.job_name_contains,
                    failed_job_limit=args.failed_job_limit,
                    keep_trace=args.show_logs,
                ),
                log,
            ): path
            for project_id, path in targets
        }
        for future in as_completed(futures):
            checked += 1
            path = futures[future]
            try:
                match = future.result()
            except Exception as exc:  # noqa: BLE001 — isolate worker failures
                errors += 1
                log.error("Unexpected error for %s: %s", path, exc)
                match = None
            if match is not None:
                matches.append(match)
                if args.show_logs or args.project:
                    _print_match(match, log, show_logs=args.show_logs)
            if checked % CHECK_PROGRESS_INTERVAL == 0:
                elapsed = time.monotonic() - start
                rate = checked / elapsed if elapsed else 0.0
                log.info(
                    "Progress: %d/%d (%.1f/s, matches=%d, errors=%d)",
                    checked,
                    len(targets),
                    rate,
                    len(matches),
                    errors,
                )

    matches.sort(key=lambda item: (item.path_with_namespace, -(item.pipeline_id or 0)))
    log.info(
        "Done: checked=%d matches=%d errors=%d (log file: %s)",
        checked,
        len(matches),
        errors,
        LOG_FILE,
    )
    return matches


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Find failed CI jobs in a GitLab group, extract root-cause messages from "
            f"logs, and print frequency statistics. Default stage: {DEFAULT_STAGE!r}."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="See the script docstring for examples.",
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
        "--stage",
        default=DEFAULT_STAGE,
        help=f"CI stage to match (default: {DEFAULT_STAGE}); use --any-stage to disable",
    )
    parser.add_argument(
        "--any-stage",
        action="store_true",
        help="Match failed jobs in any stage (overrides --stage)",
    )
    parser.add_argument(
        "--job-name",
        default=None,
        help="Exact CI job name to match (default: any name in the selected stage)",
    )
    parser.add_argument(
        "--job-name-contains",
        default=None,
        help="Substring that must appear in the CI job name",
    )
    parser.add_argument(
        "--failed-job-limit",
        type=int,
        default=DEFAULT_FAILED_JOB_LIMIT,
        help=(
            "Max newest failed jobs to scan per project when looking for a "
            f"stage/name match (default: {DEFAULT_FAILED_JOB_LIMIT}; "
            "avoids missing arc_json behind newer non-matching failures)"
        ),
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help=f"Parallel project checkers (default: {DEFAULT_WORKERS})",
    )
    parser.add_argument(
        "--active-since-days",
        type=int,
        default=None,
        help=(
            "Only inspect projects with last_activity_at within N days "
            "(lists newest-first and stops early; major speedup)"
        ),
    )
    parser.add_argument(
        "--project-cache",
        default=None,
        help=(
            "JSON file for project-id cache. If the file exists it is loaded "
            f"(skips group listing). After a fresh listing it is written. "
            f"Example: {DEFAULT_PROJECT_CACHE}"
        ),
    )
    parser.add_argument(
        "--refresh-project-cache",
        action="store_true",
        help="Ignore an existing --project-cache file and relist the group",
    )
    parser.add_argument(
        "--include-subgroups",
        action="store_true",
        help="Include projects from subgroups (slower; default: group only)",
    )
    parser.add_argument(
        "--all-projects",
        action="store_true",
        help="Inspect every project in the group, not only ARC-hash paths",
    )
    parser.add_argument(
        "--project",
        default=None,
        help=(
            "Only this project id, path, or path_with_namespace "
            "(resolved directly via API; does not list the whole group)"
        ),
    )
    parser.add_argument(
        "--max-projects",
        type=int,
        default=None,
        help="Stop after selecting this many projects (useful for smoke tests)",
    )
    parser.add_argument(
        "--report-file",
        default=DEFAULT_REPORT_FILE,
        help=f"Markdown report output path (default: {DEFAULT_REPORT_FILE})",
    )
    parser.add_argument(
        "--report-json",
        default=DEFAULT_REPORT_JSON,
        help=f"JSON report output path (default: {DEFAULT_REPORT_JSON})",
    )
    parser.add_argument(
        "--show-logs",
        action="store_true",
        help="Print full job traces to the log (not recommended for large scans)",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help=argparse.SUPPRESS,  # deprecated: stats are the default; traces always fetched
    )
    args = parser.parse_args(argv)
    if args.any_stage:
        args.stage = None
    return args


def _validate_args(args: argparse.Namespace, log: logging.Logger) -> int | None:
    checks: list[tuple[bool, str]] = [
        (not args.token, "GitLab token required: pass --token or set GITLAB_TOKEN"),
        (args.workers < 1, "--workers must be at least 1"),
        (args.failed_job_limit < 1, "--failed-job-limit must be at least 1"),
        (args.max_projects is not None and args.max_projects < 1, "--max-projects must be at least 1"),
        (
            args.active_since_days is not None and args.active_since_days < 1,
            "--active-since-days must be at least 1",
        ),
        (bool(args.job_name and args.job_name_contains), "Use only one of --job-name or --job-name-contains"),
        (
            bool(args.refresh_project_cache and not args.project_cache),
            "--refresh-project-cache requires --project-cache",
        ),
    ]
    for failed, message in checks:
        if failed:
            log.error(message)
            return 1
    return None


def _resolve_targets(
    gl: gitlab.Gitlab,
    group: Group,
    args: argparse.Namespace,
    log: logging.Logger,
) -> list[tuple[int, str]] | None:
    """Return targets, or None on fatal resolution error."""
    if args.project:
        targets = _resolve_single_project(gl, group, args.project, log)
        return targets or None

    cache_path = Path(args.project_cache) if args.project_cache else None
    if cache_path is not None and not args.refresh_project_cache:
        cached = _load_project_cache(cache_path, group.full_path, log)
        if cached is not None:
            if args.max_projects is not None:
                return cached[: args.max_projects]
            return cached

    active_since = None
    if args.active_since_days is not None:
        active_since = datetime.now(UTC) - timedelta(days=args.active_since_days)
        log.info("Activity cutoff: last_activity_at >= %s", active_since.isoformat())

    targets = _collect_projects(
        group,
        log,
        CollectConfig(
            all_projects=args.all_projects,
            include_subgroups=args.include_subgroups,
            max_projects=args.max_projects,
            active_since=active_since,
        ),
    )
    if cache_path is not None:
        _save_project_cache(cache_path, group.full_path, targets, log)
    return targets


def main(argv: list[str] | None = None) -> int:
    """List projects with a failed job and print logs."""
    args = _parse_args(argv)
    log = _configure_logging()

    validation_error = _validate_args(args, log)
    if validation_error is not None:
        return validation_error

    gl = gitlab.Gitlab(args.url, private_token=args.token, per_page=100)
    gl.auth()

    group = gl.groups.get(args.group)
    log.info("Group: %s (id=%s)", group.full_path, group.id)
    log.info("Job filter: %s", _filter_description(args))

    targets = _resolve_targets(gl, group, args, log)
    if targets is None:
        return 1

    matches = _check_projects(targets, args, log)

    if not matches:
        log.info("No matching failed jobs found (%s)", _filter_description(args))
        return 0

    _report_cause_statistics(
        matches,
        report_md=Path(args.report_file),
        report_json=Path(args.report_json),
        log=log,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
