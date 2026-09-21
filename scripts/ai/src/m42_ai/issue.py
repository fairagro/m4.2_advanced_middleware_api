"""Issue create / issue-start plumbing via `gh` and `git`."""

from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path
from typing import Any

from m42_ai.gh import GhError, repo_owner_name, run_gh, run_git

LABEL_SPECS: dict[str, tuple[str, str]] = {
    "severity:blocker": ("B60205", "Blocks merge / data loss / broken contract"),
    "severity:high": ("D93F0B", "Serious defect with a real path"),
    "severity:medium": ("FBCA04", "Important but not high-risk"),
    "severity:low": ("0E8A16", "Nit / low urgency"),
    "practicality:high": ("1D76DB", "Realistic path in this system"),
    "practicality:medium": ("5319E7", "Non-default / internal / admin path"),
    "practicality:low": ("C5DEF5", "Mostly excluded by types/invariants"),
    "practicality:none": ("EDEDED", "No real path / unsupported environment"),
    "practicality:seen-in-the-wild": ("BFDADC", "Observed in real usage"),
    "cost:cheap": ("C2E0C6", "Small local fix"),
    "cost:medium": ("FEF2C0", "Moderate issue-planning cost"),
    "cost:expensive": ("F9D0C4", "Large or cross-cutting work"),
}

ORG_TYPES = frozenset({"Bug", "Security", "Feature", "Task", "Discussion", "Refactoring"})
ISSUE_BRANCH_CHANNELS = frozenset({"build", "ci", "docs"})
DEFAULT_ISSUE_BRANCH_CHANNEL = "build"
ISSUE_URL_RE = re.compile(r"https://github\.com/[^/\s]+/[^/\s]+/issues/\d+")


def slugify(text: str, *, max_len: int = 48) -> str:
    s = text.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    if not s:
        s = "issue"
    return s[:max_len].rstrip("-")


def normalize_issue_channel(channel: str | None) -> str:
    """Return a fleet CI channel (`build` | `ci` | `docs`); default `build`."""
    raw = (channel or DEFAULT_ISSUE_BRANCH_CHANNEL).strip().lower()
    if raw not in ISSUE_BRANCH_CHANNELS:
        allowed = ", ".join(sorted(ISSUE_BRANCH_CHANNELS))
        raise ValueError(f"channel must be one of: {allowed} (got {channel!r})")
    return raw


def issue_branch_name(issue: int, slug: str, *, channel: str | None = None) -> str:
    ch = normalize_issue_channel(channel)
    return f"{ch}/issue-{issue}-{slug}"


def _repo_args(repo: str | None) -> list[str]:
    return ["--repo", repo] if repo else []


def ensure_labels(
    labels: list[str],
    *,
    cwd: Path | None = None,
    repo: str | None = None,
) -> None:
    unknown = [n for n in labels if n not in LABEL_SPECS]
    if unknown:
        raise ValueError(f"off-allowlist labels: {unknown}")
    # Default gh page size is 30; triage repos can exceed that. Raise the limit so
    # existing allowlisted labels are not mistaken for missing.
    proc = run_gh(
        [
            "label",
            "list",
            "--limit",
            "1000",
            "--json",
            "name",
            "--jq",
            ".[].name",
            *_repo_args(repo),
        ],
        cwd=cwd,
    )
    existing = {line.strip() for line in proc.stdout.splitlines() if line.strip()}
    for name in labels:
        if name in existing:
            continue
        color, desc = LABEL_SPECS[name]
        run_gh(
            ["label", "create", name, "--color", color, "--description", desc, *_repo_args(repo)],
            cwd=cwd,
        )


def _extract_issue_url(text: str) -> str | None:
    m = ISSUE_URL_RE.search(text)
    return m.group(0) if m else None


