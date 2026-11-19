"""
Unit tests for the HarvestDocument schema in the Middleware API.

This module contains tests to validate the instantiation, validation, and
aliasing behavior of the HarvestDocument schema.
"""

from datetime import datetime

import pytest
from pydantic import ValidationError

from middleware.api.document_store.harvest_document import (
    CatalogPushEventType,
    HarvestCatalogEvent,
    HarvestDocument,
    HarvestStatistics,
)
from middleware.shared.api_models.common.models import HarvestStatus
from middleware.shared.api_models.v3.models import HarvestError, HarvestErrorType

ARCS_SUBMITTED = 10


def test_harvest_document_instantiation() -> None:
    """Test that HarvestDocument can be instantiated and validated."""
    now = datetime.now()
    stats = HarvestStatistics(arcs_submitted=ARCS_SUBMITTED, arcs_new=5)

    doc = HarvestDocument(
        doc_id="harvest-123",
        rdi="test-rdi",
        client_id="test-client",
        started_at=now,
        status=HarvestStatus.RUNNING,
        statistics=stats,
    )

    assert doc.doc_id == "harvest-123"
    assert doc.rdi == "test-rdi"
    assert doc.client_id == "test-client"
    assert doc.status == HarvestStatus.RUNNING
    assert doc.statistics.arcs_submitted == ARCS_SUBMITTED
    assert doc.type == "harvest"


def test_harvest_document_alias() -> None:
    """Test that HarvestDocument correctly uses aliases for CouchDB fields."""
    now = datetime.now()
    stats = HarvestStatistics(arcs_submitted=ARCS_SUBMITTED, arcs_new=5)

    doc = HarvestDocument(
        doc_id="harvest-123",
        doc_rev="1-abc",
        rdi="test-rdi",
        client_id="test-client",
        started_at=now,
        status=HarvestStatus.COMPLETED,
        statistics=stats,
    )

    assert doc.doc_id == "harvest-123"
    assert doc.doc_rev == "1-abc"

    # Test export with aliases
    dump = doc.model_dump(by_alias=True)
    assert dump["_id"] == "harvest-123"
    assert dump["_rev"] == "1-abc"


# Older on-disk harvest shapes: see middleware/api/tests/fixtures/store_docs/ (#652).


def test_harvest_document_stores_errors() -> None:
    """HarvestDocument retains typed per-item errors."""
    now = datetime.now()
    doc = HarvestDocument(
        doc_id="harvest-err",
        rdi="test-rdi",
        started_at=now,
        status=HarvestStatus.RUNNING,
        errors=[
            HarvestError(
                arc_id="ARC-1",
                error_type=HarvestErrorType.DUPLICATE,
                message="conflict",
                timestamp="2024-01-01T00:00:00Z",
            )
        ],
    )
    assert len(doc.errors) == 1
    assert doc.errors[0].error_type is HarvestErrorType.DUPLICATE


def test_harvest_catalog_event_accepts_known_types() -> None:
    """Catalog flush events accept the CATALOG_PUSH_* outcomes including SKIPPED."""
    success = HarvestCatalogEvent(
        timestamp=datetime.now(),
        type=CatalogPushEventType.CATALOG_PUSH_SUCCESS,
        message="ok",
    )
    skipped = HarvestCatalogEvent(
        timestamp=datetime.now(),
        type=CatalogPushEventType.CATALOG_PUSH_SKIPPED,
        message="unchanged",
    )
    assert success.type is CatalogPushEventType.CATALOG_PUSH_SUCCESS
    assert skipped.type is CatalogPushEventType.CATALOG_PUSH_SKIPPED


def test_harvest_catalog_event_rejects_unknown_type() -> None:
    """Invalid catalog event types must fail validation."""
    with pytest.raises(ValidationError):
        HarvestCatalogEvent.model_validate({
            "timestamp": datetime.now().isoformat(),
            "type": "GIT_PUSH_SUCCESS",
            "message": "wrong domain",
        })
