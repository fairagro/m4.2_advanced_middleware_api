"""Review-open shaping and GitHub write helpers for review replies/resolves."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from m42_ai.gh import GhError, repo_owner_name, run_gh, run_git

AI_AUTHOR_RE = re.compile(r"copilot|bugbot|cursor", re.IGNORECASE)

# GitHub Code Quality review-bot login (PR review threads; distinct from finding dismiss).
CODE_QUALITY_AUTHORS = frozenset({"github-code-quality"})

# Stable marker for first-party `/code-review` COMMENT bodies (often under a human login).
CODE_REVIEW_MARKER = "<!-- m42-ai:code-review -->"

REVIEW_OPEN_QUERY = """
query($owner:String!,$name:String!,$n:Int!) {
  repository(owner:$owner, name:$name) {
    pullRequest(number:$n) {
      url
      number
      reviews(first: 50) {
        nodes { databaseId author { login } submittedAt state body }
      }
      comments(last: 100) {
        nodes { databaseId author { login } createdAt body }
      }
      reviewThreads(first: 100) {
        nodes {
          id
          isResolved
          comments(first: 20) {
            nodes { databaseId author { login } body path originalPosition }
          }
        }
      }
    }
  }
}
"""

RESOLVE_MUTATION = """
mutation($id:ID!) {
  resolveReviewThread(input:{threadId:$id}) {
    thread { id isResolved }
  }
}
"""


def is_code_quality_author(login: str | None) -> bool:
    """True when the login is the GitHub Code Quality PR review bot."""
    if not login:
        return False
    return login.strip().lower() in CODE_QUALITY_AUTHORS


def fetch_code_quality_findings(
    owner: str,
    repo: str,
    *,
    cwd: Path | None = None,
) -> list[dict[str, Any]]:
    """Soft-fail GET of repository Code Quality findings (read-only REST).

    Returns [] on any failure (missing API, auth, network). Never raises for API errors.
    """
    root = cwd or Path.cwd()
    try:
        proc = run_gh(
            [
                "api",
                "-H",
                "Accept: application/vnd.github+json",
                "-H",
                "X-GitHub-Api-Version: 2022-11-28",
                f"/repos/{owner}/{repo}/code-quality/findings",
            ],
            cwd=root,
        )
    except GhError:
        return []
    try:
        data = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError:
        return []
    if isinstance(data, list):
        return [f for f in data if isinstance(f, dict)]
    return []


def _normalize_repo_path(path: str | None) -> str:
    if not path:
        return ""
    return path.strip().lstrip("./").replace("\\", "/")


def _finding_rule_bits(finding: dict[str, Any]) -> tuple[str, str]:
    rule = finding.get("rule") if isinstance(finding.get("rule"), dict) else {}
    rid = str(rule.get("id") or "").strip().lower()
    title = str(rule.get("title") or "").strip().lower()
    return rid, title


def _finding_message_text(finding: dict[str, Any]) -> str:
    msg = finding.get("message")
    if isinstance(msg, dict):
        return str(msg.get("text") or msg.get("markdown") or "").strip().lower()
    return str(msg or "").strip().lower()


def _findings_matching_path(findings: list[dict[str, Any]], norm_path: str) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for finding in findings:
        loc = finding.get("location") if isinstance(finding.get("location"), dict) else {}
        fpath = _normalize_repo_path(str(loc.get("path") or ""))
        if fpath == norm_path:
            matches.append(finding)
    return matches


def _score_finding_against_body(finding: dict[str, Any], body_l: str) -> int:
    """Heuristic score for how well a finding matches a review-comment body."""
    rid, title = _finding_rule_bits(finding)
    msg = _finding_message_text(finding)
    score = 0
    if title and title in body_l:
        score += 3
    if rid and rid in body_l:
        score += 2
    if title:
        heading = title.split()[0]
        if heading and f"## {heading}" in body_l:
            score += 2
        elif title.replace(" ", "") in body_l.replace(" ", ""):
            score += 1
    if msg:
        frag = msg[:40].strip()
        if len(frag) >= 12 and frag in body_l:
            score += 2
        for token in re.findall(r"'([^']+)'|\"([^\"]+)\"|`([^`]+)`", body_l):
            name = next((t for t in token if t), "")
            if name and name in msg:
                score += 2
                break
    return score


def _finding_summary(finding: dict[str, Any]) -> dict[str, Any]:
    rid, _title = _finding_rule_bits(finding)
    out: dict[str, Any] = {
        "number": finding.get("number"),
        "state": finding.get("state"),
    }
    if rid:
        out["rule_id"] = rid
    return out


def _pick_unique_best(
    scored: list[tuple[int, dict[str, Any]]],
    path_matches: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Choose one finding from scored path matches, or None if ambiguous."""
    best_score, best = scored[0]
    if best_score <= 0:
        return path_matches[0] if len(path_matches) == 1 else None
    tied = [f for s, f in scored if s == best_score]
    return best if len(tied) == 1 else None


