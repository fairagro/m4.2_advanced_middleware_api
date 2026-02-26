"""Configuration models for harvest-related components."""

from typing import Annotated

from pydantic import BaseModel, Field


class HarvestConfig(BaseModel):
    """Configuration for a harvest run."""

    grace_period_days: Annotated[int, Field(description="Days before marking ARC as deleted")] = 14
    auto_mark_deleted: Annotated[bool, Field(description="Automatically mark ARCs as deleted")] = False
