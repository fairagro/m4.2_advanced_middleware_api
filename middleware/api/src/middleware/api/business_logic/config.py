"""Configuration models for business logic components."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Protocol

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from middleware.api.arc_store.arc_store_config import ArcStoreConfig
    from middleware.api.arc_store.consolidated_git import ConsolidatedGitConfig
    from middleware.api.arc_store.git_repo import GitRepoConfig
    from middleware.api.arc_store.gitlab_api import GitlabApiConfig
    from middleware.api.document_store.config import CouchDBConfig


class HarvestConfig(BaseModel):
    """Configuration for a harvest run."""

    grace_period_days: Annotated[int, Field(description="Days before marking ARC as deleted")] = 14
    auto_mark_deleted: Annotated[bool, Field(description="Automatically mark ARCs as deleted")] = False


class BusinessLogicConfig(Protocol):
    """Minimal config interface required by BusinessLogic."""

    harvest: HarvestConfig


class BusinessLogicFactoryConfig(BusinessLogicConfig, Protocol):
    """Config interface required by BusinessLogicFactory."""

    arc_store: ArcStoreConfig | None
    git_repo: GitRepoConfig | None
    gitlab_api: GitlabApiConfig | None
    consolidated_git: ConsolidatedGitConfig | None
    couchdb: CouchDBConfig
