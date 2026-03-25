"""
Unit tests for the HarvestDocument schema in the Middleware API.

This module contains tests to validate the instantiation, validation, and
aliasing behavior of the HarvestDocument schema.
"""

from datetime import datetime
from typing import Any

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


def test_harvest_document_backward_compat_no_client_id() -> None:
    """Old CouchDB documents pre-date the 'client_id' field entirely.

    Such documents must be parsed without error; client_id falls back
    to None because we have no way to recover the original client identity.
    The unrelated old 'source' field (data-source system name, not client
    identity) must be silently ignored via extra='ignore'.
    """
    now = datetime.now()
    old_doc: dict[str, Any] = {
        "_id": "harvest-old-001",
        "_rev": "1-abc",
        "type": "harvest",
        "rdi": "test-rdi",
        "source": "edaphobase",  # old field — different semantics, must be dropped
        "started_at": now.isoformat(),
        "status": HarvestStatus.COMPLETED,
        "statistics": {"arcs_submitted": 3},
    }

    doc = HarvestDocument.model_validate(old_doc)

    assert doc.client_id is None
    assert doc.doc_id == "harvest-old-001"
    assert doc.statistics.arcs_submitted == 3  # noqa: PLR2004


def test_harvest_document_backward_compat_config_field_ignored() -> None:
    """Old CouchDB documents contain a 'config' sub-document.

    The new schema does not have this field; it must be silently ignored
    rather than raising a validation error.
    """
    now = datetime.now()
    old_doc: dict[str, Any] = {
        "_id": "harvest-old-002",
        "type": "harvest",
        "rdi": "test-rdi",
        "source": "edaphobase",
        "started_at": now.isoformat(),
        "status": HarvestStatus.RUNNING,
        "statistics": {},
        "config": {  # old nested object not present in new schema
            "grace_period_days": 3,
            "auto_mark_deleted": True,
        },
    }

    doc = HarvestDocument.model_validate(old_doc)

    assert doc.client_id is None
    # Neither 'config' nor 'source' must appear on the new model
    assert not hasattr(doc, "config")
    assert not hasattr(doc, "source")
