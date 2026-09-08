"""Review-open shaping and GitHub write helpers for review replies/resolves."""

from __future__ import annotations

import json
import re
from typing import Any

from m42_ai.gh import repo_owner_name, run_gh

AI_AUTHOR_RE = re.compile(r"copilot|bugbot|cursor", re.I)

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


def is_ai_author(login: str | None) -> bool:
    if not login:
        return False
    return bool(AI_AUTHOR_RE.search(login))


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
    heading_re = re.compile(r"suppressed\s+comments", re.I)
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
        author = (r.get("author") or {}).get("login")
        if is_ai_author(author):
            continue
        body = r.get("body") or ""
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
        if not is_ai_author(author):
            continue
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

    all_reviews = list(pr["reviews"]["nodes"])
    all_ai = [
        r
        for r in all_reviews
        if r.get("author") and is_ai_author((r["author"] or {}).get("login")) and is_submitted_review(r)
    ]
    all_ai.sort(key=lambda r: (_event_time(r, "submittedAt"), r.get("databaseId") or 0))

    issue_comments = list((pr.get("comments") or {}).get("nodes") or [])

    suppressed_ai = [r for r in all_ai if extract_suppressed_comments(r.get("body") or "")]
    answered_ids = answered_suppressed_review_ids(
        suppressed_ai,
        issue_comments=issue_comments,
        all_reviews=all_reviews,
    )

    # Open summary work: at most the latest unanswered suppressed AI review.
    open_suppressed_id: int | None = None
    for r in suppressed_ai:
        rid = int(r["databaseId"])
        if rid not in answered_ids:
            open_suppressed_id = rid
    # Permalink triage: force that review's suppressed into the open set.
    if review_id is not None:
        open_suppressed_id = review_id

    scoped_ai = [r for r in all_ai if r.get("databaseId") == review_id] if review_id is not None else all_ai

    reviews_out: list[dict[str, Any]] = []
    summary_only: list[dict[str, Any]] = []
    for rev in scoped_ai:
        body = rev.get("body") or ""
        suppressed = extract_suppressed_comments(body)
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


def fetch_review_open(
    pr: int,
    *,
    owner: str | None = None,
    repo: str | None = None,
    review_id: int | None = None,
) -> dict[str, Any]:
    if owner is None or repo is None:
        owner, repo = repo_owner_name()
    proc = run_gh([
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
    ])
    payload = json.loads(proc.stdout)
    if payload.get("errors"):
        raise RuntimeError(f"GraphQL errors: {payload['errors']}")
    try:
        return shape_review_open(payload, review_id=review_id)
    except RuntimeError:
        raise RuntimeError(f"pullRequest is null for {owner}/{repo}#{pr} (wrong number or no access)") from None


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
