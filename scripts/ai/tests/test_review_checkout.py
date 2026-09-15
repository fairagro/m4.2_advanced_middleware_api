"""PR head checkout guards for review-open (mocked gh — no live GitHub)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from m42_ai.review import ensure_pr_head, fetch_review_open

FIXTURE = Path(__file__).parent / "fixtures" / "review_pr.json"


def _graphql_payload() -> str:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    data["data"]["repository"]["pullRequest"].setdefault("comments", {"nodes": []})
    return json.dumps(data)


def test_ensure_pr_head_checkouts_when_clean_wrong_branch(tmp_path: Path) -> None:
    state = {"branch": "main"}

    def fake_git(args: list[str], **kwargs: object) -> MagicMock:
        if args[:2] == ["branch", "--show-current"]:
            return MagicMock(stdout=f"{state['branch']}\n")
        if args[:2] == ["status", "--porcelain"]:
            return MagicMock(stdout="")
        raise AssertionError(args)

    def fake_gh(args: list[str], **kwargs: object) -> MagicMock:
        if args[:2] == ["pr", "view"]:
            return MagicMock(stdout='{"headRefName":"issue-108-x"}')
        if args[:2] == ["pr", "checkout"]:
            state["branch"] = "issue-108-x"
            return MagicMock(stdout="")
        raise AssertionError(args)

    with (
        patch("m42_ai.review.run_git", side_effect=fake_git),
        patch("m42_ai.review.run_gh", side_effect=fake_gh),
    ):
        out = ensure_pr_head(108, owner="o", repo="r", cwd=tmp_path)

    assert out == {
        "head_ref": "issue-108-x",
        "current_branch": "issue-108-x",
        "checked_out": True,
    }


def test_ensure_pr_head_refuses_dirty_wrong_branch(tmp_path: Path) -> None:
    gh_calls: list[list[str]] = []

    def fake_git(args: list[str], **kwargs: object) -> MagicMock:
        if args[:2] == ["branch", "--show-current"]:
            return MagicMock(stdout="main\n")
        if args[:2] == ["status", "--porcelain"]:
            return MagicMock(stdout=" M file.py\n")
        raise AssertionError(args)

    def fake_gh(args: list[str], **kwargs: object) -> MagicMock:
        gh_calls.append(list(args))
        if args[:2] == ["pr", "view"]:
            return MagicMock(stdout='{"headRefName":"issue-108-x"}')
        raise AssertionError(args)

    with (
        patch("m42_ai.review.run_git", side_effect=fake_git),
        patch("m42_ai.review.run_gh", side_effect=fake_gh),
        pytest.raises(RuntimeError, match="dirty"),
    ):
        ensure_pr_head(108, owner="o", repo="r", cwd=tmp_path)

    assert not any(c[:2] == ["pr", "checkout"] for c in gh_calls)


def test_ensure_pr_head_allows_dirty_on_head(tmp_path: Path) -> None:
    gh_calls: list[list[str]] = []

    def fake_git(args: list[str], **kwargs: object) -> MagicMock:
        if args[:2] == ["branch", "--show-current"]:
            return MagicMock(stdout="issue-108-x\n")
        if args[:2] == ["status", "--porcelain"]:
            return MagicMock(stdout=" M file.py\n")
        raise AssertionError(args)

    def fake_gh(args: list[str], **kwargs: object) -> MagicMock:
        gh_calls.append(list(args))
        if args[:2] == ["pr", "view"]:
            return MagicMock(stdout='{"headRefName":"issue-108-x"}')
        raise AssertionError(args)

    with (
        patch("m42_ai.review.run_git", side_effect=fake_git),
        patch("m42_ai.review.run_gh", side_effect=fake_gh),
    ):
        out = ensure_pr_head(108, owner="o", repo="r", cwd=tmp_path)

    assert out["checked_out"] is False
    assert out["current_branch"] == "issue-108-x"
    assert not any(c[:2] == ["pr", "checkout"] for c in gh_calls)


def test_fetch_review_open_includes_head_fields(tmp_path: Path) -> None:
    state = {"branch": "main"}

    def fake_git(args: list[str], **kwargs: object) -> MagicMock:
        if args[:2] == ["branch", "--show-current"]:
            return MagicMock(stdout=f"{state['branch']}\n")
        if args[:2] == ["status", "--porcelain"]:
            return MagicMock(stdout="")
        raise AssertionError(args)

    def fake_gh(args: list[str], **kwargs: object) -> MagicMock:
        if args[:2] == ["pr", "view"]:
            return MagicMock(stdout='{"headRefName":"feature-x"}')
        if args[:2] == ["pr", "checkout"]:
            state["branch"] = "feature-x"
            return MagicMock(stdout="")
        if args[:2] == ["api", "graphql"]:
            return MagicMock(stdout=_graphql_payload())
        raise AssertionError(args)

    with (
        patch("m42_ai.review.run_git", side_effect=fake_git),
        patch("m42_ai.review.run_gh", side_effect=fake_gh),
    ):
        out = fetch_review_open(1, owner="o", repo="r", cwd=tmp_path)

    assert out["head_ref"] == "feature-x"
    assert out["current_branch"] == "feature-x"
    assert "unresolved_ai_threads" in out
