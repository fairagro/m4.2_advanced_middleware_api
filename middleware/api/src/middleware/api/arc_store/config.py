"""Configuration models for ARC store components."""

import tempfile
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, Field, SecretStr, field_validator


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
