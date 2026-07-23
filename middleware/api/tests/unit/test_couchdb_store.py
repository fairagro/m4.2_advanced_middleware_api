"""Unit tests for CouchDB DocumentStore."""

import hashlib
import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import SecretStr

from middleware.api.document_store import DuplicateArcError
from middleware.api.document_store.arc_document import ArcDocument, ArcEvent, ArcMetadata
from middleware.api.document_store.config import CouchDBConfig
from middleware.api.document_store.content_hash import RoCrateContent, calculate_arc_content_hash
from middleware.api.document_store.couchdb import CouchDB
from middleware.shared.api_models.common.models import ArcEventType, ArcLifecycleStatus


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
    client.save_document_if_revision_matches = AsyncMock()
    client.create_index = AsyncMock()
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
    arc_content: RoCrateContent = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [{"@id": "./", "identifier": "arc_123"}],
    }

    # Mock client methods
    mock_client_instance.get_document.return_value = None  # document not found -> new
    mock_client_instance.save_document.return_value = {"id": "arc_...", "rev": "1-..."}

    # Execute
    result = await store.store_arc(rdi, arc_content, "arc_123")

    # Verify
    assert result.is_new is True
    assert result.has_changes is True

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
    arc_content: RoCrateContent = {"key": "value"}
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
    mock_client_instance.connect.assert_called_once()

    await store.close()
    mock_client_instance.close.assert_called_once()

    await store.health_check()
    mock_client_instance.health_check.assert_called_once()


@pytest.mark.asyncio
async def test_couchdb_store_setup(store: CouchDB, mock_client_instance: MagicMock) -> None:
    """Test setup calls client.create_index."""
    await store.setup()
    assert mock_client_instance.create_index.call_count == 2  # noqa: PLR2004
    mock_client_instance.create_index.assert_any_call(["type", "rdi"], name="idx_type_rdi")
    mock_client_instance.create_index.assert_any_call(
        ["doc_type", "metadata.last_harvest_id"],
        name="idx_doc_type_harvest",
    )


@pytest.mark.asyncio
async def test_store_arc_update_changed(store: CouchDB, mock_client_instance: MagicMock) -> None:
    """Test updating an existing ARC with changes."""
    # Setup
    rdi = "test_rdi"
    arc_content: RoCrateContent = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [{"@id": "./", "identifier": "arc_123"}, {"@id": "dataset", "name": "Changed Name"}],
    }

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
    result = await store.store_arc(rdi, arc_content, "arc_123")

    # Verify
    assert result.is_new is False
    assert result.has_changes is True
    assert result.has_changes is True

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
    arc_content: RoCrateContent = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [{"@id": "./", "identifier": "arc_123"}],
    }

    # Calculate hash to match (normalized, volatile fields excluded)
    content_hash = calculate_arc_content_hash(arc_content)

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
    result = await store.store_arc(rdi, arc_content, "arc_123")

    # Verify
    assert result.is_new is False
    assert result.has_changes is False
    assert result.has_changes is False

    # Should still save to update last_seen
    mock_client_instance.save_document.assert_called_once()


def _make_existing_arc_doc(rdi: str, arc_content: RoCrateContent, last_harvest_id: str | None = None) -> dict:
    """Build a minimal existing ARC document dict for mocking."""
    content_hash = calculate_arc_content_hash(arc_content)
    return {
        "_id": "arc_...",
        "_rev": "1-rev",
        "rdi": rdi,
        "arc_content": arc_content,
        "metadata": {
            "arc_hash": content_hash,
            "status": "ACTIVE",
            "first_seen": "2023-01-01T00:00:00Z",
            "last_seen": "2023-01-01T00:00:00Z",
            "last_harvest_id": last_harvest_id,
            "events": [],
        },
    }


