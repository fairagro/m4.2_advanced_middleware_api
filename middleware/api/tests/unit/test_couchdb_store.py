"""Unit tests for CouchDB DocumentStore."""

import hashlib
import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import SecretStr

from middleware.api.config import CouchDBConfig
from middleware.api.document_store.couchdb import CouchDB
from middleware.api.schemas import ArcDocument, ArcEvent, ArcEventType, ArcMetadata
from middleware.api.schemas.arc_document import ArcLifecycleStatus


@pytest.fixture
def config() -> CouchDBConfig:
    """Create test configuration."""
    return CouchDBConfig(url="http://test:5984", user="user", password=SecretStr("pass"))


@pytest.fixture
def mock_client_instance() -> MagicMock:
    """Create a mock client instance."""
    client = MagicMock()
    # Async methods need to be AsyncMock
    client.connect = AsyncMock()
    client.close = AsyncMock()
    client.health_check = AsyncMock(return_value=True)
    client.get_document = AsyncMock()
    client.save_document = AsyncMock()
    return client


@pytest.fixture
def store(config: CouchDBConfig, mock_client_instance: MagicMock) -> CouchDB:
    """Create CouchDB store with mocked client."""
    # Patch where CouchDB calls CouchDBClient.from_config
    with patch("middleware.api.document_store.couchdb.CouchDBClient.from_config", return_value=mock_client_instance):
        store_inst = CouchDB(config)
        return store_inst


@pytest.mark.asyncio
async def test_store_arc_new(store: CouchDB, mock_client_instance: MagicMock) -> None:
    """Test storing a new ARC."""
    # Setup
    rdi = "test_rdi"
    arc_content = {"@graph": [{"@id": "./", "identifier": "arc_123"}]}

    # Mock client methods
    mock_client_instance.get_document.return_value = None  # document not found -> new
    mock_client_instance.save_document.return_value = {"id": "arc_...", "rev": "1-..."}

    # Execute
    result = await store.store_arc(rdi, arc_content)

    # Verify
    assert result.is_new is True
    assert result.has_changes is True
    assert result.should_trigger_git is True

    # Check save called
    mock_client_instance.save_document.assert_called_once()
    args, _ = mock_client_instance.save_document.call_args
    doc_id, doc_data = args
    assert doc_id.startswith("arc_")
    assert doc_data["rdi"] == rdi
    assert doc_data["arc_content"] == arc_content
    assert doc_data["metadata"]["status"] == ArcLifecycleStatus.ACTIVE
    assert len(doc_data["metadata"]["events"]) == 1
    assert doc_data["metadata"]["events"][0]["type"] == "ARC_CREATED"


@pytest.mark.asyncio
async def test_get_arc_content(store: CouchDB, mock_client_instance: MagicMock) -> None:
    """Test get_arc_content returns content."""
    arc_content = {"key": "value"}
    mock_client_instance.get_document.return_value = {"arc_content": arc_content}

    result = await store.get_arc_content("test_id")
    assert result == arc_content
    mock_client_instance.get_document.assert_called_once_with("arc_test_id")


@pytest.mark.asyncio
async def test_get_metadata(store: CouchDB, mock_client_instance: MagicMock) -> None:
    """Test get_metadata returns ArcMetadata."""
    metadata_dict = {
        "arc_hash": "hash",
        "status": "ACTIVE",
        "first_seen": datetime.now(UTC).isoformat(),
        "last_seen": datetime.now(UTC).isoformat(),
        "events": [],
    }
    mock_client_instance.get_document.return_value = {"metadata": metadata_dict}

    result = await store.get_metadata("test_id")
    assert isinstance(result, ArcMetadata)
    assert result.arc_hash == "hash"


@pytest.mark.asyncio
async def test_add_event_non_existent(store: CouchDB, mock_client_instance: MagicMock) -> None:
    """Test add_event does nothing if document not found."""
    mock_client_instance.get_document.return_value = None
    event = ArcEvent(type=ArcEventType.ARC_UPDATED, message="test", timestamp=datetime.now(UTC))

    await store.add_event("non_existent", event)
    mock_client_instance.save_document.assert_not_called()


@pytest.mark.asyncio
async def test_couchdb_store_lifecycle(store: CouchDB, mock_client_instance: MagicMock) -> None:
    """Test connect, close, and health_check calls client."""
    await store.connect()
    mock_client_instance.connect.assert_called_with(db_name="arcs")

    await store.close()
    mock_client_instance.close.assert_called_once()

    await store.health_check()
    mock_client_instance.health_check.assert_called_once()


@pytest.mark.asyncio
async def test_couchdb_store_setup(store: CouchDB, mock_client_instance: MagicMock) -> None:
    """Test setup calls client.connect with setup_system."""
    await store.setup(setup_system=True)
    mock_client_instance.connect.assert_called_with(db_name="arcs", setup_system=True)


