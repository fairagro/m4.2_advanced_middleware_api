"""Preferred ``arc_store`` / ``consolidated_store`` configuration blocks."""

from typing import Annotated, ClassVar

from pydantic import BaseModel, ConfigDict, Field

from middleware.api.arc_store.consolidated_git.config import ConsolidatedGitConfig
from middleware.api.arc_store.git_cli_settings import GitCliSettings
from middleware.api.arc_store.git_repo.config import GitRepoConfig


class ArcStoreConfig(BaseModel):
    """Required per-ARC ArcStore slot.

    Backend is ``git_repo`` only — no separate ``type`` field. Nested
    ``gitlab_api`` is rejected via ``extra="forbid"``.
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
        GitRepoConfig,
        Field(description="Per-ARC GitRepo backend settings"),
    ]


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