def create_issue(
    *,
    title: str,
    body: str,
    issue_type: str,
    labels: list[str],
    parent: int | None = None,
    cwd: Path | None = None,
    repo: str | None = None,
) -> dict[str, Any]:
    if issue_type not in ORG_TYPES:
        raise ValueError(f"invalid org issue type: {issue_type!r}")
    # Triage labels must be allowlisted; sync-followup:* may be pre-created by callers.
    triage = [n for n in labels if n in LABEL_SPECS]
    extra = [n for n in labels if n not in LABEL_SPECS]
    if extra and not all(n.startswith("sync-followup:") for n in extra):
        raise ValueError(f"off-allowlist labels: {extra}")
    ensure_labels(triage, cwd=cwd, repo=repo)

    def _args(with_parent: bool) -> list[str]:
        args = [
            "issue",
            "create",
            "--title",
            title,
            "--body-file",
            "-",
            "--type",
            issue_type,
            *_repo_args(repo),
        ]
        for lab in labels:
            args.extend(["--label", lab])
        if with_parent and parent is not None:
            args.extend(["--parent", str(parent)])
        return args

    relation = f"sub-of #{parent}" if parent is not None else "linked"
    parent_failed: str | None = None

    def _result(
        *,
        url: str,
        relation_out: str,
        parent_fallback: bool,
        parent_error: str | None,
        partial_failure: bool,
    ) -> dict[str, Any]:
        return {
            "url": url,
            "type": issue_type,
            "labels": labels,
            "relation": relation_out,
            "parent_fallback": parent_fallback,
            "parent_error": parent_error,
            "partial_failure": partial_failure,
        }

    if parent is not None:
        try:
            proc = run_gh(_args(True), input_text=body, cwd=cwd)
            created_url = _extract_issue_url(proc.stdout) or proc.stdout.strip()
            return _result(
                url=created_url,
                relation_out=relation,
                parent_fallback=False,
                parent_error=None,
                partial_failure=False,
            )
        except GhError as exc:
            # Only fall back when no issue URL was produced. Parent attach can fail
            # after create; URL is often on stdout while stderr explains the error —
            # GhError keeps both streams so we do not open a second issue.
            maybe = _extract_issue_url(exc.stdout) or _extract_issue_url(exc.stderr) or _extract_issue_url(str(exc))
            if maybe:
                return _result(
                    url=maybe,
                    relation_out="linked",
                    parent_fallback=False,
                    parent_error=exc.stderr.strip() or str(exc),
                    partial_failure=True,
                )
            parent_failed = exc.stderr.strip() or str(exc)

    proc = run_gh(_args(False), input_text=body, cwd=cwd)
    created_url = _extract_issue_url(proc.stdout) or proc.stdout.strip()
    return _result(
        url=created_url,
        relation_out="linked" if parent_failed else relation,
        parent_fallback=bool(parent_failed),
        parent_error=parent_failed,
        partial_failure=bool(parent_failed),
    )


def _parse_issue_type(raw: Any) -> str | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        name = raw.strip()
        return name or None
    if isinstance(raw, dict):
        name = str(raw.get("name") or "").strip()
        return name or None
    return None


def _label_names(labels_raw: list[Any]) -> list[str]:
    names: list[str] = []
    for item in labels_raw:
        raw = item.get("name") if isinstance(item, dict) else item
        if raw is None:
            continue
        name = str(raw).strip()
        if name:
            names.append(name)
    return names


def _triage_from_labels(label_names: list[str]) -> dict[str, str | None]:
    severity = next((n for n in label_names if n.startswith("severity:")), None)
    practicality = next((n for n in label_names if n.startswith("practicality:")), None)
    cost = next((n for n in label_names if n.startswith("cost:")), None)
    return {"severity": severity, "practicality": practicality, "cost": cost}


def view_issue(issue: int, *, cwd: Path | None = None) -> dict[str, Any]:
    """Fetch a stable triage-oriented JSON shape for an issue (incl. comments)."""
    proc = run_gh(
        [
            "issue",
            "view",
            str(issue),
            "--json",
            "number,title,url,body,labels,state,author,issueType,comments",
        ],
        cwd=cwd,
    )
    meta = json.loads(proc.stdout)
    labels_raw = meta.get("labels") or []
    label_names = _label_names(labels_raw if isinstance(labels_raw, list) else [])
    author = meta.get("author") or {}
    author_login = author.get("login") if isinstance(author, dict) else None
    comments_out: list[dict[str, str | None]] = []
    for c in meta.get("comments") or []:
        if not isinstance(c, dict):
            continue
        c_author = c.get("author") or {}
        login = c_author.get("login") if isinstance(c_author, dict) else None
        comments_out.append(
            {
                "author": login,
                "body": str(c.get("body") or ""),
                "created_at": str(c.get("createdAt") or c.get("created_at") or "") or None,
            }
        )
    comments_out.sort(key=lambda row: row.get("created_at") or "")
    return {
        "number": int(meta["number"]),
        "title": str(meta["title"]),
        "url": str(meta["url"]),
        "body": str(meta.get("body") or ""),
        "state": str(meta.get("state") or ""),
        "issue_type": _parse_issue_type(meta.get("issueType")),
        "labels": label_names,
        "triage": _triage_from_labels(label_names),
        "author": author_login,
        "comments": comments_out,
    }


