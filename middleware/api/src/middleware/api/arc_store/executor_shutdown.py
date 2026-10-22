"""Bounded thread-pool shutdown and ephemeral workdir removal for Git ArcStores."""

from __future__ import annotations

import logging
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

logger = logging.getLogger(__name__)

# Long enough for a typical in-flight clone to finish its workdir cleanup, short enough
# that Celery worker_shutdown does not wait without a bound.
EXECUTOR_SHUTDOWN_TIMEOUT_S = 60.0


def shutdown_executor(executor: ThreadPoolExecutor, *, timeout_s: float = EXECUTOR_SHUTDOWN_TIMEOUT_S) -> None:
    """Cancel unstarted work and wait up to ``timeout_s`` for work that has started.

    ``Executor.shutdown`` has no timeout argument. A daemon waiter runs ``wait=True`` so
    this function can return when the bound expires. Pool threads stay non-daemon.
    """
    finished = threading.Event()

    def _wait() -> None:
        executor.shutdown(wait=True, cancel_futures=True)
        finished.set()

    threading.Thread(target=_wait, name="arcstore-executor-shutdown", daemon=True).start()
    if not finished.wait(timeout_s):
        logger.warning(
            "ArcStore executor shutdown exceeded %.0fs; in-flight Git work may still be running",
            timeout_s,
        )


def remove_ephemeral_workdir(local_path: Path) -> None:
    """Remove an ephemeral Git workdir. A missing path is success. Other OS errors are logged."""
    try:
        shutil.rmtree(local_path)
    except FileNotFoundError:
        return
    except OSError as exc:
        logger.warning("Failed to clean up local path %s: %s", local_path, exc)
