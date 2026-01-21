"""Implements an ArcStore using local Git CLI (via GitPython) as backend."""

import asyncio
import concurrent.futures
import http
import logging
import shutil
import tempfile
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, TypeVar
from urllib.parse import quote

import git.cmd
from arctrl import ARC  # type: ignore[import-untyped]
from git import Repo
from git.exc import GitCommandError
from opentelemetry import trace
from pydantic import BaseModel, Field, SecretStr, field_validator

from . import ArcStore

logger = logging.getLogger(__name__)


class GitRepoConfig(BaseModel):
    """Configuration for Git CLI based ArcStore."""

    url: Annotated[str, Field(description="Base URL of the git server (e.g. https://gitlab.com)")]
    group: Annotated[str, Field(description="The group/namespace the ARC repos belong to")]
    branch: Annotated[str, Field(description="The git branch to use for ARC repos")] = "main"
    token: Annotated[SecretStr | None, Field(description="Auth token (for HTTPS auth)")] = None
    user_name: Annotated[str, Field(description="Git user.name")] = "Middleware API"
    user_email: Annotated[str, Field(description="Git user.email")] = "middleware@fairagro.net"
    max_workers: Annotated[int, Field(description="Max threads for git operations")] = 5
    command_timeout: Annotated[float | None, Field(description="Timeout (s) for git commands")] = None
    http_low_speed_limit: Annotated[int | None, Field(description="http.lowSpeedLimit in bytes/sec")] = None
    http_low_speed_time: Annotated[int | None, Field(description="http.lowSpeedTime in seconds")] = None
    cache_dir: Annotated[
        Path,
        Field(
            description="Local directory to cache git repos.",
            validate_default=True,
        ),
    ] = None  # type: ignore[assignment]

    @field_validator("url")
    @classmethod
    def validate_url_scheme(cls, v: str) -> str:
        """Ensure URL uses HTTP, HTTPS or FILE (for tests)."""
        valid_schemes = ("https://", "file://", "http://")
        if not v.lower().startswith(valid_schemes):
            msg = f"Git URL must start with one of: {valid_schemes}"
            raise ValueError(msg)
        return v

    @field_validator("cache_dir", mode="before")
    @classmethod
    def set_default_cache_dir(cls, v: Path | str | None) -> Path | str:
        """Set default cache dir if None."""
        if v is None:
            return Path(tempfile.gettempdir()) / "middleware_git_cache"
        return v


class GitContextConfig(BaseModel):
    """Configuration for a specific GitContext."""

    repo_url: SecretStr
    branch: str
    user_name: str | None
    user_email: str | None
    local_path: Path
    command_timeout: float | None = None
    http_low_speed_limit: int | None = None
    http_low_speed_time: int | None = None


_T = TypeVar("_T")