def correlate_code_quality_finding(
    *,
    path: str | None,
    body: str,
    findings: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Return a single best matching finding summary, or None if none/ambiguous.

    Match order: path agreement required; then prefer rule title in body heading / message
    overlap; if multiple path-only matches remain without a unique rule/message hit → None.
    """
    norm_path = _normalize_repo_path(path)
    if not norm_path or not findings:
        return None

    path_matches = _findings_matching_path(findings, norm_path)
    if not path_matches:
        return None

    body_l = (body or "").lower()
    scored = [(_score_finding_against_body(f, body_l), f) for f in path_matches]
    scored.sort(key=lambda t: t[0], reverse=True)
    chosen = _pick_unique_best(scored, path_matches)
    return _finding_summary(chosen) if chosen is not None else None


def enrich_threads_with_code_quality_findings(
    threads: list[dict[str, Any]],
    findings: list[dict[str, Any]],
) -> None:
    """Mutate CQ-bot threads in place with ``code_quality_finding`` when correlatable."""
    if not findings:
        return
    for thread in threads:
        author = (thread.get("first_comment") or {}).get("author")
        if not is_code_quality_author(author):
            continue
        body = (thread.get("first_comment") or {}).get("body") or ""
        match = correlate_code_quality_finding(
            path=thread.get("path"),
            body=body,
            findings=findings,
        )
        if match is not None:
            thread["code_quality_finding"] = match


def is_ai_author(login: str | None) -> bool:
    if not login:
        return False
    return bool(AI_AUTHOR_RE.search(login))


def is_code_review_report(body: str | None) -> bool:
    """True when a review body was published by the `/code-review` skill."""
    return bool(body) and CODE_REVIEW_MARKER in body


def is_finder_review(review: dict[str, Any]) -> bool:
    """Copilot/Bugbot/Cursor login **or** first-party code-review marker in body."""
    author = (review.get("author") or {}).get("login")
    body = review.get("body") or ""
    return is_ai_author(author) or is_code_review_report(body)


class PrHeadGateError(RuntimeError):
    """Fail-closed PR-head checkout for review-open (structured for agents)."""

    def __init__(
        self,
        message: str,
        *,
        error_code: str,
        head_ref: str | None = None,
        current_branch: str | None = None,
        pr: int | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.head_ref = head_ref
        self.current_branch = current_branch
        self.pr = pr

    def as_json(self) -> dict[str, Any]:
        """Machine-readable gate failure — agents MUST stop (no stash/improvise)."""
        out: dict[str, Any] = {
            "ok": False,
            "pr_head_ok": False,
            "error_code": self.error_code,
            "error": str(self),
            "agent_action": "stop",
        }
        if self.pr is not None:
            out["pr"] = self.pr
        if self.head_ref is not None:
            out["head_ref"] = self.head_ref
        if self.current_branch is not None:
            out["current_branch"] = self.current_branch
        return out


def _md_table_cells(line: str) -> list[str]:
    return [p.strip() for p in line.strip().strip("|").split("|")]


def _find_path_table_header(lines: list[str]) -> tuple[int, list[str]] | None:
    for i, line in enumerate(lines):
        if "|" not in line:
            continue
        parts = [p.lower() for p in _md_table_cells(line)]
        if "path" in parts:
            return i, parts
    return None


def _optional_col(cols: list[str], name: str) -> int | None:
    return cols.index(name) if name in cols else None


def _cell_at(parts: list[str], idx: int | None) -> str:
    if idx is None or idx >= len(parts):
        return ""
    return parts[idx]


def _parse_code_review_table_row(
    line: str,
    *,
    path_i: int,
    goal_i: int | None,
    severity_i: int | None,
    note_i: int | None,
) -> dict[str, str | None] | None:
    if "|" not in line:
        return None
    parts = _md_table_cells(line)
    if not parts or all(set(p) <= set("-: ") for p in parts):
        return None
    if len(parts) <= path_i:
        return None
    path = parts[path_i]
    if not path or path.lower() == "path":
        return None
    bits = [b for b in (_cell_at(parts, goal_i), _cell_at(parts, severity_i), _cell_at(parts, note_i)) if b]
    return {"path": path, "line": None, "text": " — ".join(bits) if bits else path}


_FINDING_START_RE = re.compile(r"^\s*\d+\.\s+")
_PATH_BULLET_RE = re.compile(r"^\s*-\s+\*\*Path:\*\*\s+(.+?)\s*$", re.IGNORECASE)
_FIELD_BULLET_RE = re.compile(
    r"^\s*-\s+\*\*(Severity|Cost|Goal|Note):\*\*\s*(.*)$",
    re.IGNORECASE,
)


def _normalize_code_review_path(raw: str) -> str:
    """Strip backticks and optional `` (`symbol`) `` suffix from a Path bullet value."""
    s = raw.strip()
    tick = re.search(r"`([^`]+)`", s)
    if tick:
        return tick.group(1).strip()
    return re.sub(r"\s*\([^)]*\)\s*$", "", s).strip()


def _extract_code_review_numbered_findings(lines: list[str]) -> list[dict[str, str | None]]:
    """Parse ``N. **Title**`` blocks with ``- **Path:**`` bullets (current skill template)."""
    items: list[dict[str, str | None]] = []
    i = 0
    while i < len(lines):
        if not _FINDING_START_RE.match(lines[i]):
            i += 1
            continue
        block: list[str] = [lines[i]]
        i += 1
        while i < len(lines):
            line = lines[i]
            if _FINDING_START_RE.match(line) or re.match(r"^#{1,6}\s+", line):
                break
            block.append(line)
            i += 1
        path: str | None = None
        goal = ""
        severity = ""
        note = ""
        for bl in block[1:]:
            pm = _PATH_BULLET_RE.match(bl)
            if pm:
                path = _normalize_code_review_path(pm.group(1))
                continue
            fm = _FIELD_BULLET_RE.match(bl)
            if not fm:
                continue
            key = fm.group(1).lower()
            val = fm.group(2).strip()
            if key == "severity":
                severity = val.split("·", maxsplit=1)[0].strip()
                gm = re.search(r"\*\*Goal:\*\*\s*([^·\n]+)", bl, re.IGNORECASE)
                if gm:
                    goal = gm.group(1).strip()
            elif key == "goal":
                goal = val.split("·", maxsplit=1)[0].strip()
            elif key == "note":
                note = val
        if path:
            bits = [b for b in (goal, severity, note) if b]
            items.append({"path": path, "line": None, "text": " — ".join(bits) if bits else path})
    return items


def _extract_code_review_table_findings(lines: list[str]) -> list[dict[str, str | None]]:
    """Legacy Findings index / table-only reports (``path`` header column)."""
    header = _find_path_table_header(lines)
    if header is None:
        return []
    header_idx, cols = header
    path_i = cols.index("path")
    goal_i = _optional_col(cols, "goal")
    severity_i = _optional_col(cols, "severity")
    note_i = _optional_col(cols, "note")

    items: list[dict[str, str | None]] = []
    for line in lines[header_idx + 1 :]:
        if "|" not in line:
            if items:
                break
            continue
        row = _parse_code_review_table_row(line, path_i=path_i, goal_i=goal_i, severity_i=severity_i, note_i=note_i)
        if row is not None:
            items.append(row)
    return items


def extract_code_review_findings(body: str) -> list[dict[str, str | None]]:
    """Parse numbered Path findings from a marked `/code-review` report (legacy table fallback)."""
    if not is_code_review_report(body):
        return []
    lines = body.splitlines()
    numbered = _extract_code_review_numbered_findings(lines)
    if numbered:
        return numbered
    return _extract_code_review_table_findings(lines)


def extract_summary_findings(body: str) -> list[dict[str, str | None]]:
    """Suppressed Copilot packing **or** code-review numbered/table findings."""
    if is_code_review_report(body):
        return extract_code_review_findings(body)
    return extract_suppressed_comments(body)


def extract_suppressed_comments(body: str) -> list[dict[str, str | None]]:
    """Extract summary-only / suppressed findings from a review body.

    Copilot often uses ``**path:line**`` then a ``*`` bullet (no thread). Older fixtures use plain ``-`` lists
    under a ``Suppressed comments`` heading. Do **not** treat the whole-review title
    ``Needs a closer look`` as the suppressed section — that would swallow the intro.
    """
    if not body:
        return []
    lines = body.splitlines()
    collecting = False
    items: list[dict[str, str | None]] = []
    heading_re = re.compile(r"suppressed\s+comments", re.IGNORECASE)
    path_re = re.compile(r"^\s*\*\*(.+?)(?::(\d+))?\*\*\s*$")
    bullet_re = re.compile(r"^\s*(?:[-*]|\d+\.)\s+")
    pending_path: str | None = None
    pending_line: str | None = None

    for line in lines:
        if heading_re.search(line):
            collecting = True
            pending_path = None
            pending_line = None
            continue
        if not collecting:
            continue
        if re.match(r"^#{1,6}\s+", line) and not heading_re.search(line):
            break
        path_m = path_re.match(line)
        if path_m:
            pending_path = path_m.group(1).strip()
            pending_line = path_m.group(2)
            continue
        if bullet_re.match(line):
            text = bullet_re.sub("", line).strip()
            # After Copilot path+bullet pairs, footer bullets like "- **Files reviewed:**" appear
            # without a preceding **path** line — stop rather than treating them as findings.
            if pending_path is None and any(i.get("path") for i in items):
                break
            items.append({"path": pending_path, "line": pending_line, "text": text})
            pending_path = None
            pending_line = None
            continue
        if line.strip() == "":
            continue
        if items and not line.startswith((" ", "\t", "*")):
            break
    return items


TRIAGE_REPLY_RE = re.compile(r"(?is)^\s*(Fixed in |Dismissed\.|Follow-up:)")


def is_triage_reply_body(body: str | None) -> bool:
    """True for review-fixer conversation / review replies (cannot resolve suppressed)."""
    if not body:
        return False
    return bool(TRIAGE_REPLY_RE.match(body.strip()))


def _event_time(node: dict[str, Any], *keys: str) -> str:
    for key in keys:
        val = node.get(key)
        if val:
            return str(val)
    return ""


def is_submitted_review(review: dict[str, Any]) -> bool:
    """True when GitHub has a real submission time (excludes PENDING / unsubmitted drafts)."""
    if not review.get("submittedAt"):
        return False
    state = (review.get("state") or "").upper()
    return state != "PENDING"


def answered_suppressed_review_ids(
    suppressed_reviews: list[dict[str, Any]],
    *,
    issue_comments: list[dict[str, Any]],
    all_reviews: list[dict[str, Any]],
) -> set[int]:
    """Mark suppressed AI reviews closed when a triage reply appears after them.

    Suppressed Copilot findings have no resolve button. A later PR conversation comment or
    non-AI review body that looks like Fixed/Dismissed/Follow-up closes the most recent still-open
    suppressed review (or one explicitly named via ``pullrequestreview-<id>``).
    """
    answered: set[int] = set()
    if not suppressed_reviews:
        return answered

    by_id = {int(r["databaseId"]): r for r in suppressed_reviews if r.get("databaseId") is not None}

    replies: list[tuple[str, str]] = []
    for c in issue_comments:
        body = c.get("body") or ""
        if not is_triage_reply_body(body) and "pullrequestreview-" not in body:
            continue
        replies.append((_event_time(c, "createdAt"), body))
    for r in all_reviews:
        if not is_submitted_review(r):
            continue
        author = (r.get("author") or {}).get("login")
        body = r.get("body") or ""
        # Skip finders (bot logins and first-party code-review reports) — they are not triage replies.
        if is_ai_author(author) or is_code_review_report(body):
            continue
        if not is_triage_reply_body(body) and "pullrequestreview-" not in body:
            continue
        replies.append((_event_time(r, "submittedAt"), body))
    replies.sort(key=lambda t: t[0])

    ordered = sorted(
        suppressed_reviews,
        key=lambda r: (_event_time(r, "submittedAt"), r.get("databaseId") or 0),
    )

    for at, body in replies:
        explicit = re.search(r"pullrequestreview-(\d+)", body)
        if explicit:
            rid = int(explicit.group(1))
            if rid in by_id:
                answered.add(rid)
            continue
        if not is_triage_reply_body(body):
            continue
        candidates = [
            r for r in ordered if int(r["databaseId"]) not in answered and _event_time(r, "submittedAt") <= at
        ]
        if candidates:
            answered.add(int(candidates[-1]["databaseId"]))
    return answered


def shape_review_open(
    payload: dict[str, Any],
    *,
    review_id: int | None = None,
    code_quality_findings: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Turn raw GraphQL into agent-facing open-work JSON (no policy decisions)."""
    repo = (payload.get("data") or {}).get("repository") or {}
    pr = repo.get("pullRequest")
    if pr is None:
        raise RuntimeError("pullRequest is null in GraphQL response (wrong number or no access)")

    threads_out: list[dict[str, Any]] = []
    for thread in pr["reviewThreads"]["nodes"]:
        if thread.get("isResolved"):
            continue
        comments = thread.get("comments", {}).get("nodes") or []
        if not comments:
            continue
        first = comments[0]
        author = (first.get("author") or {}).get("login")
        # Include every unresolved thread (any author). AI-author heuristics apply only to
        # review bodies / suppressed summary packing below — not to thread filtering.
        threads_out.append({
            "thread_id": thread["id"],
            "is_resolved": False,
            "path": first.get("path"),
            "first_comment": {
                "database_id": first.get("databaseId"),
                "author": author,
                "body": first.get("body") or "",
                "original_position": first.get("originalPosition"),
            },
            "comment_count": len(comments),
        })

    if code_quality_findings:
        enrich_threads_with_code_quality_findings(threads_out, code_quality_findings)

    all_reviews = list(pr["reviews"]["nodes"])
    # Finder reviews: bot AI authors and/or `/code-review` marker (often human login).
    all_ai = [r for r in all_reviews if is_finder_review(r) and is_submitted_review(r)]
    all_ai.sort(key=lambda r: (_event_time(r, "submittedAt"), r.get("databaseId") or 0))

    issue_comments = list((pr.get("comments") or {}).get("nodes") or [])

    summary_sources = [r for r in all_ai if extract_summary_findings(r.get("body") or "")]
    answered_ids = answered_suppressed_review_ids(
        summary_sources,
        issue_comments=issue_comments,
        all_reviews=all_reviews,
    )

    # Open summary work: at most the latest unanswered finder summary review.
    open_suppressed_id: int | None = None
    for r in summary_sources:
        rid = int(r["databaseId"])
        if rid not in answered_ids:
            open_suppressed_id = rid
    # Permalink triage: force that review's summary findings into the open set.
    if review_id is not None:
        open_suppressed_id = review_id

    scoped_ai = [r for r in all_ai if r.get("databaseId") == review_id] if review_id is not None else all_ai

    reviews_out: list[dict[str, Any]] = []
    summary_only: list[dict[str, Any]] = []
    for rev in scoped_ai:
        body = rev.get("body") or ""
        suppressed = extract_summary_findings(body)
        rid = rev.get("databaseId")
        rid_int = int(rid) if rid is not None else None
        answered = rid_int in answered_ids if rid_int is not None else False
        summary_open = bool(suppressed) and rid_int == open_suppressed_id
        entry = {
            "database_id": rid,
            "author": (rev.get("author") or {}).get("login"),
            "submitted_at": rev.get("submittedAt"),
            "state": rev.get("state"),
            "body": body,
            "suppressed_comments": suppressed,
            "summary_answered": answered,
            "summary_open": summary_open,
            "is_code_review": is_code_review_report(body),
        }
        reviews_out.append(entry)
        if not summary_open:
            continue
        for item in suppressed:
            summary_only.append({
                "review_database_id": rid,
                "author": entry["author"],
                "path": item.get("path"),
                "line": item.get("line"),
                "text": item.get("text") or "",
                "resolvable": False,
            })

    latest = reviews_out[-1] if reviews_out else None
    return {
        "pr": {"number": pr.get("number"), "url": pr.get("url")},
        "round_count": len(all_ai),
        "unresolved_ai_threads": threads_out,
        "ai_reviews": reviews_out,
        "summary_only_findings": summary_only,
        "open_summary_review_id": open_suppressed_id if summary_only else None,
        "latest_ai_review": latest,
        "open_work_empty": len(threads_out) == 0 and len(summary_only) == 0,
    }


def ensure_pr_head(
    pr: int,
    *,
    owner: str | None = None,
    repo: str | None = None,
    cwd: Path | None = None,
) -> dict[str, Any]:
    """Resolve PR head ref and ensure local checkout matches it.

    Dirty working tree/index on a *different* branch refuses checkout. Dirty on the
    PR head is allowed. Fail closed when checkout cannot establish the head branch.
    Raises PrHeadGateError with a stable error_code for CLI JSON.
    """
    root = cwd or Path.cwd()
    view_args = ["pr", "view", str(pr), "--json", "headRefName"]
    if owner and repo:
        view_args.extend(["--repo", f"{owner}/{repo}"])
    meta = json.loads(run_gh(view_args, cwd=root).stdout)
    head_ref = str(meta.get("headRefName") or "").strip()
    if not head_ref:
        raise PrHeadGateError(
            f"PR #{pr} has empty headRefName",
            error_code="empty_head_ref",
            pr=pr,
        )

    current = run_git(["branch", "--show-current"], cwd=root).stdout.strip()
    dirty = bool(run_git(["status", "--porcelain"], cwd=root).stdout.strip())

    if current == head_ref:
        return {
            "head_ref": head_ref,
            "current_branch": current,
            "checked_out": False,
            "pr_head_ok": True,
        }

    if dirty:
        raise PrHeadGateError(
            f"working tree/index dirty on branch {current!r}; refuse checkout of PR #{pr} head {head_ref!r}",
            error_code="dirty_wrong_branch",
            head_ref=head_ref,
            current_branch=current,
            pr=pr,
        )

    checkout_args = ["pr", "checkout", str(pr)]
    if owner and repo:
        checkout_args.extend(["--repo", f"{owner}/{repo}"])
    try:
        run_gh(checkout_args, cwd=root)
    except GhError as exc:
        raise PrHeadGateError(
            f"failed to checkout PR #{pr} head {head_ref!r}: {exc}",
            error_code="checkout_failed",
            head_ref=head_ref,
            current_branch=current,
            pr=pr,
        ) from exc

    current = run_git(["branch", "--show-current"], cwd=root).stdout.strip()
    if current != head_ref:
        raise PrHeadGateError(
            f"after checkout expected branch {head_ref!r}, got {current!r}",
            error_code="checkout_branch_mismatch",
            head_ref=head_ref,
            current_branch=current,
            pr=pr,
        )

    return {
        "head_ref": head_ref,
        "current_branch": current,
        "checked_out": True,
        "pr_head_ok": True,
    }


def fetch_review_open(
    pr: int,
    *,
    owner: str | None = None,
    repo: str | None = None,
    review_id: int | None = None,
    cwd: Path | None = None,
    ensure_checkout: bool = True,
) -> dict[str, Any]:
    root = cwd or Path.cwd()
    if owner is None or repo is None:
        owner, repo = repo_owner_name(cwd=root)

    head_info: dict[str, Any] | None = None
    if ensure_checkout:
        head_info = ensure_pr_head(pr, owner=owner, repo=repo, cwd=root)

    proc = run_gh(
        [
            "api",
            "graphql",
            "-f",
            f"query={REVIEW_OPEN_QUERY}",
            "-F",
            f"owner={owner}",
            "-F",
            f"name={repo}",
            "-F",
            f"n={pr}",
        ],
        cwd=root,
    )
    payload = json.loads(proc.stdout)
    if payload.get("errors"):
        raise RuntimeError(f"GraphQL errors: {payload['errors']}")
    findings = fetch_code_quality_findings(owner, repo, cwd=root)
    try:
        shaped = shape_review_open(
            payload,
            review_id=review_id,
            code_quality_findings=findings or None,
        )
    except RuntimeError:
        raise RuntimeError(f"pullRequest is null for {owner}/{repo}#{pr} (wrong number or no access)") from None
    if head_info is not None:
        shaped["head_ref"] = head_info["head_ref"]
        shaped["current_branch"] = head_info["current_branch"]
        shaped["pr_head_ok"] = True
        shaped["ok"] = True
    return shaped


def review_reply(
    *,
    pr: int,
    body: str,
    in_reply_to: int | None = None,
    conversation: bool = False,
    owner: str | None = None,
    repo: str | None = None,
) -> dict[str, Any]:
    if owner is None or repo is None:
        owner, repo = repo_owner_name()
    if conversation:
        if in_reply_to is not None:
            raise ValueError("use either --conversation or --in-reply-to, not both")
        payload = json.dumps({"body": body})
        proc = run_gh(
            [
                "api",
                "-X",
                "POST",
                f"repos/{owner}/{repo}/issues/{pr}/comments",
                "--input",
                "-",
            ],
            input_text=payload,
        )
    else:
        if in_reply_to is None:
            raise ValueError("--in-reply-to is required unless --conversation")
        payload = json.dumps({"body": body, "in_reply_to": in_reply_to})
        proc = run_gh(
            [
                "api",
                "-X",
                "POST",
                f"repos/{owner}/{repo}/pulls/{pr}/comments",
                "--input",
                "-",
            ],
            input_text=payload,
        )
    return json.loads(proc.stdout)


def review_resolve(thread_id: str) -> dict[str, Any]:
    proc = run_gh([
        "api",
        "graphql",
        "-f",
        f"query={RESOLVE_MUTATION}",
        "-F",
        f"id={thread_id}",
    ])
    payload = json.loads(proc.stdout)
    if payload.get("errors"):
        raise RuntimeError(f"GraphQL errors: {payload['errors']}")
    return payload["data"]["resolveReviewThread"]["thread"]
