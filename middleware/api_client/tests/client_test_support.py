"""Shared helpers for ApiClient unit tests (not a pytest plugin)."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from arctrl import ARC  # type: ignore[import-untyped]

ARC_RESPONSE = {
    "client_id": "test-client",
    "message": "ARC processed successfully",
    "arc_id": "arc-123",
    "status": "created",
    "metadata": {
        "arc_hash": "abc123",
        "status": "ACTIVE",
        "first_seen": "2024-01-01T00:00:00Z",
        "last_seen": "2024-01-01T00:00:00Z",
    },
    "events": [],
}

HARVEST_RESPONSE: dict[str, str | None | dict] = {
    "client_id": "test-client",
    "message": "Harvest created",
    "harvest_id": "harvest-456",
    "rdi": "test-rdi",
    "status": "RUNNING",
    "started_at": "2024-01-01T00:00:00Z",
    "completed_at": None,
    "statistics": {},
}

EXPECTED_ARC_UPLOADS = 3


def rocrate_dict(identifier: str = "mock-arc") -> dict[str, Any]:
    """Minimal valid RO-Crate payload for client tests."""
    return {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [{"@id": "./", "identifier": identifier}],
    }


async def arc_gen(*arcs: dict[str, Any] | str | ARC) -> AsyncGenerator[dict[str, Any] | str | ARC, None]:
    """Yield the provided arc dicts, JSON strings, or ARC objects as an async generator."""
    for arc in arcs:
        yield arc
