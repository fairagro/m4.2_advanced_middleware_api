from __future__ import annotations

import json
from pathlib import Path

import pytest
from m42_ai import review as review_mod
from m42_ai.gh import GhError
from m42_ai.issue import slugify
from m42_ai.review import (
    CODE_REVIEW_MARKER,
    correlate_code_quality_finding,
    extract_code_review_findings,
    extract_suppressed_comments,
    is_ai_author,
    is_code_review_report,
    is_submitted_review,
    shape_review_open,
)

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

CODE_REVIEW_BODY = f"""{CODE_REVIEW_MARKER}
## Verdict

One High correctness gap.

| path | goal | severity | cost | note |
|------|------|----------|------|------|
| scripts/ai/src/m42_ai/review.py | Correctness | High | S | Null pullRequest not handled |
| docs/ci.md | Docs | Low | XS | Stale workflow name |
"""

CODE_REVIEW_DUAL_BODY = f"""{CODE_REVIEW_MARKER}
## Verdict

One High correctness gap; one Low docs nit.

1. **Null PR head not handled**
   - **Severity:** High · **Cost:** S · **Goal:** Correctness
   - **Path:** `scripts/ai/src/m42_ai/review.py` (`fetch_review_open`)
   - **Note:** GraphQL null pullRequest can crash shaping.
2. **Stale workflow name in docs**
   - **Severity:** Low · **Cost:** XS · **Goal:** Docs
   - **Path:** `docs/ci.md`
   - **Note:** Section still names a removed workflow.

## Findings index

| path | goal | severity | cost | note |
|------|------|----------|------|------|
| scripts/ai/src/m42_ai/review.py | Correctness | High | S | Null pullRequest not handled |
| docs/ci.md | Docs | Low | XS | Stale workflow name |
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


def test_pending_human_draft_does_not_answer_suppressed() -> None:
    """PENDING viewer drafts must not close suppressed Copilot findings (issue #53)."""
    payload = _payload()
    nodes = payload["data"]["repository"]["pullRequest"]["reviews"]["nodes"]
    for n in nodes:
        if n["databaseId"] == 2:
            n["body"] = COPILOT_SUPPRESSED_BODY
            n["submittedAt"] = "2026-09-02T10:00:00Z"
            n["state"] = "COMMENTED"
    nodes.append({
        "databaseId": 500,
        "author": {"login": "alice"},
        "submittedAt": None,
        "state": "PENDING",
        "body": "Dismissed. draft only — not submitted.\n#pullrequestreview-2",
    })
    shaped = shape_review_open(payload)
    assert shaped["open_summary_review_id"] == 2
    assert len(shaped["summary_only_findings"]) == 2
    rev2 = next(r for r in shaped["ai_reviews"] if r["database_id"] == 2)
    assert rev2["summary_answered"] is False


def test_submitted_human_review_body_still_answers_suppressed() -> None:
    payload = _payload()
    nodes = payload["data"]["repository"]["pullRequest"]["reviews"]["nodes"]
    for n in nodes:
        if n["databaseId"] == 2:
            n["body"] = COPILOT_SUPPRESSED_BODY
            n["submittedAt"] = "2026-09-02T10:00:00Z"
            n["state"] = "COMMENTED"
    nodes.append({
        "databaseId": 501,
        "author": {"login": "alice"},
        "submittedAt": "2026-09-03T10:00:00Z",
        "state": "COMMENTED",
        "body": "Dismissed. real submission.\n#pullrequestreview-2",
    })
    shaped = shape_review_open(payload)
    assert shaped["open_summary_review_id"] is None
    assert not shaped["summary_only_findings"]
    rev2 = next(r for r in shaped["ai_reviews"] if r["database_id"] == 2)
    assert rev2["summary_answered"] is True


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


def test_is_code_review_report() -> None:
    assert is_code_review_report(CODE_REVIEW_BODY)
    assert not is_code_review_report(COPILOT_SUPPRESSED_BODY)
    assert not is_code_review_report(None)


def test_extract_code_review_findings() -> None:
    items = extract_code_review_findings(CODE_REVIEW_BODY)
    assert len(items) == 2
    assert items[0]["path"] == "scripts/ai/src/m42_ai/review.py"
    assert "High" in (items[0]["text"] or "")
    assert "Null pullRequest" in (items[0]["text"] or "")
    assert items[1]["path"] == "docs/ci.md"


def test_extract_code_review_findings_dual_layout() -> None:
    """Numbered blocks + Findings index table: extract from the table (legacy table-only still works)."""
    items = extract_code_review_findings(CODE_REVIEW_DUAL_BODY)
    assert len(items) == 2
    assert items[0]["path"] == "scripts/ai/src/m42_ai/review.py"
    assert "High" in (items[0]["text"] or "")
    assert items[1]["path"] == "docs/ci.md"
    # Dual and legacy table-only bodies must yield the same paths for review-fixer.
    legacy = extract_code_review_findings(CODE_REVIEW_BODY)
    assert [i["path"] for i in items] == [i["path"] for i in legacy]


def test_shape_includes_human_code_review_summary() -> None:
    """Human-login `/code-review` COMMENT body must land in summary_only_findings."""
    payload = _payload()
    pr = payload["data"]["repository"]["pullRequest"]
    # Clear bot reviews so only the code-review finder remains for summary packing.
    pr["reviews"]["nodes"] = [
        {
            "databaseId": 700,
            "author": {"login": "alice"},
            "submittedAt": "2026-09-05T12:00:00Z",
            "state": "COMMENTED",
            "body": CODE_REVIEW_BODY,
        }
    ]
    shaped = shape_review_open(payload)
    assert shaped["round_count"] == 1
    assert shaped["ai_reviews"][0]["is_code_review"] is True
    assert shaped["open_summary_review_id"] == 700
    assert len(shaped["summary_only_findings"]) == 2
    assert shaped["summary_only_findings"][0]["resolvable"] is False
    assert shaped["summary_only_findings"][0]["path"] == "scripts/ai/src/m42_ai/review.py"


def test_code_review_report_does_not_answer_suppressed() -> None:
    """A later code-review COMMENT must not close prior Copilot suppressed findings."""
    payload = _payload()
    nodes = payload["data"]["repository"]["pullRequest"]["reviews"]["nodes"]
    for n in nodes:
        if n["databaseId"] == 2:
            n["body"] = COPILOT_SUPPRESSED_BODY
            n["submittedAt"] = "2026-09-02T10:00:00Z"
            n["state"] = "COMMENTED"
    nodes.append({
        "databaseId": 701,
        "author": {"login": "alice"},
        "submittedAt": "2026-09-03T10:00:00Z",
        "state": "COMMENTED",
        "body": CODE_REVIEW_BODY,
    })
    shaped = shape_review_open(payload)
    # Latest unanswered summary source is the code-review (after Copilot).
    assert shaped["open_summary_review_id"] == 701
    assert all(f["review_database_id"] == 701 for f in shaped["summary_only_findings"])
    rev2 = next(r for r in shaped["ai_reviews"] if r["database_id"] == 2)
    assert rev2["summary_answered"] is False


def test_triage_reply_answers_code_review_summary() -> None:
    payload = _payload()
    pr = payload["data"]["repository"]["pullRequest"]
    pr["reviews"]["nodes"] = [
        {
            "databaseId": 700,
            "author": {"login": "alice"},
            "submittedAt": "2026-09-05T12:00:00Z",
            "state": "COMMENTED",
            "body": CODE_REVIEW_BODY,
        },
        {
            "databaseId": 702,
            "author": {"login": "bob"},
            "submittedAt": "2026-09-06T12:00:00Z",
            "state": "COMMENTED",
            "body": "Dismissed.\n#pullrequestreview-700",
        },
    ]
    shaped = shape_review_open(payload)
    assert not shaped["summary_only_findings"]
    assert shaped["open_summary_review_id"] is None
    rev = next(r for r in shaped["ai_reviews"] if r["database_id"] == 700)
    assert rev["summary_answered"] is True


def test_shape_review_open_includes_human_and_ai_threads() -> None:
    shaped = shape_review_open(_payload())
    assert shaped["pr"]["number"] == 22
    assert shaped["round_count"] == 2
    thread_ids = {t["thread_id"] for t in shaped["unresolved_ai_threads"]}
    assert thread_ids == {"PRRT_open_ai", "PRRT_open_human"}
    assert "PRRT_resolved" not in thread_ids
    human = next(t for t in shaped["unresolved_ai_threads"] if t["thread_id"] == "PRRT_open_human")
    assert human["first_comment"]["author"] == "alice"
    assert shaped["latest_ai_review"] is not None
    assert shaped["ai_reviews"][-1]["author"] == "cursor"
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
    assert shaped["latest_ai_review"] is not None
    assert shaped["ai_reviews"][-1]["author"] == "cursor"
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
    assert not shaped["summary_only_findings"]
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


def test_latest_ai_review_null_when_no_submitted_ai() -> None:
    """Empty submitted AI reviews → JSON null, not {} (issue #96)."""
    payload = _payload()
    pr = payload["data"]["repository"]["pullRequest"]
    pr["reviews"]["nodes"] = [
        n for n in pr["reviews"]["nodes"] if not is_ai_author((n.get("author") or {}).get("login"))
    ]
    pr["reviewThreads"]["nodes"] = []
    shaped = shape_review_open(payload)
    assert not shaped["ai_reviews"]
    assert shaped["latest_ai_review"] is None
    assert shaped["round_count"] == 0


def test_slugify() -> None:
    assert slugify("CLI for agent GitHub/git plumbing!") == "cli-for-agent-github-git-plumbing"
    assert slugify("bad .. slug~name") == "bad-slug-name"


def test_shape_attaches_code_quality_finding() -> None:
    payload = {
        "data": {
            "repository": {
                "pullRequest": {
                    "number": 1,
                    "url": "https://example.test/pr/1",
                    "reviews": {"nodes": []},
                    "comments": {"nodes": []},
                    "reviewThreads": {
                        "nodes": [
                            {
                                "id": "TH_CQ",
                                "isResolved": False,
                                "comments": {
                                    "nodes": [
                                        {
                                            "databaseId": 1,
                                            "author": {"login": "github-code-quality"},
                                            "body": "## Unused import\n\nImport of 'owslib' is not used.",
                                            "path": "middleware/inspire/src/middleware/inspire/xml_hardening.py",
                                            "originalPosition": 1,
                                        }
                                    ]
                                },
                            },
                            {
                                "id": "TH_HUMAN",
                                "isResolved": False,
                                "comments": {
                                    "nodes": [
                                        {
                                            "databaseId": 2,
                                            "author": {"login": "alice"},
                                            "body": "nit",
                                            "path": "middleware/inspire/src/middleware/inspire/xml_hardening.py",
                                            "originalPosition": 2,
                                        }
                                    ]
                                },
                            },
                        ]
                    },
                }
            }
        }
    }
    findings = [
        {
            "number": 23,
            "state": "open",
            "rule": {"id": "py/unused-import", "title": "Unused import"},
            "location": {
                "path": "middleware/inspire/src/middleware/inspire/xml_hardening.py",
                "start_line": 21,
            },
            "message": {"text": "Import of 'owslib' is not used."},
        }
    ]
    shaped = shape_review_open(payload, code_quality_findings=findings)
    cq = next(t for t in shaped["unresolved_ai_threads"] if t["thread_id"] == "TH_CQ")
    human = next(t for t in shaped["unresolved_ai_threads"] if t["thread_id"] == "TH_HUMAN")
    assert cq["code_quality_finding"] == {
        "number": 23,
        "state": "open",
        "rule_id": "py/unused-import",
    }
    assert "code_quality_finding" not in human


def test_shape_omits_enrichment_when_findings_empty() -> None:
    payload = {
        "data": {
            "repository": {
                "pullRequest": {
                    "number": 1,
                    "url": "https://example.test/pr/1",
                    "reviews": {"nodes": []},
                    "comments": {"nodes": []},
                    "reviewThreads": {
                        "nodes": [
                            {
                                "id": "TH_CQ",
                                "isResolved": False,
                                "comments": {
                                    "nodes": [
                                        {
                                            "databaseId": 1,
                                            "author": {"login": "github-code-quality"},
                                            "body": "## Unused import\n",
                                            "path": "a.py",
                                            "originalPosition": 1,
                                        }
                                    ]
                                },
                            }
                        ]
                    },
                }
            }
        }
    }
    shaped = shape_review_open(payload, code_quality_findings=[])
    assert "code_quality_finding" not in shaped["unresolved_ai_threads"][0]


def test_correlate_ambiguous_path_only_returns_none() -> None:

    findings = [
        {
            "number": 1,
            "state": "open",
            "rule": {"id": "py/unused-import", "title": "Unused import"},
            "location": {"path": "a.py"},
            "message": {"text": "Import of 'x' is not used."},
        },
        {
            "number": 2,
            "state": "open",
            "rule": {"id": "py/unused-global-variable", "title": "Unused global variable"},
            "location": {"path": "a.py"},
            "message": {"text": "The global variable 'Y' is not used."},
        },
    ]
    assert correlate_code_quality_finding(path="a.py", body="something unrelated", findings=findings) is None


def test_fetch_code_quality_findings_soft_fails(monkeypatch: pytest.MonkeyPatch) -> None:

    def boom(*_a: object, **_k: object) -> object:
        raise GhError(["gh"], 1, "nope")

    monkeypatch.setattr(review_mod, "run_gh", boom)
    assert review_mod.fetch_code_quality_findings("o", "r") == []
