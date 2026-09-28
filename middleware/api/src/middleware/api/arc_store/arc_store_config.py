"""Preferred ``arc_store`` / ``consolidated_store`` configuration blocks."""

from enum import StrEnum
from typing import Annotated, ClassVar, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from middleware.api.arc_store.consolidated_git.config import ConsolidatedGitConfig
from middleware.api.arc_store.git_cli_settings import GitCliSettings
from middleware.api.arc_store.git_repo.config import GitRepoConfig
from middleware.api.arc_store.gitlab_api.store import GitlabApiConfig


class ArcStoreBackendType(StrEnum):
    """Configured per-ARC ArcStore implementation."""

    GIT_REPO = "git_repo"
    GITLAB_API = "gitlab_api"


class ArcStoreConfig(BaseModel):
    """Required per-ARC ArcStore slot.

    Backend is selected by which nested settings key is set (``git_repo`` or
    deprecated ``gitlab_api``) — no separate ``type`` field.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    git: Annotated[
        GitCliSettings | None,
        Field(
            description=(
                "Shared Git CLI settings (branch, token, user_name, cache_dir, …) "
                "merged into git_repo when not set there"
            ),
        ),
    ] = None
    git_repo: Annotated[
        GitRepoConfig | None,
        Field(description="Per-ARC GitRepo backend settings (selects git_repo backend)"),
    ] = None
    gitlab_api: Annotated[
        GitlabApiConfig | None,
        Field(description="Deprecated GitLab API backend settings (selects gitlab_api backend)"),
    ] = None

    @model_validator(mode="after")
    def exactly_one_backend(self) -> Self:
        """Require exactly one of ``git_repo`` or ``gitlab_api``."""
        has_git_repo = self.git_repo is not None
        has_gitlab_api = self.gitlab_api is not None
        if has_git_repo == has_gitlab_api:
            raise ValueError("arc_store must set exactly one of 'git_repo' or 'gitlab_api'")
        return self


class ConsolidatedStoreConfig(BaseModel):
    """Optional consolidated catalog slot (``consolidated_store``).

    The slot name selects the catalog backend; nested settings live under
    ``consolidated_git`` (no separate ``type`` field).
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    git: Annotated[
        GitCliSettings | None,
        Field(
            description=(
                "Shared Git CLI settings (branch, token, user_name, cache_dir, …) "
                "merged into consolidated_git when not set there"
            ),
        ),
    ] = None
    consolidated_git: Annotated[
        ConsolidatedGitConfig,
        Field(description="Shared-repo consolidated catalog backend settings"),
    ]
