"""Per-RDI single-flight lock for catalog finalize (process-local fallback)."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

# Per-event-loop locks keyed by RDI. CouchDB overrides for multi-worker Celery
# (see CouchDB.catalog_finalize_lock). Keying by loop id avoids pytest-asyncio
# "Lock is bound to a different event loop" when modules outlive a loop.
_locks_by_loop: dict[int, dict[str, asyncio.Lock]] = {}
_guards_by_loop: dict[int, asyncio.Lock] = {}


async def _lock_for(rdi: str) -> asyncio.Lock:
    loop = asyncio.get_running_loop()
    loop_id = id(loop)
    guard = _guards_by_loop.get(loop_id)
    if guard is None:
        guard = asyncio.Lock()
        _guards_by_loop[loop_id] = guard
        _locks_by_loop[loop_id] = {}
    async with guard:
        locks = _locks_by_loop[loop_id]
        lock = locks.get(rdi)
        if lock is None:
            lock = asyncio.Lock()
            locks[rdi] = lock
        return lock


@asynccontextmanager
async def process_local_catalog_finalize_lock(
    rdi: str,
    *,
    wait_timeout_s: float,
) -> AsyncGenerator[None, None]:
    """Acquire a process-local per-RDI lock or time out.

    Raises:
        TimeoutError: If the lock is not acquired within ``wait_timeout_s``.
    """
    lock = await _lock_for(rdi)
    try:
        await asyncio.wait_for(lock.acquire(), timeout=wait_timeout_s)
    except TimeoutError as exc:
        raise TimeoutError(f"Catalog finalize lock wait timed out for RDI {rdi}") from exc
    try:
        yield
    finally:
        lock.release()