class GitContext:
    """Context manager for handling a git repository clone."""

    def __init__(self, config: GitContextConfig) -> None:
        """Initialize GitContext."""
        self.config = config
        self.repo: Repo | None = None
        self._tracer = trace.get_tracer(__name__)

    def _run_git_command(self, action: str, func: Callable[..., _T], *args: object, **kwargs: object) -> _T:
        """Run a git command with optional timeout and duration logging."""
        if self.config.command_timeout is not None:
            kwargs.setdefault("kill_after_timeout", self.config.command_timeout)

        with self._tracer.start_as_current_span(
            f"git.{action}",
            attributes={"git.action": action},
        ) as span:
            try:
                result = func(*args, **kwargs)
                logger.info("Git %s succeeded", action)
                return result
            except GitCommandError as exc:  # pragma: no cover - behavior validated indirectly
                status = getattr(exc, "status", None)
                status_msg = f" (status {status})" if status is not None else ""
                logger.warning("Git %s failed%s: %s", action, status_msg, exc)
                span.record_exception(exc)
                raise

    def _apply_repo_config(self) -> None:
        """Apply user and HTTP tuning to the repository config."""
        if not self.repo:
            return

        with self.repo.config_writer() as cw:
            if self.config.user_name:
                cw.set_value("user", "name", self.config.user_name)
            if self.config.user_email:
                cw.set_value("user", "email", self.config.user_email)
            if self.config.http_low_speed_limit is not None:
                cw.set_value("http", "lowSpeedLimit", str(self.config.http_low_speed_limit))
            if self.config.http_low_speed_time is not None:
                cw.set_value("http", "lowSpeedTime", str(self.config.http_low_speed_time))

    def _ensure_path(self) -> Path:
        repo_path = self.config.local_path
        if not repo_path.parent.exists():
            repo_path.parent.mkdir(parents=True, exist_ok=True)
        return repo_path

    def _sync_existing_repo(self, repo_path: Path, url: str) -> None:
        self.repo = Repo(repo_path)
        if "origin" in self.repo.remotes:
            self.repo.remotes.origin.set_url(url)
        else:
            self.repo.create_remote("origin", url)

        try:
            self._run_git_command("fetch", self.repo.remotes.origin.fetch)
            remote_ref = f"origin/{self.config.branch}"
            self._run_git_command("reset", self.repo.git.reset, "--hard", remote_ref)
        except GitCommandError:
            logger.warning("Failed to sync repo at %s. Assuming clean state needed.", repo_path)

    def _handle_repo_init_error(self, repo_path: Path, url: str) -> None:
        if not (repo_path / ".git").exists():
            logger.info("Clone failed. Initializing new repo at %s", repo_path)
            self.repo = Repo.init(repo_path)
            self.repo.create_remote("origin", url)
            # Create a detached head if branch doesn't exist yet (e.g. empty repo)
            # We don't need to force HEAD creation if it fails, just init is enough
            try:
                self.repo.git.checkout("-b", self.config.branch)
            except GitCommandError as e:
                # If branch already exists or other git error, log and continue
                logger.debug("Could not create new branch '%s': %s", self.config.branch, e)
            except (OSError, ValueError, IndexError, AttributeError) as e:
                logger.warning("Unexpected error during repo init checkout: %s", e)
        elif not self.repo:
            self.repo = Repo(repo_path)

    def __enter__(self) -> "GitContext":
        """Enter context: clone or init repo."""
        repo_path = self._ensure_path()
        url = self.config.repo_url.get_secret_value()

        logger.debug("Accessing repo at %s", repo_path)
        try:
            if (repo_path / ".git").exists():
                self._sync_existing_repo(repo_path, url)
            else:
                self.repo = self._run_git_command(
                    "clone",
                    Repo.clone_from,
                    url,
                    repo_path,
                    branch=self.config.branch,
                )
        except GitCommandError:
            self._handle_repo_init_error(repo_path, url)

        # Configure user
        self._apply_repo_config()

        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        """Exit context."""
        if self.repo:
            self.repo.close()

    @property
    def path(self) -> str:
        """Return the path to the repository directory."""
        return str(self.config.local_path)

    def commit_and_push(self, message: str) -> None:
        """Add all changes, commit and push."""
        if not self.repo:
            msg = "Repository not initialized"
            raise RuntimeError(msg)

        with self._tracer.start_as_current_span("git.commit_and_push") as span:
            # Check if dirty or untracked files exist
            if not self.repo.is_dirty(untracked_files=True):
                logger.info("No changes to commit.")
                span.set_attribute("git.dirty", False)
                return

            span.set_attribute("git.dirty", True)

            with self._tracer.start_as_current_span("git.add"):
                self.repo.git.add(A=True)

            with self._tracer.start_as_current_span("git.commit"):
                self.repo.index.commit(message)

            logger.info("Pushing changes to remote branch %s", self.config.branch)
            self._run_git_command("push", self.repo.remotes.origin.push, self.config.branch)


