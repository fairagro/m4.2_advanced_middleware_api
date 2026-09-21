"""Tests for sync-followup parse / pr-for-commit / ensure (mocked gh)."""

from __future__ import annotations

from argparse import Namespace
from unittest.mock import MagicMock, patch

from m42_ai.cli import cmd_pr_for_commit, cmd_sync_followup_ensure, cmd_sync_followup_ids
from m42_ai.sync_followup import (
    ensure_sync_followup_issue,
    parse_sync_followup_ids,
    pr_for_commit,
)


def test_parse_body_only() -> None:
    ids = parse_sync_followup_ids("Summary\n\nSYNC-FOLLOWUP: remove-stubs\n\nMore\n")
    assert ids == ["remove-stubs"]


def test_parse_comment_only_and_both() -> None:
    assert parse_sync_followup_ids("", "SYNC-FOLLOWUP: owslib-silence\n") == ["owslib-silence"]
    ids = parse_sync_followup_ids(
        "SYNC-FOLLOWUP: remove-stubs\n",
        "note\nSYNC-FOLLOWUP: owslib-silence\n",
        "SYNC-FOLLOWUP: remove-stubs\n",
    )
    assert ids == ["remove-stubs", "owslib-silence"]


def test_parse_ignores_malformed() -> None:
    assert not parse_sync_followup_ids("SYNC-FOLLOWUP:\n", "SYNC-FOLLOWUP: \n", "x SYNC-FOLLOWUP: nope\n")


def test_pr_for_commit_matches_merge_oid() -> None:
    payload = [
        {
            "number": 42,
            "url": "https://github.com/o/r/pull/42",
            "title": "t",
            "body": "SYNC-FOLLOWUP: a\n",
            "mergeCommit": {"oid": "abcdef1234567890"},
            "commits": [],
        }
    ]
    with patch("m42_ai.sync_followup.run_gh") as run_gh:
        run_gh.return_value = MagicMock(stdout=__import__("json").dumps(payload))
        out = pr_for_commit("abcdef1", owner="o", repo="r")
    assert out is not None
    assert out["number"] == 42


def test_cli_sync_followup_ids_offline() -> None:
    with patch("sys.stdout", new_callable=lambda: __import__("io").StringIO()) as buf:
        rc = cmd_sync_followup_ids(
            Namespace(
                pr=None,
                owner=None,
                repo=None,
                cwd=None,
                body="SYNC-FOLLOWUP: remove-stubs\n",
                body_file=None,
                comment=["SYNC-FOLLOWUP: other-id\n"],
            )
        )
    assert rc == 0
    assert "remove-stubs" in buf.getvalue()
    assert "other-id" in buf.getvalue()


def test_ensure_reuses_open_issue() -> None:
    listed = [{"number": 7, "url": "https://github.com/o/p/issues/7", "title": "Sync follow-up: x", "labels": []}]
    calls: list[list[str]] = []

    def fake_gh(args: list[str], **kwargs: object) -> MagicMock:
        calls.append(list(args))
        if args[:2] == ["issue", "list"]:
            return MagicMock(stdout=__import__("json").dumps(listed))
        raise AssertionError(f"unexpected: {args}")

    with patch("m42_ai.sync_followup.run_gh", side_effect=fake_gh):
        out = ensure_sync_followup_issue(repo="o/p", stable_id="remove-stubs")
    assert out["action"] == "reused"
    assert out["number"] == 7
    assert not any(c[:2] == ["issue", "create"] for c in calls)


def test_ensure_creates_when_missing() -> None:
    def fake_gh(args: list[str], **_kwargs: object) -> MagicMock:
        if args[:2] == ["issue", "list"]:
            return MagicMock(stdout="[]")
        if args[:2] == ["label", "list"]:
            return MagicMock(stdout="severity:low\ncost:medium\n")
        if args[:2] == ["label", "create"]:
            return MagicMock(stdout="")
        if args[:2] == ["issue", "create"]:
            return MagicMock(stdout="https://github.com/o/p/issues/9\n")
        raise AssertionError(f"unexpected: {args}")

    with (
        patch("m42_ai.sync_followup.run_gh", side_effect=fake_gh),
        patch("m42_ai.sync_followup.ensure_labels"),
        patch("m42_ai.sync_followup.create_issue") as create,
    ):
        create.return_value = {
            "url": "https://github.com/o/p/issues/9",
            "labels": ["severity:low", "cost:medium", "sync-followup:remove-stubs"],
        }
        out = ensure_sync_followup_issue(repo="o/p", stable_id="remove-stubs", source_sha="abc")
    assert out["action"] == "created"
    assert create.called


def test_ensure_dry_run() -> None:
    out = ensure_sync_followup_issue(repo="o/p", stable_id="x", dry_run=True)
    assert out["action"] == "would_ensure"


def test_cli_pr_for_commit_and_ensure_help_wired() -> None:
    with patch("m42_ai.cli.pr_for_commit", return_value=None):
        with patch("sys.stdout", new_callable=lambda: __import__("io").StringIO()) as buf:
            rc = cmd_pr_for_commit(Namespace(sha="abc", owner=None, repo=None, cwd=None))
        assert rc == 0
        assert '"pr": null' in buf.getvalue().replace(" ", "") or "null" in buf.getvalue()

    with patch("m42_ai.cli.ensure_sync_followup_issue", return_value={"ok": True, "action": "would_ensure"}):
        with patch("sys.stdout", new_callable=lambda: __import__("io").StringIO()):
            rc = cmd_sync_followup_ensure(
                Namespace(
                    repo="o/p",
                    id="x",
                    source_pr_url=None,
                    source_sha=None,
                    cost="cost:medium",
                    template=None,
                    dry_run=True,
                    cwd=None,
                )
            )
        assert rc == 0
