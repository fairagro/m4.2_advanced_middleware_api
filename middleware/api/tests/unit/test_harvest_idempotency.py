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
async def test_create_harvest_idempotent_expected_datasets_conflict(
    couchdb: CouchDB, couchdb_client: MagicMock
) -> None:
    """Existing committed claim with different expected_datasets raises conflict."""
    doc_id = CouchDB._idempotency_doc_id("client-a", "key-1")  # noqa: SLF001
    index = HarvestIdempotencyDocument(
        doc_id=doc_id,
        client_id="client-a",
        idempotency_key="key-1",
        rdi="rdi-1",
        expected_datasets=3,
        status=IdempotencyStatus.COMMITTED,
        harvest_id="harvest-existing",
        created_at=datetime.now(UTC),
    )
    couchdb_client.create_document_exclusive = AsyncMock(side_effect=DocumentConflictError("exists"))
    couchdb_client.get_document = AsyncMock(return_value=index.model_dump(mode="json", by_alias=True))

    with pytest.raises(IdempotencyBodyConflictError):
        await couchdb.create_harvest_idempotent("rdi-1", "client-a", "key-1", expected_datasets=5)


@pytest.mark.asyncio
async def test_create_harvest_idempotent_pending_timeout(couchdb: CouchDB, couchdb_client: MagicMock) -> None:
    """Stuck pending claim eventually raises IdempotencyPendingError."""
    couchdb._config.pending_poll_attempts = 2  # noqa: SLF001
    couchdb._config.pending_poll_delay_s = 0.0  # noqa: SLF001
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


@pytest.mark.asyncio
async def test_create_harvest_idempotent_preserves_create_error_if_rollback_fails(
    couchdb: CouchDB, couchdb_client: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rollback delete failures must not mask the original create error."""
    couchdb_client.create_document_exclusive = AsyncMock()
    couchdb_client.delete_document = AsyncMock(side_effect=RuntimeError("delete failed"))
    monkeypatch.setattr(couchdb, "create_harvest", AsyncMock(side_effect=RuntimeError("boom")))

    with pytest.raises(RuntimeError, match="boom"):
        await couchdb.create_harvest_idempotent("rdi-1", "client-a", "key-1")


@pytest.mark.asyncio
async def test_create_harvest_idempotent_keeps_claim_when_harvest_rollback_fails_on_commit(
    couchdb: CouchDB, couchdb_client: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Failed harvest rollback on commit failure must not release the claim."""

    async def _delete_side_effect(doc_to_delete: str) -> bool:
        if doc_to_delete == "harvest-1":
            raise RuntimeError("harvest delete failed")
        return True

    couchdb_client.create_document_exclusive = AsyncMock()
    couchdb_client.delete_document = AsyncMock(side_effect=_delete_side_effect)
    couchdb_client.save_document = AsyncMock(side_effect=RuntimeError("commit failed"))
    monkeypatch.setattr(couchdb, "create_harvest", AsyncMock(return_value="harvest-1"))

    with pytest.raises(RuntimeError, match="commit failed"):
        await couchdb.create_harvest_idempotent("rdi-1", "client-a", "key-1")

    couchdb_client.delete_document.assert_awaited_once_with("harvest-1")


@pytest.mark.asyncio
async def test_create_harvest_idempotent_rolls_back_on_commit_failure(
    couchdb: CouchDB, couchdb_client: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Failed index commit deletes harvest and claim so the key can be retried."""
    couchdb_client.create_document_exclusive = AsyncMock()
    couchdb_client.delete_document = AsyncMock(return_value=True)
    couchdb_client.save_document = AsyncMock(side_effect=RuntimeError("commit failed"))
    monkeypatch.setattr(couchdb, "create_harvest", AsyncMock(return_value="harvest-1"))

    with pytest.raises(RuntimeError, match="commit failed"):
        await couchdb.create_harvest_idempotent("rdi-1", "client-a", "key-1")

    assert couchdb_client.delete_document.await_count == 2  # noqa: PLR2004
    deleted_ids = [call.args[0] for call in couchdb_client.delete_document.await_args_list]
    assert deleted_ids == ["harvest-1", CouchDB._idempotency_doc_id("client-a", "key-1")]  # noqa: SLF001