class GitRepo(ArcStore):
    """Implements an ArcStore using Git CLI (GitPython) as backend."""

    def __init__(self, config: GitRepoConfig) -> None:
        """Initialize GitRepo."""
        super().__init__()
        self._config = config
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=self._config.max_workers)

    def _check_health(self) -> bool:
        """Check connection to the storage backend."""
        url = self._config.url

        # Check for file:// scheme used in integration tests
        if url.lower().startswith("file://"):
            logger.debug("Skipping health check for file:// URL: %s", url)
            return True

        try:
            # Set a short timeout, disable bandit check, as we've already validated the URL
            with urllib.request.urlopen(url, timeout=5) as response:  # nosec B310
                if response.status >= http.HTTPStatus.BAD_REQUEST:
                    logger.error("Git server check failed: %s returned status %s", url, response.status)
                    return False
                logger.debug("Git server check passed: %s returned status %s", url, response.status)
                return True
        except urllib.error.HTTPError as e:
            logger.exception("Git server check failed: %s returned HTTP error %s: %s", url, e.code, e.reason)
        except urllib.error.URLError as e:
            logger.exception("Git server check failed: %s is unreachable. Reason: %s", url, e.reason)
        except TimeoutError:
            logger.exception("Git server check failed: %s timed out", url)
        except Exception:  # pylint: disable=broad-exception-caught
            logger.exception("Git server check failed: %s caused unexpected error", url)

        return False

    def _get_repo_url(self, arc_id: str) -> str:
        # Construct URL: base/group/arc_id.git
        base = self._config.url.rstrip("/")
        group = self._config.group.strip("/")
        return f"{base}/{group}/{arc_id}.git"

    def _get_authenticated_url(self, repo_url: str) -> str:
        """Inject auth token into URL if present."""
        if self._config.token:
            token = quote(self._config.token.get_secret_value())
            if repo_url.startswith("https://"):
                clean = repo_url.replace("https://", "")
                return f"https://oauth2:{token}@{clean}"
            if repo_url.startswith("http://"):
                clean = repo_url.replace("http://", "")
                return f"http://oauth2:{token}@{clean}"
        return repo_url

    def _get_context_config(self, arc_id: str) -> GitContextConfig:
        repo_url = self._get_repo_url(arc_id)
        auth_url = self._get_authenticated_url(repo_url)

        # cache_dir is guaranteed to be a Path by Pydantic validation
        local_path = self._config.cache_dir / arc_id

        return GitContextConfig(
            repo_url=SecretStr(auth_url),
            branch=self._config.branch,
            user_name=self._config.user_name,
            user_email=self._config.user_email,
            local_path=local_path,
            command_timeout=self._config.command_timeout,
            http_low_speed_limit=self._config.http_low_speed_limit,
            http_low_speed_time=self._config.http_low_speed_time,
        )

    async def _create_or_update(self, arc_id: str, arc: ARC) -> None:
        """Create or update ARC using Git CLI."""
        logger.debug("Creating/updating ARC %s via Git CLI", arc_id)
        loop = asyncio.get_running_loop()

        def _task() -> None:
            with self._tracer.start_as_current_span(
                "git_repo.create_or_update",
                attributes={"arc_id": arc_id},
            ) as span:
                ctx_config = self._get_context_config(arc_id)
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
                        with self._tracer.start_as_current_span("arc.write"):
                            arc.Write(str(repo_path))

                        # Commit and push
                        ctx.commit_and_push(f"Update ARC {arc_id}")
                except GitCommandError as e:
                    span.record_exception(e)
                    # Try to diagnose connection issues
                    self.check_health()
                    raise
                except Exception as e:
                    span.record_exception(e)
                    raise

        await loop.run_in_executor(self._executor, _task)

    async def _get(self, arc_id: str) -> ARC | None:
        """Get ARC from Git."""
        loop = asyncio.get_running_loop()

        def _task() -> ARC | None:
            with self._tracer.start_as_current_span(
                "git_repo.get",
                attributes={"arc_id": arc_id},
            ) as span:
                ctx_config = self._get_context_config(arc_id)
                try:
                    with GitContext(ctx_config) as ctx:
                        if not ctx.repo:
                            span.set_attribute("found", False)
                            return None
                        span.set_attribute("git.local_path", str(ctx.path))
                        try:
                            with self._tracer.start_as_current_span("arc.load"):
                                arc = ARC.load(ctx.path)
                            span.set_attribute("found", arc is not None)
                            return arc
                        except (FileNotFoundError, OSError) as e:
                            logger.warning("File system error loading ARC from repo %s: %s", arc_id, e)
                            span.record_exception(e)
                            return None
                        except Exception as e:  # pylint: disable=broad-exception-caught # noqa: BLE001
                            logger.warning(
                                "Failed to load ARC from repo %s (might not be an ARC or invalid): %s",
                                arc_id,
                                e,
                            )
                            span.record_exception(e)
                            return None
                except GitCommandError as e:
                    logger.debug("Failed to clone/access repo for %s: %s", arc_id, e)
                    span.record_exception(e)
                    return None

        return await loop.run_in_executor(self._executor, _task)

    async def _delete(self, arc_id: str) -> None:
        """Delete ARC (Not supported via Git CLI easily without platform API)."""
        logger.warning(
            "Delete operation is not supported by GitRepo (CLI backend). Manual deletion required for %s",
            arc_id,
        )

    async def _exists(self, arc_id: str) -> bool:
        """Check if ARC repo exists."""
        loop = asyncio.get_running_loop()

        def _task() -> bool:
            with self._tracer.start_as_current_span(
                "git_repo.exists",
                attributes={"arc_id": arc_id},
            ) as span:
                # We can try to ls-remote
                repo_url = self._get_repo_url(arc_id)
                span.set_attribute("git.repo_url", repo_url)

                # Inject token for ls-remote check
                url = self._get_authenticated_url(repo_url)

                g = git.cmd.Git()
                try:
                    with self._tracer.start_as_current_span("git.ls-remote"):
                        if self._config.command_timeout is not None:
                            g.ls_remote(url, kill_after_timeout=self._config.command_timeout)
                        else:
                            g.ls_remote(url)
                    logger.info("Git ls-remote for %s succeeded", arc_id)
                    span.set_attribute("exists", True)
                    return True
                except GitCommandError as e:
                    logger.warning("Git ls-remote for %s failed", arc_id)
                    span.set_attribute("exists", False)
                    span.record_exception(e)
                    return False

        return await loop.run_in_executor(self._executor, _task)