def branch_ahead(*, base: str = "main", cwd: Path | None = None) -> dict[str, Any]:
    """True when HEAD has commits not on origin/<base> (fetch first so the tip is fresh)."""
    root = cwd or Path.cwd()
    upstream = f"origin/{base}"
    run_git(["fetch", "origin", base], cwd=root)
    current = run_git(["branch", "--show-current"], cwd=root).stdout.strip()
    ahead = int(run_git(["rev-list", "--count", f"{upstream}..HEAD"], cwd=root).stdout.strip() or "0")
    return {
        "base": base,
        "upstream": upstream,
        "current_branch": current,
        "ahead": ahead,
        "ok": ahead > 0,
    }


def ensure_issue_branch(
    *,
    issue: int,
    slug: str | None = None,
    base: str = "main",
    channel: str | None = None,
    cwd: Path | None = None,
) -> dict[str, Any]:
    """Ensure local `{channel}/issue-<n>-<slug>` exists and is checked out. No commit, push, or PR."""
    root = cwd or Path.cwd()
    if run_git(["status", "--porcelain"], cwd=root).stdout.strip():
        raise RuntimeError("working tree/index must be clean before issue-branch / issue-start")

    ch = normalize_issue_channel(channel)
    viewed = view_issue(issue, cwd=root)
    title = viewed["title"]
    branch = issue_branch_name(issue, slugify(slug) if slug else slugify(title), channel=ch)

    current = run_git(["branch", "--show-current"], cwd=root).stdout.strip()
    created = False
    if current != branch:
        if run_git(["branch", "--list", branch], cwd=root).stdout.strip():
            run_git(["checkout", branch], cwd=root)
        else:
            run_git(["fetch", "origin", base], cwd=root)
            run_git(["checkout", base], cwd=root)
            run_git(["pull", "--ff-only", "origin", base], cwd=root)
            run_git(["checkout", "-b", branch], cwd=root)
            created = True

    ahead_info = branch_ahead(base=base, cwd=root)
    return {
        "issue": {
            "number": viewed["number"],
            "url": viewed["url"],
            "title": title,
            "issue_type": viewed["issue_type"],
        },
        "branch": branch,
        "channel": ch,
        "created": created,
        "base": base,
        "ahead": ahead_info["ahead"],
    }


def issue_start(
    *,
    issue: int,
    slug: str | None = None,
    base: str = "main",
    channel: str | None = None,
    cwd: Path | None = None,
    draft_title: str | None = None,
) -> dict[str, Any]:
    """Push issue branch and open a draft PR — requires commits ahead of base (no empty bootstrap)."""
    root = cwd or Path.cwd()
    ensured = ensure_issue_branch(issue=issue, slug=slug, base=base, channel=channel, cwd=root)
    if int(ensured["ahead"]) == 0:
        raise RuntimeError(f"no commits ahead of {base}; commit real work before issue-start (no empty bootstrap)")

    run_git(["push", "-u", "origin", "HEAD"], cwd=root)

    title = str(ensured["issue"]["title"])
    pr_title = draft_title or title
    body = f"## Summary\n- MVP scope: (fill in)\n\nFixes #{issue}\n"
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as tmp:
        tmp.write(body)
        body_path = tmp.name
    try:
        proc = run_gh(
            [
                "pr",
                "create",
                "--draft",
                "--base",
                base,
                "--title",
                pr_title,
                "--body-file",
                body_path,
            ],
            cwd=root,
        )
    finally:
        Path(body_path).unlink(missing_ok=True)

    pr_url = proc.stdout.strip()
    owner, name = repo_owner_name(cwd=root)
    return {
        "issue": ensured["issue"],
        "branch": ensured["branch"],
        "pr_url": pr_url,
        "repo": f"{owner}/{name}",
        "ahead": ensured["ahead"],
    }
