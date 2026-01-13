"""Unit tests for shared API models."""

from middleware.shared.api_models.models import (
    ArcStatus,
    CreateOrUpdateArcsRequest,
    LivenessResponse,
)


def test_liveness_response_default() -> None:
    """Test creating a LivenessResponse with default message."""
    response = LivenessResponse()
    assert response.message == "ok"


def test_liveness_response_custom_message() -> None:
    """Test creating a LivenessResponse with custom message."""
    response = LivenessResponse(message="service is running")
    assert response.message == "service is running"


def test_create_or_update_arcs_request() -> None:
    """Test creating a CreateOrUpdateArcsRequest."""
    arcs_data = [
        {"identifier": "1", "title": "ARC 1"},
        {"identifier": "2", "title": "ARC 2"},
    ]

    request = CreateOrUpdateArcsRequest(rdi="edaphobase", arcs=arcs_data)

    assert request.rdi == "edaphobase"
    assert len(request.arcs) == 2  # noqa: PLR2004
    assert request.arcs[0]["identifier"] == "1"
    assert request.arcs[1]["identifier"] == "2"


def test_arc_status_enum() -> None:
    """Test ArcStatus enum values."""
    assert ArcStatus.CREATED == "created"
    assert ArcStatus.UPDATED == "updated"
    assert ArcStatus.DELETED == "deleted"
    assert ArcStatus.REQUESTED == "requested"


def test_arc_status_enum_all_values() -> None:
    """Test that all ArcStatus values are present."""
    statuses = [status.value for status in ArcStatus]
    assert "created" in statuses
    assert "updated" in statuses
    assert "deleted" in statuses
    assert "requested" in statuses
    assert len(statuses) == 4  # noqa: PLR2004
