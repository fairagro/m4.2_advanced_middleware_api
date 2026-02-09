"""Harvest document schema for CouchDB."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field

from middleware.api.schemas import HarvestStatus


class HarvestStatistics(BaseModel):
    """Statistics for a completed harvest run."""

    arcs_submitted: Annotated[int, Field(description="Total ARCs submitted")] = 0
    arcs_new: Annotated[int, Field(description="New ARCs created")] = 0
    arcs_updated: Annotated[int, Field(description="Existing ARCs updated")] = 0
    arcs_unchanged: Annotated[int, Field(description="ARCs with no changes")] = 0
    arcs_missing: Annotated[int, Field(description="ARCs marked as missing")] = 0
    errors: Annotated[int, Field(description="Number of errors encountered")] = 0


class HarvestConfig(BaseModel):
    """Configuration for a harvest run."""

    grace_period_days: Annotated[int, Field(description="Days before marking ARC as deleted")] = 3
    auto_mark_deleted: Annotated[bool, Field(description="Automatically mark ARCs as deleted")] = True


class HarvestDocument(BaseModel):
    """Harvest run document for CouchDB storage."""

    # CouchDB fields
    _id: Annotated[str, Field(description="Document ID (harvest-<uuid>)", alias="_id")]
    _rev: Annotated[str | None, Field(description="CouchDB revision", alias="_rev")] = None

    # Document type for queries
    type: Annotated[str, Field(description="Document type")] = "harvest"

    # Harvest data
    rdi: Annotated[str, Field(description="Research Data Infrastructure identifier")]
    source: Annotated[str, Field(description="Source database/system")]
    started_at: Annotated[datetime, Field(description="Harvest start timestamp")]
    completed_at: Annotated[datetime | None, Field(description="Harvest completion timestamp")] = None
    status: Annotated[HarvestStatus, Field(description="Harvest status")]
    statistics: Annotated[HarvestStatistics, Field(description="Harvest statistics")] = Field(
        default_factory=HarvestStatistics
    )
    config: Annotated[HarvestConfig, Field(description="Harvest configuration")] = Field(default_factory=HarvestConfig)

    class Config:
        """Pydantic configuration."""

        populate_by_name = True
