"""Consolidated Git ArcStore: shared repo with per-RDI catalog JSON files."""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import re
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import ParamSpec, TypeVar, override
from urllib.parse import unquote, urlparse

import git.cmd
from arctrl import ARC  # type: ignore[import-untyped]
from git import Repo
from git.exc import GitCommandError
from opentelemetry import context

from middleware.api.document_store import DocumentStore
from middleware.shared.json_types import CatalogDatasetRecord
from middleware.shared.security.url_redact import redact_url_userinfo

from . import ArcStore, ArcStoreError, ArcStoreTransientError
from .catalog_serialize import extract_catalog_dataset, serialize_catalog_file
from .consolidated_git_config import ConsolidatedGitConfig
from .git_cli_settings import GitContextConfig
from .git_repo import GitContext, format_git_error_detail, is_soft_git_error, is_transient_git_error

logger = logging.getLogger(__name__)

T = TypeVar("T")
P = ParamSpec("P")

# Same character set as Config.validate_known_rdis (single path segment for "{rdi}.json").
_SAFE_RDI_FILENAME = re.compile(r"^[a-zA-Z0-9_.-]+$")


def _require_safe_catalog_rdi(rdi: str) -> None:
    """Reject RDIs that are unsafe as a single catalog filename segment."""
    if not rdi or not _SAFE_RDI_FILENAME.fullmatch(rdi):
        raise ArcStoreError(f"Invalid RDI for catalog filename: {rdi!r}")


class ConsolidatedGitArcStore(ArcStore):
    """Publish ``{rdi}.json`` catalogs to one shared Git repo on finalize."""

    def __init__(self, config: ConsolidatedGitConfig, doc_store: DocumentStore) -> None:
        """Initialize consolidated catalog store."""
        super().__init__()
        self._config = config
        self._doc_store = doc_store
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=self._config.max_workers)

    @property
    @override
    def publishes_per_arc_git(self) -> bool:
        """Catalog backend does not push one Git project per ARC."""
        return False

    @property
    @override
    def supports_standalone_upload(self) -> bool:
        """Standalone upload has no harvest finalize signal."""
        return False

    @override
    async def shutdown(self) -> None:
        """Shut down the thread-pool executor."""
        self._executor.shutdown(wait=False, cancel_futures=True)

    @override
    def _check_health(self) -> bool:
        """Check catalog remote reachability.

        ``file://`` remotes match ``LocalFileSystemGitProvider``: always healthy.
        The bare repo is created lazily on first publish (``_ensure_remote_bare_repo``),
        so readiness must not require the path to exist yet.
        """
        if self._config.repo_url.lower().startswith("file://"):
            return True
        return self._check_remote_catalog_health()

    def _check_remote_catalog_health(self) -> bool:
        """Probe HTTPS/HTTP catalog remotes with ``git ls-remote``."""
        remote_url = self._config.catalog_repo_url()
        git_cli = git.cmd.Git()
        try:
            if self._config.command_timeout is not None:
                git_cli.ls_remote(remote_url, kill_after_timeout=self._config.command_timeout)
            else:
                git_cli.ls_remote(remote_url)
        except GitCommandError as exc:
            detail = redact_url_userinfo(format_git_error_detail(exc))
            if is_soft_git_error(exc):
                logger.debug("Catalog remote health check: remote not found (%s)", detail)
            else:
                logger.warning("Catalog remote health check failed: %s", detail)
            return False
        return True

    async def _run_in_executor(self, func: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
        loop = asyncio.get_running_loop()
        otel_ctx = context.get_current()

        def _wrapper() -> T:
            token = context.attach(otel_ctx)
            try:
                return func(*args, **kwargs)
            finally:
                context.detach(token)

        return await loop.run_in_executor(self._executor, _wrapper)

    @override
    async def _create_or_update(self, arc_id: str, arc: ARC, *, rdi: str) -> None:
        """Per-ARC Git sync is unused; catalog publish happens in ``finalize``."""
        logger.debug(
            "Ignoring create_or_update for consolidated catalog store (arc_id=%s, rdi=%s)",
            arc_id,
            rdi,
        )

    @override
    async def _get(self, arc_id: str) -> ARC | None:
        """Per-ARC get is unsupported for the catalog backend."""
        return None

    @override
    async def _delete(self, arc_id: str) -> None:
        """Per-ARC delete is a no-op for the catalog backend."""
        return

    @override
    async def _exists(self, arc_id: str) -> bool:
        """Per-ARC exists is unsupported; always False."""
        return False

    def _ensure_remote_bare_repo(self) -> None:
        """Create a local bare remote for file:// catalog URLs when missing."""
        url = self._config.repo_url
        if not url.lower().startswith("file://"):
            return
        parsed = urlparse(url)
        remote_path = Path(unquote(parsed.path))
        if remote_path.exists():
            return
        logger.info("Creating bare catalog remote at %s", remote_path)
        remote_path.parent.mkdir(parents=True, exist_ok=True)
        Repo.init(remote_path, bare=True)

    def _context_config(self, local_path: Path) -> GitContextConfig:
        return self._config.git_context_config(repo_url=self._config.repo_url, local_path=local_path)

    def _publish_catalog_bytes(self, rdi: str, catalog_bytes: bytes) -> bool:
        """Clone into a temp dir, write catalog file, push if bytes differ. Returns True if pushed."""
        _require_safe_catalog_rdi(rdi)
        self._config.cache_dir.mkdir(parents=True, exist_ok=True)
        temp_dir = Path(tempfile.mkdtemp(prefix="catalog_finalize_", dir=self._config.cache_dir))
        try:
            self._ensure_remote_bare_repo()
            filename = f"{rdi}.json"
            with GitContext(self._context_config(temp_dir)) as git_ctx:
                target = Path(git_ctx.path) / filename
                if target.exists() and target.read_bytes() == catalog_bytes:
                    logger.info("Catalog %s unchanged; skipping commit/push", filename)
                    return False
                target.write_bytes(catalog_bytes)
                try:
                    git_ctx.commit_and_push(f"Update {filename}")
                except GitCommandError as exc:
                    detail = redact_url_userinfo(format_git_error_detail(exc))
                    if is_transient_git_error(exc):
                        raise ArcStoreTransientError(detail) from exc
                    if is_soft_git_error(exc):
                        raise ArcStoreError(detail) from exc
                    raise ArcStoreError(f"Git failure publishing {filename}: {detail}") from exc
                return True
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @override
    async def _finalize(self, *, rdi: str) -> bool:
        """Rebuild ``{rdi}.json`` from CouchDB ARC bodies (streamed, Dataset-only retained)."""
        datasets: list[CatalogDatasetRecord] = []
        async for arc_id, content in self._doc_store.iter_arc_contents_by_rdi(rdi):
            try:
                datasets.append(extract_catalog_dataset(content))
            except ValueError as exc:
                raise ArcStoreError(f"Catalog extraction failed for ARC {arc_id}: {exc}") from exc

        catalog_bytes = serialize_catalog_file(datasets)
        try:
            pushed = await self._run_in_executor(self._publish_catalog_bytes, rdi, catalog_bytes)
        except ArcStoreTransientError:
            raise
        except ArcStoreError:
            raise
        except Exception as exc:
            raise ArcStoreError(f"Failed to publish catalog for RDI {rdi}: {exc}") from exc

        logger.info("Finalized catalog for RDI %s (%d datasets, pushed=%s)", rdi, len(datasets), pushed)
        return pushed
