"""Unit tests for DocumentStore.append_harvest_error."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from middleware.api.document_store.couchdb import CouchDB
from middleware.api.document_store.harvest_document import HarvestDocument, HarvestStatistics
from middleware.shared.api_models.common.models import HarvestStatus
from middleware.shared.api_models.v3.models import HarvestError, HarvestErrorType


@pytest.fixture
def couchdb_client() -> MagicMock:
    """Provide a MagicMock standing in for CouchDBClient."""
    return MagicMock()


@pytest.fixture
def couchdb(couchdb_client: MagicMock) -> CouchDB:
    """CouchDB store with a mocked low-level client."""
    store = CouchDB.__new__(CouchDB)
    store._config = MagicMock()  # noqa: SLF001
    store._config.max_save_retries = 3
    store._db_name = "test"  # noqa: SLF001
    store._client = couchdb_client  # type: ignore[assignment]
    return store


@pytest.mark.asyncio
async def test_append_harvest_error_updates_list_and_statistics(couchdb: CouchDB, couchdb_client: MagicMock) -> None:
    """Appending an error extends the list and sets statistics.errors to len(errors)."""
    harvest_id = "harvest-1"
    existing = HarvestDocument(
        doc_id=harvest_id,
        doc_rev="1-abc",
        rdi="rdi-1",
        started_at=datetime.now(UTC),
        status=HarvestStatus.RUNNING,
        statistics=HarvestStatistics(errors=0),
        errors=[],
    )
    couchdb_client.get_document = AsyncMock(
        return_value=existing.model_dump(mode="json", by_alias=True, exclude_none=True)
    )
    couchdb_client.save_document_if_revision_matches = AsyncMock()

    error = HarvestError(
        arc_id="ARC-1",
        error_type=HarvestErrorType.DUPLICATE,
        message="conflict",
        timestamp="2024-01-01T00:00:00Z",
    )

    updated = await couchdb.append_harvest_error(harvest_id, error)

    assert len(updated.errors) == 1
    assert updated.errors[0].arc_id == "ARC-1"
    assert updated.statistics.errors == 1
    couchdb_client.save_document_if_revision_matches.assert_awaited_once()
