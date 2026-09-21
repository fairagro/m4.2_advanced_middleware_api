"""Sync follow-up plumbing: PR-for-SHA, SYNC-FOLLOWUP parse, ensure product issues."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from m42_ai.gh import run_gh
from m42_ai.issue import LABEL_SPECS, create_issue, ensure_labels

SYNC_FOLLOWUP_RE = re.compile(r"(?m)^[ \t]*SYNC-FOLLOWUP:[ \t]*(?P<id>[A-Za-z0-9][A-Za-z0-9._/-]*)[ \t]*$")
DEDUPE_LABEL_PREFIX = "sync-followup:"
DEFAULT_COST = "cost:medium"
DEFAULT_SEVERITY = "severity:low"
FOLLOWUP_LABEL_COLOR = "BFD4F2"
FOLLOWUP_LABEL_DESC = "Devinfra sync product follow-up (stable id)"

# Devinfra-only template (not on product sync allowlist).
DEFAULT_TEMPLATE = Path(__file__).resolve().parents[4] / "docs" / "sync-followup-issue.md"

_STABLE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")


def parse_sync_followup_ids(*texts: str) -> list[str]:
    """Return distinct stable ids from SYNC-FOLLOWUP trailers in order of first appearance."""
    seen: set[str] = set()
    out: list[str] = []
    for text in texts:
        if not text:
            continue
        for match in SYNC_FOLLOWUP_RE.finditer(text):
            sid = match.group("id")
            if sid in seen:
                continue
            seen.add(sid)
            out.append(sid)
    return out


def validate_stable_id(stable_id: str) -> str:
    sid = stable_id.strip()
    if not _STABLE_ID_RE.fullmatch(sid):
        raise ValueError(f"invalid SYNC-FOLLOWUP id: {stable_id!r}")
    return sid


def dedupe_label(stable_id: str) -> str:
    return f"{DEDUPE_LABEL_PREFIX}{validate_stable_id(stable_id)}"


def ensure_dedupe_label(label: str, *, repo: str | None = None, cwd: Path | None = None) -> None:
    """Create ``sync-followup:<id>`` if missing (not part of triage LABEL_SPECS)."""
    if not label.startswith(DEDUPE_LABEL_PREFIX):
        raise ValueError(f"not a sync-followup dedupe label: {label!r}")
    args = ["label", "list", "--limit", "1000", "--json", "name", "--jq", ".[].name"]
    if repo:
        args.extend(["--repo", repo])
    proc = run_gh(args, cwd=cwd)
    existing = {line.strip() for line in proc.stdout.splitlines() if line.strip()}
    if label in existing:
        return
    create_args = [
        "label",
        "create",
        label,
        "--color",
        FOLLOWUP_LABEL_COLOR,
        "--description",
        FOLLOWUP_LABEL_DESC,
    ]
    if repo:
        create_args.extend(["--repo", repo])
    run_gh(create_args, cwd=cwd)


def pr_for_commit(
    sha: str,
    *,
    owner: str | None = None,
    repo: str | None = None,
    cwd: Path | None = None,
) -> dict[str, Any] | None:
    """Return ``{number, url, title, body}`` for a PR containing ``sha``, or None."""
    short = sha.strip()
    if not short:
        raise ValueError("sha is empty")
    args = [
        "pr",
        "list",
        "--state",
        "all",
        "--search",
        short,
        "--limit",
        "20",
        "--json",
        "number,url,title,body,mergeCommit,commits",
    ]
    if owner and repo:
        args.extend(["--repo", f"{owner}/{repo}"])
    proc = run_gh(args, cwd=cwd)
    listed = json.loads(proc.stdout)
    if not isinstance(listed, list):
        raise RuntimeError("gh pr list JSON: expected a list")

    needle = short.lower()
    for item in listed:
        if not isinstance(item, dict):
            continue
        merge = item.get("mergeCommit") or {}
        merge_oid = ""
        if isinstance(merge, dict):
            merge_oid = str(merge.get("oid") or "")
        commits = item.get("commits") or []
        commit_oids: list[str] = []
        if isinstance(commits, list):
            for c in commits:
                if isinstance(c, dict):
                    oid = str(c.get("oid") or "")
                    if oid:
                        commit_oids.append(oid)
        oids = [merge_oid, *commit_oids]
        if any(
            oid and (oid.lower().startswith(needle) or needle.startswith(oid.lower()[: len(needle)])) for oid in oids
        ):
            return {
                "number": int(item["number"]),
                "url": str(item["url"]),
                "title": str(item.get("title") or ""),
                "body": str(item.get("body") or ""),
            }

    if listed and len(listed) == 1 and isinstance(listed[0], dict) and listed[0].get("number"):
        item = listed[0]
        return {
            "number": int(item["number"]),
            "url": str(item["url"]),
            "title": str(item.get("title") or ""),
            "body": str(item.get("body") or ""),
        }
    return None


def _bodies_from_comment_list(items: object) -> list[str]:
    bodies: list[str] = []
    if not isinstance(items, list):
        return bodies
    for item in items:
        if isinstance(item, dict) and item.get("body"):
            bodies.append(str(item["body"]))
    return bodies


def _bodies_from_reviews(items: object) -> list[str]:
    bodies: list[str] = []
    if not isinstance(items, list):
        return bodies
    for item in items:
        if not isinstance(item, dict):
            continue
        if str(item.get("state") or "").upper() == "PENDING":
            continue
        if item.get("body"):
            bodies.append(str(item["body"]))
    return bodies


def _pr_comment_bodies(
    pr: int,
    *,
    owner: str | None = None,
    repo: str | None = None,
    cwd: Path | None = None,
) -> list[str]:
    """Issue comments + submitted review bodies for a PR."""
    if owner and repo:
        comments = json.loads(
            run_gh(
                ["api", f"repos/{owner}/{repo}/issues/{pr}/comments", "--paginate"],
                cwd=cwd,
            ).stdout
            or "[]"
        )
        reviews = json.loads(
            run_gh(
                ["api", f"repos/{owner}/{repo}/pulls/{pr}/reviews", "--paginate"],
                cwd=cwd,
            ).stdout
            or "[]"
        )
        return [*_bodies_from_comment_list(comments), *_bodies_from_reviews(reviews)]

    repo_args = ["--repo", f"{owner}/{repo}"] if owner and repo else []
    data = json.loads(run_gh(["pr", "view", str(pr), *repo_args, "--json", "comments,reviews"], cwd=cwd).stdout)
    return [
        *_bodies_from_comment_list(data.get("comments")),
        *_bodies_from_reviews(data.get("reviews")),
    ]


def collect_sync_followup_ids(
    *,
    pr: int,
    owner: str | None = None,
    repo: str | None = None,
    cwd: Path | None = None,
    body: str | None = None,
) -> list[str]:
    """Collect distinct SYNC-FOLLOWUP ids from PR body and comments/reviews."""
    if body is None:
        args = ["pr", "view", str(pr), "--json", "body"]
        if owner and repo:
            args.extend(["--repo", f"{owner}/{repo}"])
        proc = run_gh(args, cwd=cwd)
        meta = json.loads(proc.stdout)
        body = str(meta.get("body") or "")
    comment_bodies = _pr_comment_bodies(pr, owner=owner, repo=repo, cwd=cwd)
    return parse_sync_followup_ids(body, *comment_bodies)


def render_followup_body(
    *,
    stable_id: str,
    source_pr_url: str | None,
    source_sha: str | None,
    template_path: Path | None = None,
) -> str:
    path = template_path or DEFAULT_TEMPLATE
    if path.is_file():
        text = path.read_text(encoding="utf-8")
    else:
        text = (
            "## Type\n\nTask\n\n## Problem\n\n"
            "Devinfra sync follow-up `{stable_id}`.\n\n"
            "## Links\n\n- Source PR: {source_pr_url}\n- Source SHA: {source_sha}\n"
        )
    return (
        text
        .replace("{stable_id}", stable_id)
        .replace("{source_pr_url}", source_pr_url or "(none)")
        .replace("{source_sha}", source_sha or "(none)")
    )


def find_open_followup(
    *,
    repo: str,
    stable_id: str,
    cwd: Path | None = None,
) -> dict[str, Any] | None:
    label = dedupe_label(stable_id)
    proc = run_gh(
        [
            "issue",
            "list",
            "--repo",
            repo,
            "--state",
            "open",
            "--label",
            label,
            "--limit",
            "5",
            "--json",
            "number,url,title,labels",
        ],
        cwd=cwd,
    )
    listed = json.loads(proc.stdout)
    if not isinstance(listed, list) or not listed:
        return None
    item = listed[0]
    if not isinstance(item, dict):
        return None
    return {
        "number": int(item["number"]),
        "url": str(item["url"]),
        "title": str(item.get("title") or ""),
        "reused": True,
    }


def ensure_sync_followup_issue(
    *,
    repo: str,
    stable_id: str,
    source_pr_url: str | None = None,
    source_sha: str | None = None,
    cost: str = DEFAULT_COST,
    template_path: Path | None = None,
    dry_run: bool = False,
    cwd: Path | None = None,
) -> dict[str, Any]:
    """Create or reuse a product Task for ``stable_id``."""
    sid = validate_stable_id(stable_id)
    label = dedupe_label(sid)
    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "repo": repo,
            "id": sid,
            "label": label,
            "action": "would_ensure",
        }

    existing = find_open_followup(repo=repo, stable_id=sid, cwd=cwd)
    if existing is not None:
        return {"ok": True, "dry_run": False, "repo": repo, "id": sid, "action": "reused", **existing}

    triage = [DEFAULT_SEVERITY, cost]
    if cost not in LABEL_SPECS:
        raise ValueError(f"invalid cost label: {cost!r}")
    ensure_labels(triage, cwd=cwd, repo=repo)
    ensure_dedupe_label(label, repo=repo, cwd=cwd)

    title = f"Sync follow-up: {sid}"
    body = render_followup_body(
        stable_id=sid,
        source_pr_url=source_pr_url,
        source_sha=source_sha,
        template_path=template_path,
    )
    created = create_issue(
        title=title,
        body=body,
        issue_type="Task",
        labels=[*triage, label],
        cwd=cwd,
        repo=repo,
    )
    return {
        "ok": True,
        "dry_run": False,
        "repo": repo,
        "id": sid,
        "action": "created",
        "url": created["url"],
        "labels": created["labels"],
    }
