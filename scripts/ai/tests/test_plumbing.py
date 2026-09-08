"""Contract tests for auth / issue-view / branch / PR hygiene (mocked — no live GitHub)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from m42_ai.auth import auth_status
from m42_ai.issue import branch_ahead, ensure_issue_branch, view_issue
from m42_ai.pr import pr_strip_footer, strip_marketing_footers


def test_strip_marketing_footers_cursor_markdown() -> None:
    body = "## Summary\n- done\n\nFixes #6\n\n---\nMade with [Cursor](https://cursor.com)\n"
    cleaned, changed = strip_marketing_footers(body)
    assert changed is True
    assert "Made with" not in cleaned
    assert "Fixes #6" in cleaned


def test_strip_marketing_footers_noop() -> None:
    body = "## Summary\n- done\n\nFixes #6\n"
    cleaned, changed = strip_marketing_footers(body)
    assert changed is False
    assert cleaned == body


def test_auth_status_ok() -> None:
    payload = {
        "hosts": {
            "github.com": [
                {
                    "state": "success",
                    "active": True,
                    "host": "github.com",
                    "login": "alice",
                    "tokenSource": "GH_TOKEN",
                    "gitProtocol": "https",
                }
            ]
        }
    }
    with patch("m42_ai.auth.run_gh") as run_gh:
        run_gh.return_value = MagicMock(returncode=0, stdout=__import__("json").dumps(payload), stderr="")
        out = auth_status()
    assert out["ok"] is True
    assert out["login"] == "alice"
    assert out["token_source"] == "GH_TOKEN"
    assert out["error"] is None


def test_auth_status_missing_host() -> None:
    with patch("m42_ai.auth.run_gh") as run_gh:
        run_gh.return_value = MagicMock(returncode=0, stdout='{"hosts":{}}', stderr="")
        out = auth_status()
    assert out["ok"] is False
    assert out["error"]


def test_view_issue_shapes_triage() -> None:
    raw = {
        "number": 6,
        "title": "Pin vendor skills",
        "url": "https://github.com/o/r/issues/6",
        "body": "done when…",
        "state": "OPEN",
        "issueType": {"name": "Task"},
        "labels": [
            {"name": "severity:medium"},
            {"name": "practicality:high"},
            {"name": "cost:cheap"},
            {"name": "other"},
            {"name": None},
            {"name": "  "},
            "also-ok",
        ],
        "author": {"login": "alice"},
    }
    with patch("m42_ai.issue.run_gh") as run_gh:
        run_gh.return_value = MagicMock(stdout=__import__("json").dumps(raw))
        out = view_issue(6)
    assert out["issue_type"] == "Task"
    assert out["triage"] == {
        "severity": "severity:medium",
        "practicality": "practicality:high",
        "cost": "cost:cheap",
    }
    assert "other" in out["labels"]
    assert "also-ok" in out["labels"]
    assert "None" not in out["labels"]
    assert "" not in out["labels"]


def test_branch_ahead_ok_and_not() -> None:
    def fake_git(args: list[str], **kwargs: object) -> MagicMock:
        if args[:3] == ["fetch", "origin", "main"]:
            return MagicMock(stdout="")
        if args[:2] == ["branch", "--show-current"]:
            return MagicMock(stdout="issue-6-x\n")
        if args[:2] == ["rev-list", "--count"]:
            return MagicMock(stdout="2\n")
        raise AssertionError(args)

    with patch("m42_ai.issue.run_git", side_effect=fake_git):
        out = branch_ahead(base="main")
    assert out["ok"] is True
    assert out["ahead"] == 2
    assert out["upstream"] == "origin/main"

    def fake_git_zero(args: list[str], **kwargs: object) -> MagicMock:
        if args[:3] == ["fetch", "origin", "main"]:
            return MagicMock(stdout="")
        if args[:2] == ["branch", "--show-current"]:
            return MagicMock(stdout="issue-6-x\n")
        return MagicMock(stdout="0\n")

    with patch("m42_ai.issue.run_git", side_effect=fake_git_zero):
        out0 = branch_ahead(base="main")
    assert out0["ok"] is False
    assert out0["ahead"] == 0


def test_ensure_issue_branch_refuses_dirty(tmp_path: Path) -> None:
    with patch("m42_ai.issue.run_git") as run_git:
        run_git.return_value = MagicMock(stdout=" M x\n")
        with pytest.raises(RuntimeError, match="clean"):
            ensure_issue_branch(issue=6, slug="pin", cwd=tmp_path)


def test_pr_strip_footer_edits_when_changed() -> None:
    dirty = "## Summary\n\nFixes #6\n\nMade with Cursor\n"
    calls: list[list[str]] = []

    def fake_gh(args: list[str], **kwargs: object) -> MagicMock:
        calls.append(list(args))
        if args[:2] == ["pr", "view"]:
            return MagicMock(
                stdout=__import__("json").dumps({
                    "number": 25,
                    "url": "https://github.com/o/r/pull/25",
                    "title": "t",
                    "body": dirty,
                })
            )
        if args[:2] == ["pr", "edit"]:
            return MagicMock(stdout="")
        raise AssertionError(args)

    with patch("m42_ai.pr.run_gh", side_effect=fake_gh):
        out = pr_strip_footer(25)
    assert out["changed"] is True
    assert "Made with" not in out["body"]
    assert any(c[:2] == ["pr", "edit"] for c in calls)


def test_pr_strip_footer_noop_skips_edit() -> None:
    clean = "## Summary\n\nFixes #6\n"
    calls: list[list[str]] = []

    def fake_gh(args: list[str], **kwargs: object) -> MagicMock:
        calls.append(list(args))
        if args[:2] == ["pr", "view"]:
            return MagicMock(
                stdout=__import__("json").dumps({
                    "number": 25,
                    "url": "https://github.com/o/r/pull/25",
                    "title": "t",
                    "body": clean,
                })
            )
        raise AssertionError(args)

    with patch("m42_ai.pr.run_gh", side_effect=fake_gh):
        out = pr_strip_footer(25)
    assert out["changed"] is False
    assert not any(c[:2] == ["pr", "edit"] for c in calls)
