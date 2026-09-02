"""Best-effort reclaim of stale ephemeral Git working directories under cache_dir."""

from __future__ import annotations

import logging
import re
import shutil
import time
from collections.abc import Iterable
from pathlib import Path

logger = logging.getLogger(__name__)

GIT_REPO_SYNC_PREFIX = "git_repo_sync_"
CATALOG_FINALIZE_PREFIX = "catalog_finalize_"

# Longer than a worst-case clone + write + push under load.
DEFAULT_ORPHAN_TTL_SECONDS = 6 * 60 * 60

_EPHEMERAL_PREFIXES: tuple[str, ...] = (GIT_REPO_SYNC_PREFIX, CATALOG_FINALIZE_PREFIX)
# Production ``arc_id`` is SHA-256 hex (see ``calculate_arc_id``).
_LEGACY_ARC_ID_DIR = re.compile(r"^[0-9a-f]{64}$")


def _directory_age_seconds(path: Path, *, now: float) -> float | None:
    try:
        return now - path.stat().st_mtime
    except OSError:
        return None


def reclaim_stale_git_cache_dirs(
    cache_dir: Path,
    *,
    ttl_seconds: float = DEFAULT_ORPHAN_TTL_SECONDS,
    include_legacy_arc_id_dirs: bool = True,
    now: float | None = None,
    prefixes: Iterable[str] | None = None,
) -> int:
    """Delete stale ephemeral (and optional legacy) directories under ``cache_dir``.

    Returns the number of directories successfully removed. Failures are logged and
    skipped so callers can treat reclaim as best-effort.
    """
    if not cache_dir.is_dir():
        return 0

    clock = time.time() if now is None else now
    active_prefixes = tuple(prefixes) if prefixes is not None else _EPHEMERAL_PREFIXES
    removed = 0

    try:
        entries = list(cache_dir.iterdir())
    except OSError as exc:
        logger.warning("Failed to list git cache dir %s: %s", cache_dir, exc)
        return 0

    for entry in entries:
        if not entry.is_dir():
            continue
        name = entry.name
        matches_prefix = any(name.startswith(prefix) for prefix in active_prefixes)
        matches_legacy = include_legacy_arc_id_dirs and _LEGACY_ARC_ID_DIR.fullmatch(name) is not None
        if not matches_prefix and not matches_legacy:
            continue
        age = _directory_age_seconds(entry, now=clock)
        if age is None or age < ttl_seconds:
            continue
        try:
            shutil.rmtree(entry)
            removed += 1
            logger.info("Reclaimed stale git cache directory %s (age=%.0fs)", entry, age)
        except OSError as exc:
            logger.warning("Failed to reclaim git cache directory %s: %s", entry, exc)

    return removed
