"""Tests for bounded ArcStore executor shutdown and ephemeral workdir removal."""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr

from middleware.api.arc_store.consolidated_git import ConsolidatedGitArcStore, ConsolidatedGitConfig
from middleware.api.arc_store.executor_shutdown import remove_ephemeral_workdir, shutdown_executor
from middleware.api.arc_store.git_repo import GitRepo, GitRepoConfig


def test_shutdown_executor_waits_for_fast_task() -> None:
    """A task that finishes inside the bound is done before shutdown returns."""
    executor = ThreadPoolExecutor(max_workers=1)
    finished = threading.Event()

    def _task() -> None:
        finished.set()

    executor.submit(_task)
    started = time.monotonic()
    shutdown_executor(executor, timeout_s=2.0)
    assert finished.is_set()
    assert time.monotonic() - started < 1.5


def test_shutdown_executor_returns_when_work_exceeds_bound() -> None:
    """In-flight work past the bound does not hold shutdown, and a queued task does not run."""
    executor = ThreadPoolExecutor(max_workers=1)
    started = threading.Event()
    release = threading.Event()
    queued_ran = threading.Event()

    def _blocker() -> None:
        started.set()
        release.wait(5)

    def _queued() -> None:
        queued_ran.set()

    try:
        executor.submit(_blocker)
        assert started.wait(2)
        executor.submit(_queued)
        started_at = time.monotonic()
        shutdown_executor(executor, timeout_s=0.25)
        elapsed = time.monotonic() - started_at
    finally:
        release.set()

    assert elapsed >= 0.2
    assert elapsed < 1.5
    assert not queued_ran.is_set()


def test_remove_ephemeral_workdir_logs_os_error_and_does_not_raise(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """OSError while deleting a workdir is a warning, not an exception."""
    work_dir = tmp_path / "git_repo_sync_orphan"
    work_dir.mkdir()
    with (
        patch("middleware.api.arc_store.executor_shutdown.shutil.rmtree", side_effect=OSError("busy")),
        caplog.at_level("WARNING"),
    ):
        remove_ephemeral_workdir(work_dir)
    assert "busy" in caplog.text
    assert str(work_dir) in caplog.text


def test_remove_ephemeral_workdir_missing_path_is_silent(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """A workdir that is already gone does not log."""
    missing = tmp_path / "already-gone"
    with caplog.at_level("WARNING"):
        remove_ephemeral_workdir(missing)
    assert caplog.text == ""


@pytest.mark.asyncio
async def test_git_repo_shutdown_returns_when_work_exceeds_bound(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GitRepo.shutdown returns once the bound expires while Git work is still in flight."""
    monkeypatch.setattr("middleware.api.arc_store.git_repo.store.EXECUTOR_SHUTDOWN_TIMEOUT_S", 0.25)
    repo = GitRepo(
        GitRepoConfig(
            url="https://gitlab.example.com",
            group="mygroup",
            token=None,
            cache_dir=tmp_path / "git_cache",
        )
    )
    started = threading.Event()
    release = threading.Event()

    def _blocker() -> None:
        started.set()
        release.wait(5)

    try:
        repo._executor.submit(_blocker)  # noqa: SLF001
        assert started.wait(2)
        started_at = time.monotonic()
        await repo.shutdown()
        elapsed = time.monotonic() - started_at
    finally:
        release.set()

    assert elapsed >= 0.2
    assert elapsed < 1.5


@pytest.mark.asyncio
async def test_consolidated_shutdown_returns_when_work_exceeds_bound(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Catalog store shutdown returns once the bound expires while Git work is still in flight."""
    monkeypatch.setattr("middleware.api.arc_store.consolidated_git.store.EXECUTOR_SHUTDOWN_TIMEOUT_S", 0.25)
    store = ConsolidatedGitArcStore(
        ConsolidatedGitConfig(
            repo_url=f"file://{(tmp_path / 'catalog.git').resolve()}",
            cache_dir=tmp_path / "cache",
        ),
        MagicMock(),
    )
    started = threading.Event()
    release = threading.Event()

    def _blocker() -> None:
        started.set()
        release.wait(5)

    try:
        store._executor.submit(_blocker)  # noqa: SLF001
        assert started.wait(2)
        started_at = time.monotonic()
        await store.shutdown()
        elapsed = time.monotonic() - started_at
    finally:
        release.set()

    assert elapsed >= 0.2
    assert elapsed < 1.5


@pytest.mark.asyncio
async def test_shutdown_completes_when_inflight_workdir_delete_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A failed workdir delete inside in-flight work does not fail shutdown."""
    monkeypatch.setattr("middleware.api.arc_store.git_repo.store.EXECUTOR_SHUTDOWN_TIMEOUT_S", 2.0)
    repo = GitRepo(
        GitRepoConfig(
            url="https://gitlab.example.com",
            group="mygroup",
            token=SecretStr("unused"),
            cache_dir=tmp_path / "git_cache",
        )
    )
    work_dir = tmp_path / "git_repo_sync_inflight"
    work_dir.mkdir()

    def _work() -> None:
        remove_ephemeral_workdir(work_dir)

    with (
        patch("middleware.api.arc_store.executor_shutdown.shutil.rmtree", side_effect=OSError("locked")),
        caplog.at_level("WARNING"),
    ):
        repo._executor.submit(_work)  # noqa: SLF001
        await repo.shutdown()

    assert "locked" in caplog.text
    assert str(work_dir) in caplog.text
