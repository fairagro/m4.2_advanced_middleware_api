"""Shared GitContext and Git error helpers for git-based ArcStore backends."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from types import TracebackType
from typing import ParamSpec, TypeVar

from git import Repo
from git.exc import GitCommandError
from opentelemetry import trace
from opentelemetry.trace import Span

from middleware.api.arc_store import ArcStoreTransientError
from middleware.api.arc_store.git_cli_settings import GitContextConfig
from middleware.shared.security.url_redact import redact_url_userinfo

logger = logging.getLogger(__name__)

P = ParamSpec("P")
_T = TypeVar("_T")


def format_git_error_detail(exc: GitCommandError) -> str:
    """Prefer concise stderr for messages (URL credentials are redacted at sinks)."""
    stderr = str(getattr(exc, "stderr", "") or "").strip()
    return stderr or str(exc).strip()


def record_git_span_failure(span: Span, detail: str, *, expected: bool = False) -> None:
    """Record a git failure on a span without exporting URL userinfo credentials.

    Prefer this over ``span.record_exception(GitCommandError)``: exception
    payloads and unredacted status descriptions can leak oauth2 tokens to
    tracing backends. Logging remains covered by the central redacting formatter.
    """
    safe = redact_url_userinfo(detail)
    if expected:
        span.add_event("git.expected_failure", attributes={"stderr": safe})
        span.set_status(trace.Status(trace.StatusCode.OK))
    else:
        span.add_event("git.failure", attributes={"stderr": safe})
        span.set_status(trace.Status(trace.StatusCode.ERROR, safe))


def is_soft_git_error(exc: GitCommandError) -> bool:
    """Check if a GitCommandError looks like a missing remote/repo/branch (404-ish).

    Whether that outcome is *expected* depends on the git action — see
    :data:`_ACTIONS_WITH_EXPECTED_SOFT_ERRORS`.
    """
    stderr = str(getattr(exc, "stderr", ""))
    # Common messages for missing repo or branch
    soft_patterns = [
        "not found",
    ]
    return any(p in stderr.lower() for p in soft_patterns)


# Soft "not found" is a normal probe/init outcome only for these actions.
# For push/fetch/reset it usually means misconfiguration and must stay ERROR in traces.
_ACTIONS_WITH_EXPECTED_SOFT_ERRORS = frozenset({"ls-remote", "clone"})


def is_transient_git_error(exc: GitCommandError) -> bool:
    """Check if a GitCommandError is retryable (network or concurrent push conflict).

    Concurrent non-fast-forward / fetch-first pushes are transient under
    last-successful-push semantics: Celery retry re-clones from remote and
    rebuilds from CouchDB.

    Do not match generic phrases like ``failed to push some refs`` or
    ``updates were rejected`` — those also appear on permanent failures
    (protected branch, hook rejection, permission denied).
    """
    stderr = str(getattr(exc, "stderr", "")).lower()
    transient_patterns = [
        # Network / availability
        "could not resolve host",
        "failed to connect",
        "connection refused",
        "503 service unavailable",
        "502 bad gateway",
        "connection timed out",
        "unexpected disconnect",
        "early eof",
        "the requested url returned error: 50",
        # Concurrent push only (not generic push rejection wrappers)
        "non-fast-forward",
        "fetch first",
    ]
    return any(p in stderr for p in transient_patterns)


class GitContext:
    """Context manager for handling a git repository clone."""

    def __init__(self, config: GitContextConfig) -> None:
        """Initialize GitContext."""
        self.config = config
        self.repo: Repo | None = None
        self._tracer = trace.get_tracer(__name__)

    def _run_git_command(self, action: str, func: Callable[P, _T], *args: P.args, **kwargs: P.kwargs) -> _T:
        """Run a git command with optional timeout and duration logging."""
        if self.config.command_timeout is not None:
            kwargs.setdefault("kill_after_timeout", self.config.command_timeout)

        with self._tracer.start_as_current_span(
            f"api.GitContext._run_git_command:{action}",
            attributes={"git.action": action},
            set_status_on_exception=False,
        ) as span:
            try:
                result = func(*args, **kwargs)
                logger.debug("Git %s succeeded", action)
                return result
            except GitCommandError as exc:  # pragma: no cover - behavior validated indirectly
                detail = format_git_error_detail(exc)
                safe_detail = redact_url_userinfo(detail)
                if is_soft_git_error(exc) and action in _ACTIONS_WITH_EXPECTED_SOFT_ERRORS:
                    # Soft 404 on ls-remote / clone is expected (probe or first-time remote).
                    level = logging.DEBUG if action == "ls-remote" else logging.INFO
                    logger.log(level, "Git %s failed as expected: %s", action, safe_detail)
                    record_git_span_failure(span, detail, expected=True)
                elif is_soft_git_error(exc):
                    # Same stderr pattern on push/fetch/reset is an operational failure.
                    logger.warning("Git %s failed (missing remote/ref): %s", action, safe_detail)
                    record_git_span_failure(span, detail)
                elif is_transient_git_error(exc):
                    status = getattr(exc, "status", None)
                    status_msg = f" (status {status})" if status is not None else ""
                    logger.info("Git %s failed with transient error%s: %s", action, status_msg, safe_detail)
                    record_git_span_failure(span, detail)
                    raise ArcStoreTransientError(f"Transient Git error during {action}: {safe_detail}") from exc
                else:
                    status = getattr(exc, "status", None)
                    status_msg = f" (status {status})" if status is not None else ""
                    logger.warning("Git %s failed%s: %s", action, status_msg, safe_detail)
                    record_git_span_failure(span, detail)
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

    def __enter__(self) -> GitContext:
        """Enter context: clone or init repo."""
        repo_path = self._ensure_path()
        url = self.config.repo_url.unredacted()

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
                    depth=1,
                )
        except GitCommandError:
            self._handle_repo_init_error(repo_path, url)

        # Configure user
        self._apply_repo_config()

        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit context."""
        if self.repo:
            self.repo.close()

    @property
    def path(self) -> str:
        """Path to the repository directory."""
        return str(self.config.local_path)

    def commit_and_push(self, message: str) -> None:
        """Add all changes, commit and push."""
        if not self.repo:
            msg = "Repository not initialized"
            raise RuntimeError(msg)

        with self._tracer.start_as_current_span("api.GitContext.commit_and_push") as span:
            # Check if dirty or untracked files exist
            if not self.repo.is_dirty(untracked_files=True):
                logger.info("No changes to commit.")
                span.set_attribute("git.dirty", False)
                return

            span.set_attribute("git.dirty", True)

            with self._tracer.start_as_current_span("api.GitContext.commit_and_push:add"):
                self.repo.git.add(A=True)

            with self._tracer.start_as_current_span("api.GitContext.commit_and_push:commit"):
                self.repo.index.commit(message)

            logger.info("Pushing changes to remote branch %s", self.config.branch)
            self._run_git_command("push", self.repo.remotes.origin.push, self.config.branch)
