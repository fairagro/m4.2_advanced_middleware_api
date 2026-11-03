#!/usr/bin/env python3
r"""Report yearly GitHub activity stats across fairagro middleware repos.

Metrics (calendar year, UTC):
  - major_releases: published, non-draft GitHub Releases whose tag semver is X.0.0
  - minor_releases: published, non-draft GitHub Releases whose tag semver is X.Y.0 (Y > 0)
  - closed_issues: issues (not PRs) with closed:YYYY-01-01..YYYY-12-31
  - commits: commits on the default branch in [YYYY-01-01, YYYY+1-01-01) via GraphQL

Semver is extracted from fleet tags such as ``N-docker-vX.Y.Z`` / ``N-chart-vX.Y.Z``
or plain ``vX.Y.Z``. Pre-release suffixes (``-rc…``, ``-migrate…``) are ignored
(not counted as major/minor). Docker and Helm chart releases are counted separately
when both exist.

Requires: ``gh`` authenticated for github.com (use ``scripts/bin/gh`` / unset
stale ``GH_TOKEN`` in agent shells per Devinfra #69).

Usage:
  ./scripts/report-github-year-stats.py
  ./scripts/report-github-year-stats.py --year 2026
  ./scripts/report-github-year-stats.py --year 2027 --json
  ./scripts/report-github-year-stats.py --year 2026 \\
      --repo fairagro/m4.2_advanced_middleware_api \\
      --repo fairagro/m4.2_middleware_devinfra
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

DEFAULT_REPOS: tuple[str, ...] = (
    "fairagro/m4.2_advanced_middleware_api",
    "fairagro/m4.2_middleware_devinfra",
    "fairagro/m4.2_middleware_harvester",
    "fairagro/m4_rdi_portfolio",
    "fairagro/m4.2_infrastructure",
    "fairagro/m4.2_sql_to_arc",
)

_MIN_REPORT_YEAR = 2000
_MAX_REPORT_YEAR = 2100

# Trailing stable semver in a tag (optional leading junk / surface prefix).
_SEMVER_RE = re.compile(r"(?:^|[^0-9])v?(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)$")


@dataclass(frozen=True)
class ReleaseBucket:
    """Stable-semver release tallies and matching tags for one repo/year."""

    major: int
    minor: int
    patch: int
    skipped: int
    major_tags: tuple[str, ...]
    minor_tags: tuple[str, ...]


@dataclass(frozen=True)
class RepoStats:
    """Per-repository activity counts for one calendar year."""

    repo: str
    year: int
    closed_issues: int
    commits: int
    releases: ReleaseBucket


def _gh_env() -> dict[str, str]:
    """Prefer store-backed auth; drop a stale GH_TOKEN shadow (devinfra#69)."""
    env = dict(os.environ)
    env.pop("GH_TOKEN", None)
    env.setdefault("GH_PAGER", "")
    return env


def _gh(*args: str, input_text: str | None = None) -> str:
    cmd = ["gh", *args]
    try:
        completed = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            env=_gh_env(),
            input=input_text,
        )
    except FileNotFoundError as exc:
        raise SystemExit("gh CLI not found on PATH") from exc
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        raise SystemExit(f"gh {' '.join(args)} failed: {stderr or exc}") from exc
    return completed.stdout


def _gh_json(*args: str) -> Any:
    return json.loads(_gh(*args) or "null")


def parse_stable_semver(tag_name: str) -> tuple[int, int, int] | None:
    """Return (major, minor, patch) for a stable release tag, else None."""
    match = _SEMVER_RE.search(tag_name.strip())
    if match is None:
        return None
    return (
        int(match.group("major")),
        int(match.group("minor")),
        int(match.group("patch")),
    )


def classify_release(tag_name: str) -> str | None:
    """Return 'major', 'minor', 'patch', or None if not a stable semver tag."""
    parsed = parse_stable_semver(tag_name)
    if parsed is None:
        return None
    major, minor, patch = parsed
    if minor == 0 and patch == 0:
        return "major"
    if patch == 0:
        return "minor"
    return "patch"


