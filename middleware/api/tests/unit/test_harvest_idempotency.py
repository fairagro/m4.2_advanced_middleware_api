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
def couchdb_client() -> MagicMock:
    """Provide a MagicMock standing in for CouchDBClient."""
    return MagicMock()


@pytest.fixture
def couchdb(couchdb_client: MagicMock) -> CouchDB:
    """CouchDB store with a mocked low-level client."""
    store = CouchDB.__new__(CouchDB)
    store._config = MagicMock()  # noqa: SLF001
    store._db_name = "test"  # noqa: SLF001
    store._client = couchdb_client  # type: ignore[assignment]
    return store


@pytest.mark.asyncio
async def test_create_harvest_idempotent_first_create(
    couchdb: CouchDB, couchdb_client: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """First keyed create claims, creates harvest, and commits."""
    couchdb_client.create_document_exclusive = AsyncMock()
    couchdb_client.delete_document = AsyncMock()
    couchdb_client.save_document = AsyncMock()
    create_harvest = AsyncMock(return_value="harvest-1")
    monkeypatch.setattr(couchdb, "create_harvest", create_harvest)

    harvest_id, replayed = await couchdb.create_harvest_idempotent("rdi-1", "client-a", "key-1", expected_datasets=3)

    assert harvest_id == "harvest-1"
    assert replayed is False
    couchdb_client.create_document_exclusive.assert_awaited_once()
    create_harvest.assert_awaited_once()
    couchdb_client.save_document.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_harvest_idempotent_replay(couchdb: CouchDB, couchdb_client: MagicMock) -> None:
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
    couchdb_client.create_document_exclusive = AsyncMock(side_effect=DocumentConflictError("exists"))
    couchdb_client.get_document = AsyncMock(return_value=index.model_dump(mode="json", by_alias=True))

    harvest_id, replayed = await couchdb.create_harvest_idempotent("rdi-1", "client-a", "key-1")

    assert harvest_id == "harvest-existing"
    assert replayed is True


@pytest.mark.asyncio
async def test_create_harvest_idempotent_body_conflict(couchdb: CouchDB, couchdb_client: MagicMock) -> None:
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
    couchdb_client.create_document_exclusive = AsyncMock(side_effect=DocumentConflictError("exists"))
    couchdb_client.get_document = AsyncMock(return_value=index.model_dump(mode="json", by_alias=True))

    with pytest.raises(IdempotencyBodyConflictError):
        await couchdb.create_harvest_idempotent("rdi-1", "client-a", "key-1")


@pytest.mark.asyncio
async def test_create_harvest_idempotent_pending_timeout(
    couchdb: CouchDB, couchdb_client: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
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
    couchdb_client.create_document_exclusive = AsyncMock(side_effect=DocumentConflictError("exists"))
    couchdb_client.get_document = AsyncMock(return_value=index.model_dump(mode="json", by_alias=True))

    with pytest.raises(IdempotencyPendingError):
        await couchdb.create_harvest_idempotent("rdi-1", "client-a", "key-1")


@pytest.mark.asyncio
async def test_create_harvest_idempotent_pending_body_conflict(couchdb: CouchDB, couchdb_client: MagicMock) -> None:
    """Incompatible body while claim is still pending raises conflict immediately."""
    doc_id = CouchDB._idempotency_doc_id("client-a", "key-1")  # noqa: SLF001
    index = HarvestIdempotencyDocument(
        doc_id=doc_id,
        client_id="client-a",
        idempotency_key="key-1",
        rdi="rdi-other",
        expected_datasets=None,
        status=IdempotencyStatus.PENDING,
        harvest_id=None,
        created_at=datetime.now(UTC),
    )
    couchdb_client.create_document_exclusive = AsyncMock(side_effect=DocumentConflictError("exists"))
    couchdb_client.get_document = AsyncMock(return_value=index.model_dump(mode="json", by_alias=True))

    with pytest.raises(IdempotencyBodyConflictError):
        await couchdb.create_harvest_idempotent("rdi-1", "client-a", "key-1")


@pytest.mark.asyncio
async def test_create_harvest_idempotent_deletes_claim_on_create_failure(
    couchdb: CouchDB, couchdb_client: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Failed harvest create rolls back the pending claim."""
    couchdb_client.create_document_exclusive = AsyncMock()
    couchdb_client.delete_document = AsyncMock(return_value=True)
    monkeypatch.setattr(couchdb, "create_harvest", AsyncMock(side_effect=RuntimeError("boom")))

    with pytest.raises(RuntimeError, match="boom"):
        await couchdb.create_harvest_idempotent("rdi-1", "client-a", "key-1")

    couchdb_client.delete_document.assert_awaited_once()
