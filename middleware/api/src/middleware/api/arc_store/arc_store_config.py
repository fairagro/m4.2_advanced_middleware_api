"""Preferred ``arc_store`` configuration block and backend type discriminator."""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from middleware.api.arc_store.consolidated_git.config import ConsolidatedGitConfig
from middleware.api.arc_store.git_cli_settings import GitCliSettings
from middleware.api.arc_store.git_repo.config import GitRepoConfig
from middleware.api.arc_store.gitlab_api.store import GitlabApiConfig


class ArcStoreBackendType(StrEnum):
    """Configured ArcStore implementation."""

    GIT_REPO = "git_repo"
    GITLAB_API = "gitlab_api"
    CONSOLIDATED_GIT = "consolidated_git"


class GitRepoArcStoreConfig(BaseModel):
    """ArcStore config when ``type`` is ``git_repo``."""

    type: Literal[ArcStoreBackendType.GIT_REPO] = ArcStoreBackendType.GIT_REPO
    git: Annotated[
        GitCliSettings | None,
        Field(
            description=(
                "Shared Git CLI settings (branch, token, user_name, cache_dir, …) "
                "merged into git_repo when not set there"
            ),
        ),
    ] = None
    git_repo: Annotated[GitRepoConfig, Field(description="Per-ARC GitRepo backend settings")]


class GitlabApiArcStoreConfig(BaseModel):
    """ArcStore config when ``type`` is ``gitlab_api``."""

    type: Literal[ArcStoreBackendType.GITLAB_API] = ArcStoreBackendType.GITLAB_API
    gitlab_api: Annotated[GitlabApiConfig, Field(description="GitLab API backend settings")]


class ConsolidatedGitArcStoreConfig(BaseModel):
    """ArcStore config when ``type`` is ``consolidated_git``."""

    type: Literal[ArcStoreBackendType.CONSOLIDATED_GIT] = ArcStoreBackendType.CONSOLIDATED_GIT
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


ArcStoreConfig = Annotated[
    GitRepoArcStoreConfig | GitlabApiArcStoreConfig | ConsolidatedGitArcStoreConfig,
    Field(discriminator="type"),
]