def _in_year(iso_ts: str | None, year: int) -> bool:
    if not iso_ts:
        return False
    return iso_ts.startswith(f"{year}-")


def _flatten_release_pages(pages: Any) -> list[dict[str, Any]]:
    """Flatten ``gh api --paginate --slurp`` pages into release dicts."""
    if not isinstance(pages, list):
        return []
    releases: list[dict[str, Any]] = []
    for page in pages:
        if isinstance(page, list):
            releases.extend(item for item in page if isinstance(item, dict))
        elif isinstance(page, dict):
            releases.append(page)
    return releases


def _tally_one_release(
    release: dict[str, Any],
    year: int,
    major_tags: list[str],
    minor_tags: list[str],
) -> tuple[int, int]:
    """Classify one release; return ``(patch_delta, skipped_delta)``."""
    when = release.get("published_at") or release.get("created_at")
    if release.get("draft") or not _in_year(when, year):
        return 0, 0
    if release.get("prerelease"):
        return 0, 1
    tag = str(release.get("tag_name") or "")
    kind = classify_release(tag)
    if kind == "major":
        major_tags.append(tag)
    elif kind == "minor":
        minor_tags.append(tag)
    elif kind == "patch":
        return 1, 0
    else:
        return 0, 1
    return 0, 0


def count_releases(repo: str, year: int) -> tuple[int, int, int, int, list[str], list[str]]:
    """Return major, minor, patch, skipped, major_tags, minor_tags."""
    pages = _gh_json("api", "--paginate", "--slurp", f"repos/{repo}/releases")
    major_tags: list[str] = []
    minor_tags: list[str] = []
    patch = 0
    skipped = 0
    for release in _flatten_release_pages(pages):
        patch_delta, skipped_delta = _tally_one_release(release, year, major_tags, minor_tags)
        patch += patch_delta
        skipped += skipped_delta
    return len(major_tags), len(minor_tags), patch, skipped, major_tags, minor_tags


def count_closed_issues(repo: str, year: int) -> int:
    """Count issues closed in ``year`` (UTC), excluding pull requests."""
    query = f"repo:{repo} is:issue is:closed closed:{year}-01-01..{year}-12-31"
    payload = _gh_json(
        "api",
        "-X",
        "GET",
        "search/issues",
        "-f",
        f"q={query}",
        "--jq",
        "{total_count, incomplete_results}",
    )
    if payload.get("incomplete_results"):
        print(
            f"warning: closed-issue search incomplete for {repo}",
            file=sys.stderr,
        )
    return int(payload.get("total_count") or 0)


def count_default_branch_commits(repo: str, year: int) -> int:
    """Count default-branch commits with committedDate in [year, year+1)."""
    owner, name = repo.split("/", 1)
    since = f"{year}-01-01T00:00:00Z"
    until = f"{year + 1}-01-01T00:00:00Z"
    # history() only has `since`; subtract next-year prefix for a closed interval.
    query = """
    query($owner: String!, $name: String!, $since: GitTimestamp!, $until: GitTimestamp!) {
      repository(owner: $owner, name: $name) {
        defaultBranchRef {
          target {
            ... on Commit {
              fromYear: history(since: $since) { totalCount }
              fromNext: history(since: $until) { totalCount }
            }
          }
        }
      }
    }
    """
    payload = _gh_json(
        "api",
        "graphql",
        "-f",
        f"query={query}",
        "-F",
        f"owner={owner}",
        "-F",
        f"name={name}",
        "-F",
        f"since={since}",
        "-F",
        f"until={until}",
    )
    repo_data = (payload.get("data") or {}).get("repository") or {}
    ref = repo_data.get("defaultBranchRef")
    if not ref:
        return 0
    target = ref.get("target") or {}
    from_year = int(((target.get("fromYear") or {}).get("totalCount")) or 0)
    from_next = int(((target.get("fromNext") or {}).get("totalCount")) or 0)
    return max(from_year - from_next, 0)


