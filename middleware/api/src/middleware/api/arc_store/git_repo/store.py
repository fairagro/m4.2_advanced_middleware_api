"""Implements an ArcStore using local Git CLI (via GitPython) as backend."""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import ParamSpec, TypeVar

import git.cmd
from arctrl import ARC  # type: ignore[import-untyped]
from git.exc import GitCommandError
from opentelemetry import context, trace

from middleware.api.arc_store import ArcStore
from middleware.api.arc_store.git_cache_cleanup import GIT_REPO_SYNC_PREFIX, reclaim_stale_git_cache_dirs
from middleware.api.arc_store.git_cli_settings import GitContextConfig
from middleware.api.arc_store.git_context import (
    GitContext,
    format_git_error_detail,
    is_soft_git_error,
    record_git_span_failure,
)
from middleware.api.arc_store.git_repo.config import GitRepoConfig
from middleware.api.arc_store.git_repo.remote_git_provider import (
    RemoteGitProvider,
    git_project_metadata_from_arc,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")
P = ParamSpec("P")


def _cleanup_workdir(local_path: Path) -> None:
    if not local_path.exists():
        return
    try:
        shutil.rmtree(local_path)
    except OSError as e:
        logger.warning("Failed to clean up local path %s: %s", local_path, e)


class GitRepo(ArcStore):
    """Implements an ArcStore using Git CLI (GitPython) as backend."""

    def __init__(self, config: GitRepoConfig) -> None:
        """Initialize GitRepo."""
        super().__init__()
        self._config = config
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=self._config.max_workers)

        # Initialize RemoteGitProvider
        token = self._config.token.get_secret_value() if self._config.token else None
        self._remote_provider = RemoteGitProvider.from_url(
            url=self._config.url,
            group=self._config.group,
            token=token,
        )
        reclaim_stale_git_cache_dirs(self._config.cache_dir)

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

    async def shutdown(self) -> None:
        """Shut down the thread-pool executor, cancelling any pending futures."""
        self._executor.shutdown(wait=False, cancel_futures=True)
        logger.debug("GitRepo thread-pool executor shut down")

    def _check_health(self) -> bool:
        """Check connection to the storage backend."""
        return self._remote_provider.check_health()

    def _allocate_workdir(self) -> Path:
        """Create a unique ephemeral working directory under ``cache_dir``."""
        self._config.cache_dir.mkdir(parents=True, exist_ok=True)
        return Path(tempfile.mkdtemp(prefix=GIT_REPO_SYNC_PREFIX, dir=self._config.cache_dir))

    def _get_context_config(self, arc_id: str, local_path: Path) -> GitContextConfig:
        repo_url = self._remote_provider.get_repo_url(arc_id, authenticated=False)
        return self._config.git_context_config(
            repo_url=repo_url.unredacted(),
            local_path=local_path,
        )

    async def _create_or_update(
        self,
        arc_id: str,
        arc: ARC,
        *,
        rdi: str,
    ) -> None:
        """Create or update ARC using Git CLI."""
        logger.debug("Creating/updating ARC %s via Git CLI", arc_id)

        def _task() -> None:
            with self._tracer.start_as_current_span(
                "api.GitRepo._create_or_update",
                attributes={"arc_id": arc_id, "rdi": rdi},
                set_status_on_exception=False,
            ) as span:
                reclaim_stale_git_cache_dirs(self._config.cache_dir)
                # Ensure remote exists before doing anything else (if manager is configured)
                git_metadata = git_project_metadata_from_arc(
                    arc,
                    rdi,
                    arc_id=arc_id,
                    rdi_gitlab_topics=self._config.rdi_gitlab_topics,
                )
                self._remote_provider.ensure_repo_exists(arc_id, metadata=git_metadata)

                local_path = self._allocate_workdir()
                ctx_config = self._get_context_config(arc_id, local_path)
                try:
                    with GitContext(ctx_config) as ctx:
                        if not ctx.repo:
                            msg = "Failed to initialize git repo"
                            raise RuntimeError(msg)

                        repo_path = Path(ctx.path)
                        span.set_attribute("git.local_path", str(repo_path))

                        # Cleanup existing files (except .git) to ensure sync with ARC object
                        for child in repo_path.iterdir():
                            if child.name == ".git":
                                continue
                            if child.is_dir():
                                shutil.rmtree(child)
                            else:
                                child.unlink()

                        # Write ARC to repo path
                        with self._tracer.start_as_current_span("api.GitRepo._create_or_update:arc_write"):
                            arc.Write(str(repo_path))

                        # Commit and push
                        ctx.commit_and_push(f"Update ARC {arc_id}")
                except GitCommandError as e:
                    detail = format_git_error_detail(e)
                    # Soft "not found" during create/update is not expected (clone soft is
                    # swallowed in GitContext.__enter__; remaining failures are often push).
                    record_git_span_failure(span, detail)
                    # Try to diagnose connection issues
                    self._check_health()
                    raise
                finally:
                    _cleanup_workdir(local_path)

        await self._run_in_executor(_task)

    async def _get(self, arc_id: str) -> ARC | None:
        """Get ARC from Git."""

        def _task() -> ARC | None:
            with self._tracer.start_as_current_span(
                "api.GitRepo._get",
                attributes={"arc_id": arc_id},
                set_status_on_exception=False,
            ) as span:
                reclaim_stale_git_cache_dirs(self._config.cache_dir)
                local_path = self._allocate_workdir()
                ctx_config = self._get_context_config(arc_id, local_path)
                try:
                    with GitContext(ctx_config) as ctx:
                        if not ctx.repo:
                            span.set_attribute("found", False)
                            return None
                        span.set_attribute("git.local_path", str(ctx.path))
                        try:
                            with self._tracer.start_as_current_span("api.GitRepo._get:arc_load"):
                                arc = ARC.load(ctx.path)
                            span.set_attribute("found", arc is not None)
                            return arc
                        except (FileNotFoundError, OSError) as e:
                            logger.warning("File system error loading ARC from repo %s: %s", arc_id, e)
                            span.record_exception(e)
                            return None
                except GitCommandError as e:
                    detail = format_git_error_detail(e)
                    if is_soft_git_error(e):
                        logger.debug("Failed to clone/access repo for %s: %s", arc_id, e)
                        record_git_span_failure(span, detail, expected=True)
                    else:
                        logger.warning("Failed to clone/access repo for %s: %s", arc_id, e)
                        record_git_span_failure(span, detail)
                    return None
                except Exception as e:  # pylint: disable=broad-exception-caught # noqa: BLE001
                    logger.warning(
                        "Failed to load ARC from repo %s (might not be an ARC or invalid): %s",
                        arc_id,
                        e,
                    )
                    span.record_exception(e)
                    return None
                finally:
                    _cleanup_workdir(local_path)

        return await self._run_in_executor(_task)

    async def _delete(self, arc_id: str) -> None:  # noqa: PLR6301
        """Delete ARC (Not supported via Git CLI easily without platform API)."""
        logger.warning(
            "Delete operation is not supported by GitRepo (CLI backend). Manual deletion required for %s",
            arc_id,
        )

    async def _exists(self, arc_id: str) -> bool:
        """Check if ARC repo exists."""

        def _task() -> bool:
            with self._tracer.start_as_current_span(
                "api.GitRepo._exists",
                attributes={"arc_id": arc_id},
                set_status_on_exception=False,
            ) as span:
                # We can try to ls-remote using the authenticated URL
                url = self._remote_provider.get_repo_url(arc_id, authenticated=True)
                span.set_attribute("git.repo_url", str(url))
                remote = url.unredacted()

                g = git.cmd.Git()
                try:
                    with self._tracer.start_as_current_span(
                        "api.GitRepo._exists:ls-remote",
                        set_status_on_exception=False,
                    ) as inner_span:
                        try:
                            if self._config.command_timeout is not None:
                                g.ls_remote(remote, kill_after_timeout=self._config.command_timeout)
                            else:
                                g.ls_remote(remote)
                            inner_span.set_status(trace.Status(trace.StatusCode.OK))
                        except GitCommandError as e:
                            detail = format_git_error_detail(e)
                            if is_soft_git_error(e):
                                record_git_span_failure(inner_span, detail, expected=True)
                            else:
                                record_git_span_failure(inner_span, detail)
                            raise

                    logger.info("Git ls-remote for %s succeeded", arc_id)
                    span.set_attribute("exists", True)
                    return True
                except GitCommandError as e:
                    detail = format_git_error_detail(e)
                    if is_soft_git_error(e):
                        logger.debug("Git ls-remote for %s failed (repo not found)", arc_id)
                        record_git_span_failure(span, detail, expected=True)
                    else:
                        logger.warning("Git ls-remote for %s failed: %s", arc_id, e)
                        record_git_span_failure(span, detail)
                    span.set_attribute("exists", False)
                    return False

        return await self._run_in_executor(_task)
