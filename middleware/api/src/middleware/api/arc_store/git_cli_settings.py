"""Shared Git CLI settings for GitRepo and ConsolidatedGit ArcStore backends."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Annotated
from urllib.parse import quote, urlparse

from pydantic import BaseModel, Field, SecretStr, field_validator

_GIT_URL_SCHEMES = ("https://", "file://", "http://")


def _default_git_cache_dir() -> Path:
    return Path(tempfile.gettempdir()) / "middleware_git_cache"


class GitContextConfig(BaseModel):
    """Configuration for a specific GitContext clone operation."""

    repo_url: SecretStr
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
        """Ensure a git remote URL uses HTTP, HTTPS, or FILE."""
        if not value.lower().startswith(_GIT_URL_SCHEMES):
            msg = f"Git URL must start with one of: {_GIT_URL_SCHEMES}"
            raise ValueError(msg)
        return value

    @field_validator("cache_dir", mode="before")
    @classmethod
    def normalize_cache_dir(cls, value: Path | str | None) -> Path | str:
        """Accept omitted/null YAML and coerce strings before validation."""
        if value is None:
            return _default_git_cache_dir()
        return value

    def authenticated_repo_url(self, url: str) -> str:
        """Return *url* with optional oauth2 token embedded for HTTPS remotes."""
        if self.token is None:
            return url
        token = self.token.get_secret_value()
        if not token:
            return url
        if urlparse(url).username is not None:
            return url
        # Escape the full userinfo token (default quote() leaves "/" unescaped).
        safe_token = quote(token, safe="")
        lower = url.lower()
        if lower.startswith("https://"):
            return f"https://oauth2:{safe_token}@{url[8:]}"
        if lower.startswith("http://"):
            return f"http://oauth2:{safe_token}@{url[7:]}"
        return url

    def git_context_config(self, *, repo_url: str, local_path: Path) -> GitContextConfig:
        """Build runtime ``GitContext`` settings from shared CLI options."""
        return GitContextConfig(
            repo_url=SecretStr(self.authenticated_repo_url(repo_url)),
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
    unset_fields = backend.model_fields_set
    shared_updates = {
        field: value for field, value in shared.model_dump(exclude_unset=True).items() if field not in unset_fields
    }
    if not shared_updates:
        return backend
    return backend.model_copy(update=shared_updates)
