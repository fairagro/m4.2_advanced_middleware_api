"""Unit tests for age-gated git cache orphan reclaim."""

from __future__ import annotations

import os
import time
from pathlib import Path

from middleware.api.arc_store.git_cache_cleanup import (
    CATALOG_FINALIZE_PREFIX,
    DEFAULT_ORPHAN_TTL_SECONDS,
    GIT_REPO_SYNC_PREFIX,
    reclaim_stale_git_cache_dirs,
)


def _age_dir(path: Path, *, age_seconds: float) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "marker").write_text("x", encoding="utf-8")
    stamped = time.time() - age_seconds
    os.utime(path, (stamped, stamped))


def test_reclaim_deletes_stale_ephemeral_and_legacy_dirs(tmp_path: Path) -> None:
    """Stale prefix and SHA-256 legacy dirs are removed; recent ones stay."""
    cache = tmp_path / "cache"
    cache.mkdir()
    stale_sync = cache / f"{GIT_REPO_SYNC_PREFIX}old"
    fresh_sync = cache / f"{GIT_REPO_SYNC_PREFIX}new"
    stale_finalize = cache / f"{CATALOG_FINALIZE_PREFIX}old"
    legacy = cache / ("a" * 64)
    unrelated = cache / "keep_me"
    _age_dir(stale_sync, age_seconds=DEFAULT_ORPHAN_TTL_SECONDS + 60)
    _age_dir(fresh_sync, age_seconds=60)
    _age_dir(stale_finalize, age_seconds=DEFAULT_ORPHAN_TTL_SECONDS + 60)
    _age_dir(legacy, age_seconds=DEFAULT_ORPHAN_TTL_SECONDS + 60)
    _age_dir(unrelated, age_seconds=DEFAULT_ORPHAN_TTL_SECONDS + 60)

    removed = reclaim_stale_git_cache_dirs(cache)

    assert removed == 3
    assert not stale_sync.exists()
    assert not stale_finalize.exists()
    assert not legacy.exists()
    assert fresh_sync.exists()
    assert unrelated.exists()


def test_reclaim_preserves_recent_dirs_and_missing_cache(tmp_path: Path) -> None:
    """Young ephemeral dirs survive; missing cache_dir is a no-op."""
    cache = tmp_path / "cache"
    recent = cache / f"{GIT_REPO_SYNC_PREFIX}active"
    _age_dir(recent, age_seconds=30)

    assert reclaim_stale_git_cache_dirs(cache, ttl_seconds=3600) == 0
    assert recent.exists()
    assert reclaim_stale_git_cache_dirs(tmp_path / "missing") == 0
