"""Unit tests for keyed harvest create idempotency in CouchDB DocumentStore."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from middleware.api.document_store import IdempotencyBodyConflictError, IdempotencyPendingError
from middleware.api.document_store.couchdb import CouchDB
from middleware.api.document_store.couchdb_client import DocumentConflictError
from middleware.api.document_store.harvest_idempotency_document import (
    HarvestIdempotencyDocument,
    IdempotencyStatus,
)


@pytest.fixture
def couchdb() -> CouchDB:
    """CouchDB store with a mocked low-level client."""
    store = CouchDB.__new__(CouchDB)
    store._config = MagicMock()  # noqa: SLF001
    store._db_name = "test"  # noqa: SLF001
    store._client = MagicMock()  # noqa: SLF001
    return store


@pytest.mark.asyncio
async def test_create_harvest_idempotent_first_create(couchdb: CouchDB) -> None:
    """First keyed create claims, creates harvest, and commits."""
    couchdb._client.create_document_exclusive = AsyncMock()  # noqa: SLF001
    couchdb._client.delete_document = AsyncMock()  # noqa: SLF001
    couchdb._client.save_document = AsyncMock()  # noqa: SLF001
    couchdb.create_harvest = AsyncMock(return_value="harvest-1")  # type: ignore[method-assign]

    harvest_id, replayed = await couchdb.create_harvest_idempotent("rdi-1", "client-a", "key-1", expected_datasets=3)

    assert harvest_id == "harvest-1"
    assert replayed is False
    couchdb._client.create_document_exclusive.assert_awaited_once()  # noqa: SLF001
    couchdb.create_harvest.assert_awaited_once()
    couchdb._client.save_document.assert_awaited_once()  # noqa: SLF001


@pytest.mark.asyncio
async def test_create_harvest_idempotent_replay(couchdb: CouchDB) -> None:
    """Existing committed claim with compatible body is replayed."""
    doc_id = CouchDB._idempotency_doc_id("client-a", "key-1")  # noqa: SLF001
    index = HarvestIdempotencyDocument(
        doc_id=doc_id,
        client_id="client-a",
        idempotency_key="key-1",
        rdi="rdi-1",
        expected_datasets=None,
        status=IdempotencyStatus.COMMITTED,
        harvest_id="harvest-existing",
        created_at=datetime.now(UTC),
    )
    couchdb._client.create_document_exclusive = AsyncMock(  # noqa: SLF001
        side_effect=DocumentConflictError("exists")
    )
    couchdb._client.get_document = AsyncMock(  # noqa: SLF001
        return_value=index.model_dump(mode="json", by_alias=True)
    )

    harvest_id, replayed = await couchdb.create_harvest_idempotent("rdi-1", "client-a", "key-1")

    assert harvest_id == "harvest-existing"
    assert replayed is True


@pytest.mark.asyncio
async def test_create_harvest_idempotent_body_conflict(couchdb: CouchDB) -> None:
    """Existing committed claim with different rdi raises conflict."""
    doc_id = CouchDB._idempotency_doc_id("client-a", "key-1")  # noqa: SLF001
    index = HarvestIdempotencyDocument(
        doc_id=doc_id,
        client_id="client-a",
        idempotency_key="key-1",
        rdi="rdi-other",
        expected_datasets=None,
        status=IdempotencyStatus.COMMITTED,
        harvest_id="harvest-existing",
        created_at=datetime.now(UTC),
    )
    couchdb._client.create_document_exclusive = AsyncMock(  # noqa: SLF001
        side_effect=DocumentConflictError("exists")
    )
    couchdb._client.get_document = AsyncMock(  # noqa: SLF001
        return_value=index.model_dump(mode="json", by_alias=True)
    )

    with pytest.raises(IdempotencyBodyConflictError):
        await couchdb.create_harvest_idempotent("rdi-1", "client-a", "key-1")


@pytest.mark.asyncio
async def test_create_harvest_idempotent_pending_timeout(couchdb: CouchDB, monkeypatch: pytest.MonkeyPatch) -> None:
    """Stuck pending claim eventually raises IdempotencyPendingError."""
    monkeypatch.setattr("middleware.api.document_store.couchdb._PENDING_POLL_ATTEMPTS", 2)
    monkeypatch.setattr("middleware.api.document_store.couchdb._PENDING_POLL_DELAY_S", 0)
    doc_id = CouchDB._idempotency_doc_id("client-a", "key-1")  # noqa: SLF001
    index = HarvestIdempotencyDocument(
        doc_id=doc_id,
        client_id="client-a",
        idempotency_key="key-1",
        rdi="rdi-1",
        expected_datasets=None,
        status=IdempotencyStatus.PENDING,
        harvest_id=None,
        created_at=datetime.now(UTC),
    )
    couchdb._client.create_document_exclusive = AsyncMock(  # noqa: SLF001
        side_effect=DocumentConflictError("exists")
    )
    couchdb._client.get_document = AsyncMock(  # noqa: SLF001
        return_value=index.model_dump(mode="json", by_alias=True)
    )

    with pytest.raises(IdempotencyPendingError):
        await couchdb.create_harvest_idempotent("rdi-1", "client-a", "key-1")


@pytest.mark.asyncio
async def test_create_harvest_idempotent_deletes_claim_on_create_failure(couchdb: CouchDB) -> None:
    """Failed harvest create rolls back the pending claim."""
    couchdb._client.create_document_exclusive = AsyncMock()  # noqa: SLF001
    couchdb._client.delete_document = AsyncMock(return_value=True)  # noqa: SLF001
    couchdb.create_harvest = AsyncMock(side_effect=RuntimeError("boom"))  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="boom"):
        await couchdb.create_harvest_idempotent("rdi-1", "client-a", "key-1")

    couchdb._client.delete_document.assert_awaited_once()  # noqa: SLF001
