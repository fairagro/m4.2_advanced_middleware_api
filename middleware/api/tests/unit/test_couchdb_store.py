"""Unit tests for CouchDB DocumentStore."""

import hashlib
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiocouch import CouchDB as AioCouchDB
from aiocouch.exception import NotFoundError

from middleware.api.couchdb_client import CouchDBClient
from middleware.api.document_store.couchdb import CouchDB
from middleware.api.schemas.arc_document import ArcDocument, ArcLifecycleStatus


from middleware.api.config import CouchDBConfig

@pytest.fixture
def config():
    """Create test configuration."""
    return CouchDBConfig(
        url="http://test:5984",
        user="user",
        password="pass"
    )

@pytest.fixture
def mock_client_instance():
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
def store(config, mock_client_instance):
    """Create CouchDB store with mocked client."""
    # Patch where CouchDB imports CouchDBClient
    with patch("middleware.api.document_store.couchdb.CouchDBClient", return_value=mock_client_instance):
        store = CouchDB(config)
        return store


@pytest.mark.asyncio
async def test_store_arc_new(store, mock_client_instance):
    """Test storing a new ARC."""
    # Setup
    rdi = "test_rdi"
    arc_content = {
        "@graph": [
            {"@id": "./", "identifier": "arc_123"}
        ]
    }
    
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
async def test_store_arc_update_changed(store, mock_client_instance):
    """Test updating an existing ARC with changes."""
    # Setup
    rdi = "test_rdi"
    arc_content = {
        "@graph": [
            {"@id": "./", "identifier": "arc_123"},
            {"@id": "dataset", "name": "Changed Name"}
        ]
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
            "events": []
        }
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
async def test_store_arc_no_change(store, mock_client_instance):
    """Test storing an unchanged ARC."""
    # Setup
    rdi = "test_rdi"
    arc_content = {
        "@graph": [
            {"@id": "./", "identifier": "arc_123"}
        ]
    }
    
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
            "events": []
        }
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