@pytest.mark.asyncio
async def test_store_arc_timestamp_only_not_a_change(store: CouchDB, mock_client_instance: MagicMock) -> None:
    """Re-serialized RO-Crate with fresh arctrl timestamps must not trigger a change."""
    rdi = "test_rdi"
    stored_content: RoCrateContent = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [
            {
                "@id": "./",
                "identifier": "arc_123",
                "datePublished": "2026-01-01T10:00:00.111",
                "sdDatePublished": "2026-01-01T10:00:00.112",
            },
            {"@id": "#study", "dateModified": "2026-01-01T10:00:00.200", "name": "Study"},
        ],
    }
    resubmitted_content: RoCrateContent = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [
            {
                "@id": "./",
                "identifier": "arc_123",
                "datePublished": "2026-07-01T11:19:33.494",
                "sdDatePublished": "2026-07-01T11:19:33.557",
            },
            {"@id": "#study", "dateModified": "2026-07-01T11:19:33.522", "name": "Study"},
        ],
    }
    legacy_hash = hashlib.sha256(json.dumps(stored_content, sort_keys=True).encode("utf-8")).hexdigest()
    existing_doc = {
        "_id": "arc_...",
        "_rev": "1-rev",
        "rdi": rdi,
        "arc_content": stored_content,
        "metadata": {
            "arc_hash": legacy_hash,
            "status": "ACTIVE",
            "first_seen": "2023-01-01T00:00:00Z",
            "last_seen": "2023-01-01T00:00:00Z",
            "events": [],
        },
    }

    mock_client_instance.get_document.return_value = existing_doc
    mock_client_instance.save_document.return_value = {"ok": True}

    result = await store.store_arc(rdi, resubmitted_content, "arc_123")

    assert result.is_new is False
    assert result.has_changes is False
    mock_client_instance.save_document.assert_called_once()
    _, doc_data = mock_client_instance.save_document.call_args[0]
    assert doc_data["metadata"]["arc_hash"] == calculate_arc_content_hash(resubmitted_content)
    assert doc_data["metadata"]["events"] == []


@pytest.mark.asyncio
async def test_store_arc_identical_resubmit_same_harvest_is_idempotent(
    store: CouchDB, mock_client_instance: MagicMock
) -> None:
    """Identical ARC re-submit in the same harvest succeeds without DuplicateArcError."""
    rdi = "test_rdi"
    harvest_id = "harvest-abc"
    arc_content: RoCrateContent = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [{"@id": "./", "identifier": "arc_dup"}],
    }
    mock_client_instance.get_document.return_value = _make_existing_arc_doc(
        rdi, arc_content, last_harvest_id=harvest_id
    )
    mock_client_instance.save_document.return_value = {"ok": True}

    result = await store.store_arc(rdi, arc_content, "arc_dup", harvest_id=harvest_id)

    assert result.is_new is False
    assert result.has_changes is False
    mock_client_instance.save_document.assert_called_once()


@pytest.mark.asyncio
async def test_store_arc_different_content_same_harvest_raises(store: CouchDB, mock_client_instance: MagicMock) -> None:
    """store_arc raises DuplicateArcError when the same ARC id has different content in one harvest."""
    rdi = "test_rdi"
    harvest_id = "harvest-abc"
    existing_content: RoCrateContent = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [{"@id": "./", "identifier": "arc_dup", "name": "original"}],
    }
    new_content: RoCrateContent = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [{"@id": "./", "identifier": "arc_dup", "name": "changed"}],
    }
    mock_client_instance.get_document.return_value = _make_existing_arc_doc(
        rdi, existing_content, last_harvest_id=harvest_id
    )

    with pytest.raises(DuplicateArcError, match="different content"):
        await store.store_arc(rdi, new_content, "arc_dup", harvest_id=harvest_id)

    mock_client_instance.save_document.assert_not_called()


@pytest.mark.asyncio
async def test_store_arc_concurrent_conflicting_duplicate_detected_via_validator(
    store: CouchDB, mock_client_instance: MagicMock
) -> None:
    """Validator raises DuplicateArcError when a concurrent write has different content.

    The initial get_document returns a doc from a *previous* harvest (early check
    passes). On retry, the validator sees the same harvest_id with conflicting
    content and must abort.
    """
    rdi = "test_rdi"
    harvest_id = "harvest-concurrent"
    arc_content: RoCrateContent = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [{"@id": "./", "identifier": "arc_concurrent", "name": "ours"}],
    }
    conflicting_content: RoCrateContent = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [{"@id": "./", "identifier": "arc_concurrent", "name": "theirs"}],
    }
    mock_client_instance.get_document.return_value = _make_existing_arc_doc(
        rdi, arc_content, last_harvest_id="harvest-previous"
    )
    mock_client_instance.save_document.return_value = {"ok": True}

    await store.store_arc(rdi, arc_content, "arc_concurrent", harvest_id=harvest_id)

    _, kwargs = mock_client_instance.save_document.call_args
    validator = kwargs.get("pre_save_validator")
    assert validator is not None, "store_arc must pass pre_save_validator when harvest_id is set"

    fresh_doc_with_concurrent_write = {
        "arc_content": conflicting_content,
        "metadata": {"last_harvest_id": harvest_id},
    }
    with pytest.raises(DuplicateArcError, match="different content"):
        validator(fresh_doc_with_concurrent_write)