@pytest.mark.asyncio
async def test_store_arc_update_changed(store: CouchDB, mock_client_instance: MagicMock) -> None:
    """Test updating an existing ARC with changes."""
    # Setup
    rdi = "test_rdi"
    arc_content = {"@graph": [{"@id": "./", "identifier": "arc_123"}, {"@id": "dataset", "name": "Changed Name"}]}

    # Existing document
    existing_hash = "old_hash"
    existing_doc = {
        "_id": "arc_...",
        "_rev": "1-rev",
        "rdi": rdi,
        "arc_content": {"original": "content"},
        "metadata": {
            "arc_hash": existing_hash,
            "status": "ACTIVE",
            "first_seen": "2023-01-01T00:00:00Z",
            "last_seen": "2023-01-01T00:00:00Z",
            "events": [],
        },
    }

    mock_client_instance.get_document.return_value = existing_doc
    mock_client_instance.save_document.return_value = {"ok": True}

    # Execute
    result = await store.store_arc(rdi, arc_content)

    # Verify
    assert result.is_new is False
    assert result.has_changes is True
    assert result.should_trigger_git is True

    mock_client_instance.save_document.assert_called_once()
    args, _ = mock_client_instance.save_document.call_args
    _, doc_data = args

    assert doc_data["metadata"]["arc_hash"] != existing_hash
    assert doc_data["metadata"]["events"][-1]["type"] == "ARC_UPDATED"


@pytest.mark.asyncio
async def test_store_arc_no_change(store: CouchDB, mock_client_instance: MagicMock) -> None:
    """Test storing an unchanged ARC."""
    # Setup
    rdi = "test_rdi"
    arc_content = {"@graph": [{"@id": "./", "identifier": "arc_123"}]}

    # Calculate hash to match
    json_str = json.dumps(arc_content, sort_keys=True)
    content_hash = hashlib.sha256(json_str.encode("utf-8")).hexdigest()

    # Existing document matches
    existing_doc = {
        "_id": "arc_...",
        "_rev": "1-rev",
        "rdi": rdi,
        "arc_content": arc_content,
        "metadata": {
            "arc_hash": content_hash,
            "status": "ACTIVE",
            "first_seen": "2023-01-01T00:00:00Z",
            "last_seen": "2023-01-01T00:00:00Z",
            "events": [],
        },
    }

    mock_client_instance.get_document.return_value = existing_doc
    mock_client_instance.save_document.return_value = {"ok": True}

    # Execute
    result = await store.store_arc(rdi, arc_content)

    # Verify
    assert result.is_new is False
    assert result.has_changes is False
    assert result.should_trigger_git is False

    # Should still save to update last_seen
    mock_client_instance.save_document.assert_called_once()


@pytest.mark.asyncio
async def test_add_event_trimming(store: CouchDB, mock_client_instance: MagicMock) -> None:  # noqa: ARG001
    """Test that event log is trimmed according to configuration."""
    limit = 2
    # Set a small limit (pylint: disable=protected-access)
    store._config.max_event_log_size = limit

    arc_id = "some_id"

    initial_doc = ArcDocument(
        doc_id=f"arc_{arc_id}",
        rdi="test_rdi",
        arc_content={},
        metadata=ArcMetadata(
            arc_hash="abc",
            status=ArcLifecycleStatus.ACTIVE,
            first_seen=datetime.now(UTC),
            last_seen=datetime.now(UTC),
            events=[],
        ),
    )

    mock_client_instance.get_document.return_value = initial_doc.model_dump(by_alias=True)

    # Add 3 events (one by one)
    event1 = ArcEvent(timestamp=datetime.now(UTC), type=ArcEventType.ARC_CREATED, message="1")
    event2 = ArcEvent(timestamp=datetime.now(UTC), type=ArcEventType.ARC_UPDATED, message="2")
    event3 = ArcEvent(timestamp=datetime.now(UTC), type=ArcEventType.ARC_UPDATED, message="3")

    # 1. Add first event
    await store.add_event(arc_id, event1)
    # Update mock for next call
    saved_doc_dict = mock_client_instance.save_document.call_args[0][1]
    mock_client_instance.get_document.return_value = saved_doc_dict

    # 2. Add second event
    await store.add_event(arc_id, event2)
    saved_doc_dict = mock_client_instance.save_document.call_args[0][1]
    mock_client_instance.get_document.return_value = saved_doc_dict

    # 3. Add third event
    await store.add_event(arc_id, event3)
    saved_doc_dict = mock_client_instance.save_document.call_args[0][1]

    saved_doc = ArcDocument(**saved_doc_dict)

    # Should only have limit events
    assert len(saved_doc.metadata.events) == limit  # noqa: PLR2004
    # Should be the most recent ones
    assert saved_doc.metadata.events[-1].message == "3"
    assert saved_doc.metadata.events[-2].message == "2"
