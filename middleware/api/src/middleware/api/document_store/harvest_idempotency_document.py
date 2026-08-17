"""CouchDB document for harvest-create idempotency keys."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class IdempotencyStatus(StrEnum):
    """Lifecycle of a harvest idempotency claim."""

    PENDING = "pending"
    COMMITTED = "committed"


class HarvestIdempotencyDocument(BaseModel):
    """Index document that maps ``(client_id, Idempotency-Key)`` to a harvest."""

    doc_id: Annotated[str, Field(description="Document ID", alias="_id")]
    doc_rev: Annotated[str | None, Field(description="CouchDB revision", alias="_rev")] = None
    type: Annotated[str, Field(description="Document type")] = "harvest_idempotency"
    client_id: Annotated[str, Field(description="Authenticated client that owns the key")]
    idempotency_key: Annotated[str, Field(description="Raw Idempotency-Key from the client")]
    rdi: Annotated[str, Field(description="RDI from the create request")]
    expected_datasets: Annotated[
        int | None,
        Field(description="expected_datasets from the create request"),
    ] = None
    status: Annotated[IdempotencyStatus, Field(description="Claim status")]
    harvest_id: Annotated[
        str | None,
        Field(description="Created harvest id once the claim is committed"),
    ] = None
    created_at: Annotated[datetime, Field(description="Claim creation timestamp")]

    model_config = ConfigDict(populate_by_name=True, extra="ignore")