@pytest.mark.asyncio
async def test_store_arc_concurrent_identical_resubmit_allowed_via_validator(
    store: CouchDB, mock_client_instance: MagicMock
) -> None:
    """Validator allows concurrent write when the fresh document has identical content."""
    rdi = "test_rdi"
    harvest_id = "harvest-concurrent"
    arc_content: RoCrateContent = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [{"@id": "./", "identifier": "arc_concurrent"}],
    }
    mock_client_instance.get_document.return_value = _make_existing_arc_doc(
        rdi, arc_content, last_harvest_id="harvest-previous"
    )
    mock_client_instance.save_document.return_value = {"ok": True}

    await store.store_arc(rdi, arc_content, "arc_concurrent", harvest_id=harvest_id)

    _, kwargs = mock_client_instance.save_document.call_args
    validator = kwargs.get("pre_save_validator")
    assert validator is not None

    fresh_doc_identical = {
        "arc_content": arc_content,
        "metadata": {"last_harvest_id": harvest_id},
    }
    validator(fresh_doc_identical)  # must not raise


@pytest.mark.asyncio
async def test_store_arc_same_arc_different_harvest_is_allowed(store: CouchDB, mock_client_instance: MagicMock) -> None:
    """store_arc allows re-submitting an ARC that was seen in a *different* harvest."""
    rdi = "test_rdi"
    arc_content: RoCrateContent = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [{"@id": "./", "identifier": "arc_dup"}],
    }
    mock_client_instance.get_document.return_value = _make_existing_arc_doc(
        rdi, arc_content, last_harvest_id="harvest-previous"
    )
    mock_client_instance.save_document.return_value = {"ok": True}

    result = await store.store_arc(rdi, arc_content, "arc_dup", harvest_id="harvest-new")

    assert result.is_new is False
    mock_client_instance.save_document.assert_called_once()


@pytest.mark.asyncio
async def test_store_arc_no_harvest_context_allows_resubmit(store: CouchDB, mock_client_instance: MagicMock) -> None:
    """store_arc never raises DuplicateArcError for stand-alone ARC submissions (no harvest_id)."""
    rdi = "test_rdi"
    arc_content: RoCrateContent = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [{"@id": "./", "identifier": "arc_dup"}],
    }
    mock_client_instance.get_document.return_value = _make_existing_arc_doc(
        rdi, arc_content, last_harvest_id="harvest-any"
    )
    mock_client_instance.save_document.return_value = {"ok": True}

    result = await store.store_arc(rdi, arc_content, "arc_dup", harvest_id=None)

    assert result.is_new is False
    mock_client_instance.save_document.assert_called_once()


@pytest.mark.asyncio
async def test_add_event_trimming(store: CouchDB, mock_client_instance: MagicMock) -> None:  # noqa: ARG001
    """Test that event log is trimmed according to configuration."""
    limit = 2
    # Set a small limit (pylint: disable=protected-access)
    store._config.max_event_log_size = limit  # noqa: SLF001

    arc_id = "some_id"

    now = datetime.now(UTC)
    initial_doc = ArcDocument(
        doc_id=f"arc_{arc_id}",
        rdi="test_rdi",
        arc_content={},
        metadata=ArcMetadata(
            arc_hash="abc",
            status=ArcLifecycleStatus.ACTIVE,
            first_seen=now,
            last_seen=now,
            last_changed=now,
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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "meta_patch, expected_new, expected_updated, expected_unchanged",
    [
        # ARC created in this harvest
        ({"first_harvest_id": "h1", "last_changed_harvest_id": "h1"}, 1, 0, 0),
        # ARC updated in this harvest (existed before)
        ({"first_harvest_id": "h0", "last_changed_harvest_id": "h1"}, 0, 1, 0),
        # ARC seen but unchanged
        ({"first_harvest_id": "h0", "last_changed_harvest_id": "h0"}, 0, 0, 1),
        # ARC seen but last_changed_harvest_id is None (old document, no field)
        ({"first_harvest_id": "h0", "last_changed_harvest_id": None}, 0, 0, 1),
    ],
)
async def test_get_harvest_statistics(  # noqa: PLR0913, PLR0917
    store: CouchDB,
    mock_client_instance: MagicMock,
    meta_patch: dict,
    expected_new: int,
    expected_updated: int,
    expected_unchanged: int,
) -> None:
    """get_harvest_statistics classifies ARCs via first_harvest_id and last_changed_harvest_id."""
    harvest_id = "h1"
    mock_client_instance.find_projected = AsyncMock(return_value=[{"metadata": meta_patch}])

    stats = await store.get_harvest_statistics(harvest_id)

    mock_client_instance.find_projected.assert_awaited_once_with(
        {"doc_type": "arc", "metadata.last_harvest_id": harvest_id},
        fields=["metadata.first_harvest_id", "metadata.last_changed_harvest_id"],
    )

    assert stats.arcs_submitted == 1
    assert stats.arcs_new == expected_new
    assert stats.arcs_updated == expected_updated
    assert stats.arcs_unchanged == expected_unchanged
