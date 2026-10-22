"""Filesystem ARC persistence for the local offline stand-in (no Git remote)."""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

from arctrl import ARC, start_as_task

from middleware.api_local_offline.config import LocalOfflineConfig

logger = logging.getLogger(__name__)

_SAFE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")


class FilesystemArcStoreError(Exception):
    """Raised when a filesystem ARC write fails."""


class FilesystemArcStore:
    """Persist ARCs under a local output root with arctrl (no Git remote)."""

    def __init__(self, config: LocalOfflineConfig) -> None:
        """Initialize with offline stand-in config."""
        self._output_root = config.output_root.expanduser().resolve()

    @property
    def output_root(self) -> Path:
        """Configured output root (resolved)."""
        return self._output_root

    def resolve_arc_dir(self, arc_id: str, *, identifier: str | None = None) -> Path:
        """Return a directory path under the output root for this ARC."""
        base_real = Path(os.path.realpath(self._output_root))
        candidates: list[str] = []
        if identifier is not None and identifier.strip():
            candidates.append(os.path.basename(identifier.strip()))
        candidates.append(os.path.basename(arc_id.strip()) if arc_id.strip() else "")

        for name in candidates:
            if not name or name in {".", ".."} or not _SAFE_NAME_PATTERN.match(name):
                continue
            candidate = Path(os.path.realpath(base_real / name))
            if str(candidate).startswith(str(base_real) + os.sep):
                return candidate

        fallback = f"arc_{os.urandom(4).hex()}"
        return Path(os.path.realpath(base_real / fallback))

    async def create_or_update(self, arc_id: str, arc: ARC, *, rdi: str) -> bool:
        """Write *arc* under the output root. Returns True when a write completed."""
        _ = rdi
        self._output_root.mkdir(parents=True, exist_ok=True)
        identifier = getattr(arc, "Identifier", None)
        if not isinstance(identifier, str):
            identifier = None
        target = self.resolve_arc_dir(arc_id, identifier=identifier)
        try:
            target.mkdir(parents=True, exist_ok=True)
            await start_as_task(arc.WriteAsync(str(target)))
        except Exception as exc:
            raise FilesystemArcStoreError(f"Failed to write ARC {arc_id} under {self._output_root}: {exc}") from exc
        logger.info("Wrote ARC %s to %s", arc_id, target)
        return True

    def check_health(self) -> bool:
        """Return True when the output root is writable."""
        try:
            self._output_root.mkdir(parents=True, exist_ok=True)
            probe = self._output_root / ".local_offline_write_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return True
        except OSError:
            logger.warning("Filesystem ArcStore health failed for %s", self._output_root)
            return False

    async def finalize(self, *, rdi: str) -> bool:
        """Catalog finalize is a no-op for the local offline stand-in."""
        _ = (self, rdi)
        return False
