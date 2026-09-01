"""Shared Git CLI settings for GitRepo and ConsolidatedGit ArcStore backends."""

from __future__ import annotations

import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, cast
from urllib.parse import quote, urlparse

from pydantic import BaseModel, Field, SecretStr, field_validator

from middleware.shared.security import UrlStr

_GIT_URL_SCHEMES = ("https://", "file://", "http://")


def _default_git_cache_dir() -> Path:
    return Path(tempfile.gettempdir()) / "middleware_git_cache"


class GitContextConfig(BaseModel):
    """Configuration for a specific GitContext clone operation."""

    repo_url: UrlStr
    branch: str
    user_name: str | None
    user_email: str | None
    local_path: Path
    command_timeout: float | None = None
    http_low_speed_limit: int | None = None
    http_low_speed_time: int | None = None


class GitCliSettings(BaseModel):
    """Common GitPython / ``GitContext`` settings shared by git-based ArcStore backends."""

    branch: Annotated[str, Field(description="Git branch for commits and pushes")] = "main"
    token: Annotated[SecretStr | None, Field(description="Auth token for HTTPS remotes")] = None
    user_name: Annotated[str, Field(description="Git user.name")] = "Middleware API"
    user_email: Annotated[str, Field(description="Git user.email")] = "middleware@fairagro.net"
    max_workers: Annotated[int, Field(description="Max threads for git operations", ge=1)] = 5
    command_timeout: Annotated[float | None, Field(description="Timeout (s) for git commands")] = None
    http_low_speed_limit: Annotated[int | None, Field(description="http.lowSpeedLimit in bytes/sec")] = None
    http_low_speed_time: Annotated[int | None, Field(description="http.lowSpeedTime in seconds")] = None
    cache_dir: Annotated[
        Path,
        Field(
            description="Local directory for ephemeral git working clones",
            validate_default=True,
        ),
    ] = Field(default_factory=_default_git_cache_dir)

    @classmethod
    def validate_git_url_scheme(cls, value: str) -> str:
        """Ensure a git remote URL uses HTTP, HTTPS, or FILE without userinfo.

        Credentials must be supplied via the ``token`` field (``SecretStr``), not
        embedded in the URL, so config dumps cannot leak secrets as plain strings.
        """
        if not value.lower().startswith(_GIT_URL_SCHEMES):
            msg = f"Git URL must start with one of: {_GIT_URL_SCHEMES}"
            raise ValueError(msg)
        if urlparse(value).username is not None:
            msg = "Git URL must not embed credentials in userinfo; use the token field instead"
            raise ValueError(msg)
        return value

    @field_validator("cache_dir", mode="before")
    @classmethod
    def normalize_cache_dir(cls, value: Path | str | None) -> Path | str:
        """Accept omitted/null YAML; ``None`` uses this model's ``cache_dir`` default_factory."""
        if value is None:
            field_info = cls.model_fields.get("cache_dir")
            factory = field_info.default_factory if field_info is not None else None
            if not callable(factory):
                return _default_git_cache_dir()
            # Pydantic types default_factory as ``()`` or ``(data)``; ours are zero-arg.
            return cast(Callable[[], Path], factory)()
        return value

    def authenticated_repo_url(self, url: str) -> UrlStr:
        """Return *url* with optional oauth2 token embedded for HTTPS remotes."""
        if self.token is None:
            return UrlStr(url)
        token = self.token.get_secret_value()
        if not token:
            return UrlStr(url)
        if urlparse(url).username is not None:
            return UrlStr(url)
        # Escape the full userinfo token (default quote() leaves "/" unescaped).
        safe_token = quote(token, safe="")
        lower = url.lower()
        if lower.startswith("https://"):
            return UrlStr(f"https://oauth2:{safe_token}@{url[8:]}")
        if lower.startswith("http://"):
            return UrlStr(f"http://oauth2:{safe_token}@{url[7:]}")
        return UrlStr(url)

    def git_context_config(self, *, repo_url: str | UrlStr, local_path: Path) -> GitContextConfig:
        """Build runtime ``GitContext`` settings from shared CLI options."""
        base = repo_url.unredacted() if isinstance(repo_url, UrlStr) else repo_url
        return GitContextConfig(
            repo_url=self.authenticated_repo_url(base),
            branch=self.branch,
            user_name=self.user_name,
            user_email=self.user_email,
            local_path=local_path,
            command_timeout=self.command_timeout,
            http_low_speed_limit=self.http_low_speed_limit,
            http_low_speed_time=self.http_low_speed_time,
        )


def merge_git_cli_settings[TGitCli: GitCliSettings](backend: TGitCli, shared: GitCliSettings | None) -> TGitCli:
    """Apply ``arc_store.git`` defaults without overriding backend-specific fields."""
    if shared is None:
        return backend
    backend_set_fields = backend.model_fields_set
    shared_updates = {
        field: value
        for field, value in shared.model_dump(exclude_unset=True).items()
        if field not in backend_set_fields
    }
    if not shared_updates:
        return backend
    return backend.model_copy(update=shared_updates)
