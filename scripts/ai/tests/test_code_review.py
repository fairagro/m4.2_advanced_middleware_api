"""Tests for code-review context / report-write / publish (mocked git/gh)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from m42_ai.cli import main
from m42_ai.code_review import code_review_context, publish_report, write_report
from m42_ai.gh import GhError


def test_shape_local_context_no_gh() -> None:
    def fake_git(args: list[str], **_kwargs: object) -> MagicMock:
        key = tuple(args)
        mapping = {
            ("rev-parse", "HEAD"): "abc123",
            ("merge-base", "main", "HEAD"): "base00",
            ("rev-parse", "--abbrev-ref", "HEAD"): "feature",
            ("diff", "--name-only", "base00...abc123"): "a.py\nb.md\n",
            ("diff", "--shortstat", "base00...abc123"): " 2 files changed, 3 insertions(+)\n",
        }
        if key not in mapping:
            raise AssertionError(f"unexpected git {args}")
        return MagicMock(stdout=mapping[key])

    with patch("m42_ai.code_review.run_git", side_effect=fake_git) as git, patch("m42_ai.code_review.run_gh") as gh:
        out = code_review_context(base="main")
    assert out["ok"] is True
    assert out["mode"] == "local"
    assert out["paths"] == ["a.py", "b.md"]
    assert out["head_ref"] == "feature"
    assert out["pr"] is None
    assert out["diff_omitted"] is True
    git.assert_called()
    gh.assert_not_called()


def test_shape_pr_context_includes_pr() -> None:
    view = {
        "number": 9,
        "url": "https://github.com/o/r/pull/9",
        "baseRefName": "main",
        "headRefName": "feat",
        "headRefOid": "deadbeef",
        "commits": [],
    }

    def fake_gh(args: list[str], **_kwargs: object) -> MagicMock:
        if args[:2] == ["pr", "view"]:
            return MagicMock(stdout=__import__("json").dumps(view), returncode=0)
        if args[:2] == ["pr", "diff"] and "--name-only" in args:
            return MagicMock(stdout="x.py\n", returncode=0)
        raise AssertionError(f"unexpected gh {args}")

    with (
        patch("m42_ai.code_review.run_gh", side_effect=fake_gh),
        patch("m42_ai.code_review.repo_owner_name", return_value=("o", "r")),
    ):
        out = code_review_context(pr=9)
    assert out["mode"] == "pr"
    assert out["pr"]["number"] == 9
    assert out["paths"] == ["x.py"]
    assert out["head"] == "deadbeef"


def test_write_report_tmp(tmp_path: Path) -> None:
    out = write_report("# Findings\n\n- one\n", slug="my-branch", tmp_dir=tmp_path)
    assert out["ok"] is True
    path = Path(out["path"])
    assert path.parent == tmp_path.resolve()
    assert path.name.startswith("code-review-my-branch-")
    assert path.name.endswith(".md")
    text = path.read_text(encoding="utf-8")
    assert text.startswith("<!-- m42-ai:code-review -->")
    assert "# Findings" in text


def test_write_report_keeps_existing_marker(tmp_path: Path) -> None:
    body = "<!-- m42-ai:code-review -->\n## Verdict\n\nok\n"
    out = write_report(body, slug="marked", tmp_dir=tmp_path)
    text = Path(out["path"]).read_text(encoding="utf-8")
    assert text.count("<!-- m42-ai:code-review -->") == 1
    assert "## Verdict" in text


def test_publish_local_noop(tmp_path: Path) -> None:
    body = tmp_path / "r.md"
    body.write_text("hi\n", encoding="utf-8")
    with patch("m42_ai.code_review.run_gh") as gh:
        out = publish_report(body_file=body, pr=None)
    assert out["channel"] == "local"
    assert out["ok"] is True
    gh.assert_not_called()


def test_publish_review_comment_event(tmp_path: Path) -> None:
    body = tmp_path / "r.md"
    body.write_text("review body\n", encoding="utf-8")
    with patch("m42_ai.code_review.run_gh") as gh:
        gh.return_value = MagicMock(returncode=0, stdout="", stderr="")
        out = publish_report(body_file=body, pr=3, owner="o", repo="r")
    assert out["channel"] == "pull_request_review"
    argv = gh.call_args.args[0]
    assert argv[:3] == ["pr", "review", "3"]
    assert "--comment" in argv
    assert "--body-file" in argv


def test_publish_falls_back_to_conversation_comment(tmp_path: Path) -> None:
    body = tmp_path / "r.md"
    body.write_text("x\n", encoding="utf-8")

    def fake_gh(args: list[str], **_kwargs: object) -> MagicMock:
        if args[:2] == ["pr", "review"]:
            raise GhError(args, 1, "review failed")
        if args[:2] == ["pr", "comment"]:
            return MagicMock(returncode=0, stdout="", stderr="")
        raise AssertionError(args)

    with patch("m42_ai.code_review.run_gh", side_effect=fake_gh):
        out = publish_report(body_file=body, pr=5)
    assert out["channel"] == "conversation_comment"
    assert out["ok"] is True


def test_cli_report_write_and_publish_wired(tmp_path: Path) -> None:
    with patch("m42_ai.cli.write_report", return_value={"ok": True, "path": str(tmp_path / "a.md")}) as wr:
        with patch("sys.stdout", new_callable=lambda: __import__("io").StringIO()) as buf:
            rc = main([
                "code-review-report-write",
                "--body",
                "# hi",
                "--slug",
                "s",
                "--tmp-dir",
                str(tmp_path),
            ])
        assert rc == 0
        assert wr.called
        assert "a.md" in buf.getvalue()

    body = tmp_path / "b.md"
    body.write_text("z\n", encoding="utf-8")
    with patch("m42_ai.cli.publish_report", return_value={"ok": True, "channel": "local", "path": str(body)}):
        with patch("sys.stdout", new_callable=lambda: __import__("io").StringIO()):
            rc = main(["code-review-publish", "--body-file", str(body)])
        assert rc == 0


def test_cli_context_local() -> None:
    with patch(
        "m42_ai.cli.code_review_context",
        return_value={"ok": True, "mode": "local", "paths": [], "pr": None},
    ):
        with patch("sys.stdout", new_callable=lambda: __import__("io").StringIO()) as buf:
            rc = main(["code-review-context", "--base", "main"])
        assert rc == 0
        assert '"mode": "local"' in buf.getvalue()
