"""Code-review plumbing: diff context, /tmp report, PR COMMENT review publish."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from m42_ai.gh import GhError, repo_owner_name, run_gh, run_git

_SLUG_SAFE = re.compile(r"[^a-zA-Z0-9._-]+")


def _cwd(cwd: Path | None) -> Path | None:
    return cwd


def _git_out(args: list[str], *, cwd: Path | None) -> str:
    return run_git(args, cwd=cwd).stdout.strip()


def _local_diff_range(base: str, *, cwd: Path | None) -> tuple[str, str, str]:
    """Return (merge_base, head_sha, triple_dot_range) for merge-base(base, HEAD)...HEAD."""
    head = _git_out(["rev-parse", "HEAD"], cwd=cwd)
    merge_base = _git_out(["merge-base", base, "HEAD"], cwd=cwd)
    return merge_base, head, f"{merge_base}...{head}"


def shape_local_context(*, base: str = "main", cwd: Path | None = None) -> dict[str, Any]:
    """JSON for local base...HEAD without GitHub calls."""
    merge_base, head, rng = _local_diff_range(base, cwd=cwd)
    branch = _git_out(["rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd)
    names = _git_out(["diff", "--name-only", rng], cwd=cwd)
    paths = [p for p in names.splitlines() if p]
    shortstat = _git_out(["diff", "--shortstat", rng], cwd=cwd)
    return {
        "ok": True,
        "mode": "local",
        "base": base,
        "merge_base": merge_base,
        "head": head,
        "head_ref": branch,
        "range": rng,
        "paths": paths,
        "stats": shortstat or None,
        "diff_omitted": True,
        "pr": None,
    }


def shape_pr_context(
    pr: int,
    *,
    owner: str | None = None,
    repo: str | None = None,
    cwd: Path | None = None,
) -> dict[str, Any]:
    """JSON for a PR diff via gh (paths/stats; no full patch dump)."""
    if not owner or not repo:
        o, r = repo_owner_name(cwd=cwd)
        owner = owner or o
        repo = repo or r
    view = run_gh(
        [
            "pr",
            "view",
            str(pr),
            "--repo",
            f"{owner}/{repo}",
            "--json",
            "number,url,baseRefName,headRefName,headRefOid,commits",
        ],
        cwd=cwd,
    )
    meta = json.loads(view.stdout)
    name_proc = run_gh(
        ["pr", "diff", str(pr), "--repo", f"{owner}/{repo}", "--name-only"],
        cwd=cwd,
        check=False,
    )
    if name_proc.returncode != 0:
        raise GhError(
            ["gh", "pr", "diff", str(pr), "--name-only"],
            name_proc.returncode,
            name_proc.stderr or "",
            name_proc.stdout or "",
        )
    paths = [p for p in name_proc.stdout.splitlines() if p.strip()]
    stats = f"{len(paths)} files changed" if paths else "0 files changed"
    return {
        "ok": True,
        "mode": "pr",
        "base": meta.get("baseRefName") or "main",
        "merge_base": None,
        "head": meta.get("headRefOid"),
        "head_ref": meta.get("headRefName"),
        "range": None,
        "paths": paths,
        "stats": stats,
        "diff_omitted": True,
        "pr": {
            "number": int(meta["number"]),
            "url": meta.get("url"),
            "owner": owner,
            "repo": repo,
        },
    }


def code_review_context(
    *,
    base: str = "main",
    pr: int | None = None,
    owner: str | None = None,
    repo: str | None = None,
    cwd: Path | None = None,
) -> dict[str, Any]:
    if pr is not None:
        return shape_pr_context(pr, owner=owner, repo=repo, cwd=_cwd(cwd))
    return shape_local_context(base=base, cwd=_cwd(cwd))


def _safe_slug(raw: str) -> str:
    s = _SLUG_SAFE.sub("-", raw.strip()).strip("-._") or "review"
    return s[:80]


def write_report(
    body: str,
    *,
    slug: str | None = None,
    tmp_dir: Path | None = None,
) -> dict[str, Any]:
    """Write Markdown under /tmp/code-review-<slug>-<utc>.md."""
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    label = _safe_slug(slug or "local")
    directory = tmp_dir or Path("/tmp")
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"code-review-{label}-{stamp}.md"
    path.write_text(body if body.endswith("\n") else body + "\n", encoding="utf-8")
    return {"ok": True, "path": str(path.resolve()), "slug": label}


def publish_report(
    *,
    body_file: Path,
    pr: int | None = None,
    owner: str | None = None,
    repo: str | None = None,
    cwd: Path | None = None,
) -> dict[str, Any]:
    """Submit COMMENT PR review, or no-op GitHub when pr is None."""
    path = body_file.expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"body file not found: {path}")

    if pr is None:
        return {
            "ok": True,
            "channel": "local",
            "path": str(path),
            "pr": None,
        }

    repo_args: list[str] = []
    if owner and repo:
        repo_args = ["--repo", f"{owner}/{repo}"]
    elif owner or repo:
        raise ValueError("provide both --owner and --repo, or neither")

    review_argv = ["pr", "review", str(pr), *repo_args, "--comment", "--body-file", str(path)]
    try:
        run_gh(review_argv, cwd=cwd)
        return {
            "ok": True,
            "channel": "pull_request_review",
            "path": str(path),
            "pr": pr,
        }
    except GhError as review_exc:
        comment_argv = ["pr", "comment", str(pr), *repo_args, "--body-file", str(path)]
        try:
            run_gh(comment_argv, cwd=cwd)
        except GhError as comment_exc:
            raise GhError(
                comment_argv,
                comment_exc.returncode,
                f"pr review failed ({review_exc}); pr comment also failed: {comment_exc.stderr}",
                comment_exc.stdout,
            ) from comment_exc
        return {
            "ok": True,
            "channel": "conversation_comment",
            "path": str(path),
            "pr": pr,
            "review_error": str(review_exc),
        }
