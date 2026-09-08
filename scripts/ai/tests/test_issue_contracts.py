"""Contract tests for issue-create / issue-start (mocked gh/git — no live GitHub)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from m42_ai.gh import GhError
from m42_ai.issue import create_issue, ensure_labels, issue_start


def test_cli_issue_create_omits_practicality_when_unset() -> None:
    from argparse import Namespace

    from m42_ai.cli import cmd_issue_create

    with patch("m42_ai.cli.create_issue") as create:
        create.return_value = {"url": "https://example/issues/1"}
        rc = cmd_issue_create(
            Namespace(
                title="t",
                type="Task",
                severity="severity:low",
                practicality=None,
                cost="cost:medium",
                parent=None,
                body="b",
                body_file=None,
            )
        )
    assert rc == 0
    assert create.call_args.kwargs["labels"] == ["severity:low", "cost:medium"]


def test_ensure_labels_lists_with_high_limit() -> None:
    with patch("m42_ai.issue.run_gh") as run_gh:
        run_gh.return_value = MagicMock(stdout="severity:high\n")
        ensure_labels(["severity:high", "practicality:high", "cost:cheap"])
        listed = run_gh.call_args_list[0]
        assert listed.args[0][:4] == ["label", "list", "--limit", "1000"]
        # existing severity:high skipped; other two created
        assert run_gh.call_count == 3


def test_create_issue_parent_error_with_url_on_stdout_does_not_fallback() -> None:
    url = "https://github.com/fairagro/m4.2_middleware_devinfra/issues/99"
    calls: list[list[str]] = []

    def fake_gh(args: list[str], **kwargs: object) -> MagicMock:
        calls.append(list(args))
        if args[:2] == ["label", "list"]:
            return MagicMock(stdout="severity:high\npracticality:high\ncost:cheap\n")
        if args[:2] == ["issue", "create"] and "--parent" in args:
            raise GhError(
                ["gh", *args],
                1,
                stderr="failed to add as sub-issue\n",
                stdout=f"{url}\n",
            )
        raise AssertionError(f"unexpected gh call: {args}")

    with patch("m42_ai.issue.run_gh", side_effect=fake_gh):
        out = create_issue(
            title="t",
            body="b",
            issue_type="Task",
            labels=["severity:high", "practicality:high", "cost:cheap"],
            parent=16,
        )
    assert out["url"] == url
    assert out["partial_failure"] is True
    assert out["parent_fallback"] is False
    assert sum(1 for c in calls if c[:2] == ["issue", "create"]) == 1


def test_create_issue_parent_error_without_url_falls_back_once() -> None:
    url = "https://github.com/fairagro/m4.2_middleware_devinfra/issues/100"
    creates = 0

    def fake_gh(args: list[str], **kwargs: object) -> MagicMock:
        nonlocal creates
        if args[:2] == ["label", "list"]:
            return MagicMock(stdout="severity:high\npracticality:high\ncost:cheap\n")
        if args[:2] == ["issue", "create"]:
            creates += 1
            if "--parent" in args:
                raise GhError(["gh", *args], 1, stderr="unsupported --parent\n", stdout="")
            return MagicMock(stdout=f"{url}\n")
        raise AssertionError(f"unexpected gh call: {args}")

    with patch("m42_ai.issue.run_gh", side_effect=fake_gh):
        out = create_issue(
            title="t",
            body="b",
            issue_type="Task",
            labels=["severity:high", "practicality:high", "cost:cheap"],
            parent=16,
        )
    assert creates == 2
    assert out["url"] == url
    assert out["parent_fallback"] is True
    assert out["partial_failure"] is True
    assert out["relation"] == "linked"


def test_issue_start_refuses_dirty_tree(tmp_path: Path) -> None:
    with patch("m42_ai.issue.run_git") as run_git:
        run_git.return_value = MagicMock(stdout=" M file.py\n")
        with pytest.raises(RuntimeError, match="clean"):
            issue_start(issue=16, cwd=tmp_path)
        assert run_git.call_count == 1


def test_issue_start_refuses_when_not_ahead(tmp_path: Path) -> None:
    git_calls: list[list[str]] = []

    def fake_git(args: list[str], **kwargs: object) -> MagicMock:
        git_calls.append(list(args))
        if args[:2] == ["status", "--porcelain"]:
            return MagicMock(stdout="")
        if args[:2] == ["fetch", "origin"]:
            return MagicMock(stdout="")
        if args[:2] == ["branch", "--show-current"]:
            return MagicMock(stdout="issue-16-example\n")
        if args[:2] == ["rev-list", "--count"]:
            return MagicMock(stdout="0\n")
        raise AssertionError(f"unexpected git call: {args}")

    def fake_gh(args: list[str], **kwargs: object) -> MagicMock:
        if args[:2] == ["issue", "view"]:
            return MagicMock(stdout='{"title":"Example","url":"https://github.com/o/r/issues/16","number":16}')
        raise AssertionError(f"unexpected gh call: {args}")

    with (
        patch("m42_ai.issue.run_git", side_effect=fake_git),
        patch("m42_ai.issue.run_gh", side_effect=fake_gh),
        pytest.raises(RuntimeError, match="no commits ahead"),
    ):
        issue_start(issue=16, slug="example", cwd=tmp_path)

    assert not any(c[:2] == ["commit", "--allow-empty"] for c in git_calls)
    assert not any(c[:1] == ["push"] for c in git_calls)
