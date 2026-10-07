"""Unit tests for GitContext.commit_and_push push/skip signalling."""

from unittest.mock import MagicMock, patch

import pytest

from middleware.api.arc_store.git_context import GitContext


@pytest.fixture
def git_context_and_repo() -> tuple[GitContext, MagicMock]:
    """Minimal GitContext with a mocked repo (returned separately for typing)."""
    ctx = GitContext.__new__(GitContext)
    ctx.config = MagicMock()
    ctx.config.branch = "main"
    ctx._tracer = MagicMock()  # noqa: SLF001
    span = MagicMock()
    span_cm = MagicMock()
    span_cm.__enter__.return_value = span
    span_cm.__exit__.return_value = None
    ctx._tracer.start_as_current_span.return_value = span_cm
    repo = MagicMock()
    ctx.repo = repo
    return ctx, repo


def test_commit_and_push_returns_false_when_clean(git_context_and_repo: tuple[GitContext, MagicMock]) -> None:
    """Clean working tree skips commit/push and returns False."""
    ctx, repo = git_context_and_repo
    repo.is_dirty.return_value = False

    assert ctx.commit_and_push("msg") is False
    repo.git.add.assert_not_called()
    repo.index.commit.assert_not_called()


def test_commit_and_push_returns_true_when_dirty(git_context_and_repo: tuple[GitContext, MagicMock]) -> None:
    """Dirty working tree commits, pushes, and returns True."""
    ctx, repo = git_context_and_repo
    repo.is_dirty.return_value = True
    with patch.object(ctx, "_run_git_command") as mock_run:
        assert ctx.commit_and_push("msg") is True

    repo.git.add.assert_called_once_with(A=True)
    repo.index.commit.assert_called_once_with("msg")
    mock_run.assert_called_once()