def collect_repo_stats(repo: str, year: int) -> RepoStats:
    """Gather release, issue, and commit counts for one repository."""
    major, minor, patch, skipped, major_tags, minor_tags = count_releases(repo, year)
    return RepoStats(
        repo=repo,
        year=year,
        closed_issues=count_closed_issues(repo, year),
        commits=count_default_branch_commits(repo, year),
        releases=ReleaseBucket(
            major=major,
            minor=minor,
            patch=patch,
            skipped=skipped,
            major_tags=tuple(major_tags),
            minor_tags=tuple(minor_tags),
        ),
    )


def format_table(rows: Sequence[RepoStats]) -> str:
    """Format a sequence of RepoStats as a table."""
    headers = (
        "repo",
        "major",
        "minor",
        "closed_issues",
        "commits",
    )
    data = [
        (
            r.repo,
            str(r.releases.major),
            str(r.releases.minor),
            str(r.closed_issues),
            str(r.commits),
        )
        for r in rows
    ]
    totals = (
        "TOTAL",
        str(sum(r.releases.major for r in rows)),
        str(sum(r.releases.minor for r in rows)),
        str(sum(r.closed_issues for r in rows)),
        str(sum(r.commits for r in rows)),
    )
    data.append(totals)
    widths = [max(len(headers[i]), *(len(row[i]) for row in data)) for i in range(len(headers))]

    def fmt(row: tuple[str, ...]) -> str:
        return "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row))

    lines = [fmt(headers), fmt(tuple("-" * w for w in widths))]
    lines.extend(fmt(row) for row in data)
    return "\n".join(lines)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--year",
        type=int,
        default=2026,
        help="Calendar year to report (UTC). Default: 2026",
    )
    parser.add_argument(
        "--repo",
        action="append",
        dest="repos",
        metavar="OWNER/NAME",
        help="Repo to include (repeatable). Default: fairagro middleware set",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON (per-repo + totals)",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the year-stats report for the given CLI arguments."""
    args = parse_args(argv)
    if args.year < _MIN_REPORT_YEAR or args.year > _MAX_REPORT_YEAR:
        print(f"refusing year={args.year}", file=sys.stderr)
        return 2
    repos = tuple(args.repos) if args.repos else DEFAULT_REPOS

    rows = [collect_repo_stats(repo, args.year) for repo in repos]
    totals = {
        "year": args.year,
        "major_releases": sum(r.releases.major for r in rows),
        "minor_releases": sum(r.releases.minor for r in rows),
        "closed_issues": sum(r.closed_issues for r in rows),
        "commits": sum(r.commits for r in rows),
        "patch_releases": sum(r.releases.patch for r in rows),
    }

    if args.json:
        payload = {
            "year": args.year,
            "repos": [
                {
                    "repo": r.repo,
                    "major_releases": r.releases.major,
                    "minor_releases": r.releases.minor,
                    "closed_issues": r.closed_issues,
                    "commits": r.commits,
                    "patch_releases": r.releases.patch,
                    "skipped_prerelease_or_unparsed_tags": r.releases.skipped,
                    "major_release_tags": list(r.releases.major_tags),
                    "minor_release_tags": list(r.releases.minor_tags),
                }
                for r in rows
            ],
            "totals": totals,
            "notes": {
                "releases": (
                    "Published non-draft GitHub Releases in the calendar year; "
                    "major = X.0.0, minor = X.Y.0 (Y>0); docker/chart counted separately"
                ),
                "commits": "Default-branch commits with committedDate in [year, year+1)",
                "closed_issues": "GitHub issues (not PRs) closed within the calendar year",
            },
        }
        print(json.dumps(payload, indent=2, sort_keys=False))
    else:
        print(f"GitHub year stats for {args.year} (UTC)")
        print()
        print(format_table(rows))
        print()
        print(
            "Notes: major=X.0.0, minor=X.Y.0 (Y>0); patches not in primary columns; "
            "docker/chart releases counted separately; commits = default branch."
        )
        if any(r.releases.patch or r.releases.skipped for r in rows):
            print(f"Extra: patch_releases={totals['patch_releases']} (informational; not requested in primary totals)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
