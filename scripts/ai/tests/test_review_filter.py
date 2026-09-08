from __future__ import annotations

import json
from pathlib import Path

import pytest
from m42_ai.issue import slugify
from m42_ai.review import extract_suppressed_comments, is_ai_author, is_submitted_review, shape_review_open

FIXTURE = Path(__file__).parent / "fixtures" / "review_pr.json"

COPILOT_SUPPRESSED_BODY = """### 🔵 Needs a closer look

Intro text.

<details>
<summary>Review details</summary>

### Suppressed comments (2)

**Previously missed (2)** — in code that hasn't changed since the last review.

**scripts/ai/src/m42_ai/issue.py:161**
* `issue_start()` uses the user-provided `slug` verbatim.
**scripts/ai/src/m42_ai/review.py:154**
* `fetch_review_open()` assumes pullRequest is always present.

- **Files reviewed:** 29/34
</details>
"""


def _payload() -> dict:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    data["data"]["repository"]["pullRequest"].setdefault("comments", {"nodes": []})
    return data


def test_is_ai_author() -> None:
    assert is_ai_author("copilot-pull-request-reviewer")
    assert is_ai_author("cursor[bot]")
    assert is_ai_author("Bugbot")
    assert not is_ai_author("alice")
    assert not is_ai_author(None)


def test_is_submitted_review() -> None:
    assert is_submitted_review({"submittedAt": "2026-09-04T12:00:00Z", "state": "COMMENTED"})
    assert not is_submitted_review({"submittedAt": None, "state": "PENDING"})
    assert not is_submitted_review({"submittedAt": "2026-09-04T12:00:00Z", "state": "PENDING"})
    assert not is_submitted_review({"state": "COMMENTED"})


def test_shape_ignores_pending_ai_reviews() -> None:
    payload = _payload()
    nodes = payload["data"]["repository"]["pullRequest"]["reviews"]["nodes"]
    before = shape_review_open(payload)["round_count"]
    nodes.append({
        "databaseId": 999,
        "author": {"login": "copilot-pull-request-reviewer"},
        "submittedAt": None,
        "state": "PENDING",
        "body": "## Suppressed comments\n\n- phantom",
    })
    shaped = shape_review_open(payload)
    assert shaped["round_count"] == before
    assert all(r["database_id"] != 999 for r in shaped["ai_reviews"])


def test_extract_suppressed_comments() -> None:
    body = "## Suppressed comments\n\n- One\n- Two\n\n## Next\n\n- ignore"
    assert extract_suppressed_comments(body) == [
        {"path": None, "line": None, "text": "One"},
        {"path": None, "line": None, "text": "Two"},
    ]


def test_extract_copilot_path_bullet_suppressed() -> None:
    items = extract_suppressed_comments(COPILOT_SUPPRESSED_BODY)
    assert len(items) == 2
    assert items[0]["path"] == "scripts/ai/src/m42_ai/issue.py"
    assert items[0]["line"] == "161"
    assert "slug" in (items[0]["text"] or "")
    assert items[1]["path"] == "scripts/ai/src/m42_ai/review.py"


def test_shape_review_open_filters_resolved_and_human() -> None:
    shaped = shape_review_open(_payload())
    assert shaped["pr"]["number"] == 22
    assert shaped["round_count"] == 2
    assert len(shaped["unresolved_ai_threads"]) == 1
    thread = shaped["unresolved_ai_threads"][0]
    assert thread["thread_id"] == "PRRT_open_ai"
    assert thread["first_comment"]["database_id"] == 200
    assert shaped["latest_ai_review"]["author"] == "cursor"
    assert shaped["summary_only_findings"]  # open Copilot suppressed from fixture
    assert shaped["open_work_empty"] is False


def test_shape_keeps_suppressed_when_later_cursor_review_has_none() -> None:
    payload = _payload()
    nodes = payload["data"]["repository"]["pullRequest"]["reviews"]["nodes"]
    for n in nodes:
        if n["author"]["login"] == "cursor":
            n["submittedAt"] = "2026-09-04T23:00:00Z"
            n["body"] = "Bugbot found 1 issue."
        if "copilot" in n["author"]["login"]:
            n["body"] = COPILOT_SUPPRESSED_BODY
    shaped = shape_review_open(payload)
    assert shaped["latest_ai_review"]["author"] == "cursor"
    assert shaped["open_summary_review_id"] == 2
    assert len(shaped["summary_only_findings"]) == 2
    assert shaped["summary_only_findings"][0]["resolvable"] is False


def test_older_suppressed_closed_by_explicit_review_link() -> None:
    payload = _payload()
    nodes = payload["data"]["repository"]["pullRequest"]["reviews"]["nodes"]
    nodes[1]["body"] = COPILOT_SUPPRESSED_BODY
    nodes[1]["submittedAt"] = "2026-09-02T10:00:00Z"
    nodes.append({
        "databaseId": 99,
        "author": {"login": "copilot-pull-request-reviewer"},
        "submittedAt": "2026-09-04T12:00:00Z",
        "state": "COMMENTED",
        "body": COPILOT_SUPPRESSED_BODY,
    })
    payload["data"]["repository"]["pullRequest"]["comments"] = {
        "nodes": [
            {
                "databaseId": 1,
                "author": {"login": "alice"},
                "createdAt": "2026-09-03T10:00:00Z",
                "body": "Fixed in abc.\n#pullrequestreview-2",
            }
        ]
    }
    shaped = shape_review_open(payload)
    assert shaped["open_summary_review_id"] == 99
    assert all(f["review_database_id"] == 99 for f in shaped["summary_only_findings"])


def test_triage_reply_without_id_closes_prior_suppressed() -> None:
    payload = _payload()
    nodes = payload["data"]["repository"]["pullRequest"]["reviews"]["nodes"]
    for n in nodes:
        if n["databaseId"] == 2:
            n["body"] = COPILOT_SUPPRESSED_BODY
            n["submittedAt"] = "2026-09-02T10:00:00Z"
    payload["data"]["repository"]["pullRequest"]["comments"] = {
        "nodes": [
            {
                "databaseId": 1,
                "author": {"login": "alice"},
                "createdAt": "2026-09-03T10:00:00Z",
                "body": "Fixed in abcdef.\nSuppressed notes addressed.",
            }
        ]
    }
    shaped = shape_review_open(payload)
    assert shaped["summary_only_findings"] == []
    assert shaped["open_summary_review_id"] is None
    rev2 = next(r for r in shaped["ai_reviews"] if r["database_id"] == 2)
    assert rev2["summary_answered"] is True
    assert rev2["summary_open"] is False


def test_shape_review_id_scopes_summary_bodies() -> None:
    payload = _payload()
    nodes = payload["data"]["repository"]["pullRequest"]["reviews"]["nodes"]
    for n in nodes:
        if n["databaseId"] == 2:
            n["body"] = COPILOT_SUPPRESSED_BODY
    shaped = shape_review_open(payload, review_id=2)
    assert len(shaped["ai_reviews"]) == 1
    assert shaped["ai_reviews"][0]["database_id"] == 2
    assert len(shaped["summary_only_findings"]) == 2


def test_shape_null_pull_request_raises() -> None:
    with pytest.raises(RuntimeError, match="null"):
        shape_review_open({"data": {"repository": {"pullRequest": None}}})


def test_slugify() -> None:
    assert slugify("CLI for agent GitHub/git plumbing!") == "cli-for-agent-github-git-plumbing"
    assert slugify("bad .. slug~name") == "bad-slug-name"
