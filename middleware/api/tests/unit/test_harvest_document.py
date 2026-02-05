"""
Unit tests for the HarvestDocument schema in the Middleware API.

This module contains tests to validate the instantiation, validation, and
aliasing behavior of the HarvestDocument schema.
"""

from datetime import datetime

from middleware.api.schemas import HarvestStatus
from middleware.api.schemas.harvest_document import HarvestConfig, HarvestDocument, HarvestStatistics

ARCS_SUBMITTED = 10
GRACE_PERIOD_DAYS = 7


def test_harvest_document_instantiation() -> None:
    """Test that HarvestDocument can be instantiated and validated."""
    now = datetime.now()
    stats = HarvestStatistics(arcs_submitted=ARCS_SUBMITTED, arcs_new=5)
    config = HarvestConfig(grace_period_days=GRACE_PERIOD_DAYS)

    doc = HarvestDocument(
        doc_id="harvest-123",
        rdi="test-rdi",
        source="test-source",
        started_at=now,
        status=HarvestStatus.RUNNING,
        statistics=stats,
        config=config,
    )

    assert doc.doc_id == "harvest-123"
    assert doc.rdi == "test-rdi"
    assert doc.status == HarvestStatus.RUNNING
    assert doc.statistics.arcs_submitted == ARCS_SUBMITTED
    assert doc.config.grace_period_days == GRACE_PERIOD_DAYS
    assert doc.type == "harvest"


def test_harvest_document_alias() -> None:
    """Test that HarvestDocument correctly uses aliases for CouchDB fields."""
    now = datetime.now()
    stats = HarvestStatistics(arcs_submitted=ARCS_SUBMITTED, arcs_new=5)
    config = HarvestConfig(grace_period_days=GRACE_PERIOD_DAYS)

    doc = HarvestDocument(
        doc_id="harvest-123",
        doc_rev="1-abc",
        rdi="test-rdi",
        source="test-source",
        started_at=now,
        status=HarvestStatus.COMPLETED,
        statistics=stats,
        config=config,
    )

    assert doc.doc_id == "harvest-123"
    assert doc.doc_rev == "1-abc"

    # Test export with aliases
    dump = doc.model_dump(by_alias=True)
    assert dump["_id"] == "harvest-123"
    assert dump["_rev"] == "1-abc"
