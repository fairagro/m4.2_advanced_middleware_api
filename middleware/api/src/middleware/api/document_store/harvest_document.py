"""Harvest document schema for CouchDB."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from middleware.shared.api_models.common.models import HarvestStatus


class HarvestStatistics(BaseModel):
    """Statistics for a completed harvest run."""

    expected_datasets: Annotated[
        int | None,
        Field(description="Number of datasets expected to be harvested, as reported by the client. Not validated."),
    ] = None
    arcs_submitted: Annotated[int, Field(description="Total ARCs submitted")] = 0
    arcs_new: Annotated[int, Field(description="New ARCs created")] = 0
    arcs_updated: Annotated[int, Field(description="Existing ARCs updated")] = 0
    arcs_unchanged: Annotated[int, Field(description="ARCs with no changes")] = 0
    arcs_missing: Annotated[int, Field(description="ARCs marked as missing")] = 0
    errors: Annotated[int, Field(description="Number of errors encountered")] = 0


class HarvestDocument(BaseModel):
    """Harvest run document for CouchDB storage."""

    # CouchDB fields
    doc_id: Annotated[str, Field(description="Document ID (harvest-<uuid>)", alias="_id")]
    doc_rev: Annotated[str | None, Field(description="CouchDB revision", alias="_rev")] = None

    # Document type for queries
    type: Annotated[str, Field(description="Document type")] = "harvest"

    # Harvest data
    rdi: Annotated[str, Field(description="Research Data Infrastructure identifier")]
    client_id: Annotated[
        str,
        Field(
            description="The identifier of the client who started the harvest",
            # Old CouchDB documents (main-branch schema) have neither 'client_id'
            # nor an equivalent field — they used a separate 'source' field that
            # tracked the data *source system*, not the client identity.  Provide
            # 'unknown' as the default so those documents can still be parsed.
        ),
    ] = "unknown"
    started_at: Annotated[datetime, Field(description="Harvest start timestamp")]
    completed_at: Annotated[datetime | None, Field(description="Harvest completion timestamp")] = None
    status: Annotated[HarvestStatus, Field(description="Harvest status")]
    statistics: Annotated[HarvestStatistics, Field(default_factory=HarvestStatistics, description="Harvest statistics")]

    model_config = ConfigDict(populate_by_name=True, extra="ignore")
