"""System test: CouchDB document persistence.

Regression test for the bug where aiocouch.Database.create() was called
without a subsequent await doc.save(), silently discarding every new
document write and causing GET /v2/tasks/{id} to always return PENDING.

The test spins up a real CouchDB 3.3 container via testcontainers
(no external services required) and verifies end-to-end persistence
through CouchDBClient, exactly as the production path looks.
"""

import uuid
from collections.abc import AsyncGenerator, Generator

import pytest
from testcontainers.core.container import DockerContainer  # type: ignore[import-untyped]
from testcontainers.core.wait_strategies import LogMessageWaitStrategy  # type: ignore[import-untyped]

from middleware.api.document_store.couchdb_client import CouchDBClient

_COUCHDB_IMAGE = "couchdb:3.3"
_COUCHDB_USER = "admin"
_COUCHDB_PASSWORD = "test-password"
_COUCHDB_PORT = 5984
_DB_NAME = "test_persistence"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def couchdb_container() -> Generator[DockerContainer, None, None]:
    """Start a real CouchDB 3.3 container for the module's lifetime."""
    container = (
        DockerContainer(_COUCHDB_IMAGE)
        .with_env("COUCHDB_USER", _COUCHDB_USER)
        .with_env("COUCHDB_PASSWORD", _COUCHDB_PASSWORD)
        .with_exposed_ports(_COUCHDB_PORT)
        # Wait strategy must be set before __enter__ so the container
        # blocks until CouchDB is fully initialised.
        .waiting_for(LogMessageWaitStrategy("Apache CouchDB has started"))
    )
    with container:
        yield container


@pytest.fixture
async def couchdb_client(couchdb_container: DockerContainer) -> AsyncGenerator[CouchDBClient, None]:  # type: ignore[type-arg]
    """Create and connect a CouchDBClient against the live container.

    A fresh database name is used per test so tests are fully isolated.
    """
    host = couchdb_container.get_container_host_ip()
    port = couchdb_container.get_exposed_port(_COUCHDB_PORT)
    # Each test gets its own database to guarantee isolation
    db_name = f"{_DB_NAME}_{uuid.uuid4().hex[:8]}"
    client = CouchDBClient(
        url=f"http://{host}:{port}",
        db_name=db_name,
        user=_COUCHDB_USER,
        password=_COUCHDB_PASSWORD,
        default_query_limit=100,
    )
    await client.connect()
    yield client
    await client.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.system_local
async def test_new_document_is_persisted(couchdb_client: CouchDBClient) -> None:
    """save_document() on a brand-new ID must write the document to CouchDB.

    Regression: before the fix, aiocouch.Database.create() was called without
    await doc.save(), so the document only existed in memory and get_document()
    returned None — causing every task to stay PENDING forever.
    """
    doc_id = f"task_status_{uuid.uuid4()}"
    payload = {"status": "SUCCESS", "result": {"arc_id": "arc-001"}}

    await couchdb_client.save_document(doc_id, payload)

    persisted = await couchdb_client.get_document(doc_id)

    assert persisted is not None, (
        f"Document '{doc_id}' was not found after save_document(). "
        "This is the PENDING-forever regression: aiocouch.Database.create() "
        "does not write to CouchDB — await doc.save() is required."
    )
    assert persisted["status"] == "SUCCESS"
    assert persisted["result"] == {"arc_id": "arc-001"}


@pytest.mark.system_local
async def test_update_preserves_existing_document(couchdb_client: CouchDBClient) -> None:
    """save_document() on an existing ID must update, not duplicate, the document."""
    doc_id = f"arc_{uuid.uuid4()}"

    initial_version = 1
    updated_version = 2
    await couchdb_client.save_document(doc_id, {"version": initial_version, "content": "initial"})
    await couchdb_client.save_document(doc_id, {"version": updated_version, "content": "updated"})

    persisted = await couchdb_client.get_document(doc_id)

    assert persisted is not None
    assert persisted["version"] == updated_version
    assert persisted["content"] == "updated"


@pytest.mark.system_local
async def test_document_not_found_returns_none(couchdb_client: CouchDBClient) -> None:
    """get_document() on a non-existent ID must return None, not raise."""
    result = await couchdb_client.get_document(f"does_not_exist_{uuid.uuid4()}")
    assert result is None


@pytest.mark.system_local
async def test_task_status_lifecycle(couchdb_client: CouchDBClient) -> None:
    """Full lifecycle: create PENDING → update to SUCCESS, verify each step.

    Mirrors the actual task-status flow that caused the PENDING regression:
      1. POST /v2/arcs writes a PENDING record via save_document().
      2. Celery worker writes SUCCESS via save_document().
      3. GET /v2/tasks/{id} reads via get_document() and returns SUCCESS.
    """
    task_id = f"task_status_{uuid.uuid4()}"

    # Step 1: API writes PENDING record
    await couchdb_client.save_document(task_id, {"status": "PENDING"})

    pending = await couchdb_client.get_document(task_id)
    assert pending is not None, "PENDING record must be persisted immediately"
    assert pending["status"] == "PENDING"

    # Step 2: Celery worker writes SUCCESS
    await couchdb_client.save_document(task_id, {"status": "SUCCESS", "arc_id": "arc-042"})

    success = await couchdb_client.get_document(task_id)
    assert success is not None
    assert success["status"] == "SUCCESS"
    assert success["arc_id"] == "arc-042"
