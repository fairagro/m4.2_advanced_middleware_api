"""Unit tests for shared API models."""

from middleware.shared.api_models import (
    ArcStatus,
    LivenessResponse,
)
from middleware.shared.api_models.common.models import HarvestStatus
from middleware.shared.api_models.v3.models import HarvestError, HarvestErrorType, HarvestResponse


def test_liveness_response_default() -> None:
    """Test creating a LivenessResponse with default message."""
    response = LivenessResponse()
    assert response.message == "ok"


def test_liveness_response_custom_message() -> None:
    """Test creating a LivenessResponse with custom message."""
    response = LivenessResponse(message="service is running")
    assert response.message == "service is running"


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


def test_harvest_response_errors_default_empty() -> None:
    """Legacy harvest payloads without errors validate with an empty list."""
    response = HarvestResponse.model_validate({
        "harvest_id": "harvest-1",
        "rdi": "rdi-1",
        "status": HarvestStatus.RUNNING,
        "started_at": "2024-01-01T00:00:00Z",
        "statistics": {},
    })
    assert response.errors == []


def test_harvest_response_errors_round_trip() -> None:
    """HarvestResponse accepts typed per-item errors on the wire."""
    response = HarvestResponse(
        harvest_id="harvest-1",
        rdi="rdi-1",
        status=HarvestStatus.COMPLETED,
        started_at="2024-01-01T00:00:00Z",
        statistics={"errors": 1},
        errors=[
            HarvestError(
                arc_id="ARC-1",
                error_type=HarvestErrorType.DUPLICATE,
                message="conflict",
                timestamp="2024-01-01T00:01:00Z",
            )
        ],
    )
    assert len(response.errors) == 1
    assert response.errors[0].error_type is HarvestErrorType.DUPLICATE
