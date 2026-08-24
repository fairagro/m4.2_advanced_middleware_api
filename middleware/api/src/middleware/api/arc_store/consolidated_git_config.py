"""Configuration for the consolidated Git ArcStore backend."""

import tempfile
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator

from .git_cli_settings import GitCliSettings


class ConsolidatedGitConfig(GitCliSettings):
    """Shared-repo catalog backend: one Git remote, ``{rdi}.json`` files."""

    repo_url: Annotated[
        str,
        Field(description="Full Git URL of the shared catalog repository (HTTPS or file://)"),
    ]

    @field_validator("repo_url")
    @classmethod
    def validate_repo_url_scheme(cls, value: str) -> str:
        """Ensure catalog repo URL uses HTTP, HTTPS or FILE."""
        return GitCliSettings.validate_git_url_scheme(value)

    @field_validator("cache_dir", mode="before")
    @classmethod
    def set_catalog_cache_dir(cls, value: Path | str | None) -> Path | str:
        """Default cache dir for ephemeral catalog finalize clones."""
        if value is None:
            return Path(tempfile.gettempdir()) / "middleware_catalog_git_cache"
        return value

    def catalog_repo_url(self) -> str:
        """Return the authenticated URL for the shared catalog remote."""
        return self.authenticated_repo_url(self.repo_url)
