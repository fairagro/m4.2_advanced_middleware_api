"""Configuration for the consolidated Git ArcStore backend."""

import tempfile
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator

from middleware.api.arc_store.git_cli_settings import GitCliSettings
from middleware.shared.security import UrlStr


def _default_catalog_git_cache_dir() -> Path:
    return Path(tempfile.gettempdir()) / "middleware_catalog_git_cache"


class ConsolidatedGitConfig(GitCliSettings):
    """Shared-repo catalog backend: one Git remote, ``{rdi}.json`` files."""

    repo_url: Annotated[
        str,
        Field(description="Full Git URL of the shared catalog repository (HTTPS or file://)"),
    ]
    cache_dir: Annotated[
        Path,
        Field(
            description="Local directory for ephemeral catalog finalize clones",
            validate_default=True,
        ),
    ] = Field(default_factory=_default_catalog_git_cache_dir)
    finalize_lock_wait_timeout_s: Annotated[
        float,
        Field(
            default=60.0,
            ge=0.1,
            description="Max seconds to wait for per-RDI catalog finalize single-flight lock",
        ),
    ] = 60.0

    @field_validator("repo_url")
    @classmethod
    def validate_repo_url_scheme(cls, value: str) -> str:
        """Ensure catalog repo URL uses HTTP, HTTPS or FILE."""
        return GitCliSettings.validate_git_url_scheme(value)

    def catalog_repo_url(self) -> UrlStr:
        """Return the authenticated URL for the shared catalog remote."""
        return self.authenticated_repo_url(self.repo_url)
