"""
Unit tests for the HarvestDocument schema in the Middleware API.

This module contains tests to validate the instantiation, validation, and
aliasing behavior of the HarvestDocument schema.
"""

from datetime import datetime

from middleware.api.document_store.harvest_document import HarvestDocument, HarvestStatistics
from middleware.shared.api_models.common.models import HarvestStatus

ARCS_SUBMITTED = 10
GRACE_PERIOD_DAYS = 7


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
