"""Unit tests for the create_or_update_arc functionality in BusinessLogic."""

from typing import Any
from unittest.mock import AsyncMock

import pytest

from middleware.api.business_logic import (
    ArcResponse,
    BusinessLogic,
    CreateOrUpdateArcResponse,
    InvalidJsonSemanticError,
)

SHA256_LENGTH = 64


def is_valid_sha256(s: str) -> bool:
    """Check if a string is a valid SHA-256 hash."""
    if len(s) != SHA256_LENGTH:
        return False
    try:
        int(s, 16)
        return True
    except ValueError:
        return False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "rocrate",
    [
        {  # Simple ARC
            "@context": "https://w3id.org/ro/crate/1.1/context",
            "@graph": [
                {
                    "@id": "./",
                    "@type": "Dataset",
                    "additionalType": "Investigation",
                    "identifier": "ARC-001",
                },
                {
                    "@id": "ro-crate-metadata.json",
                    "@type": "CreativeWork",
                    "conformsTo": {"@id": "https://w3id.org/ro/crate/1.1"},
                    "about": {"@id": "./"},
                },
            ],
        },
        {  # Another ARC
            "@context": "https://w3id.org/ro/crate/1.1/context",
            "@graph": [
                {
                    "@id": "./",
                    "@type": "Dataset",
                    "additionalType": "Investigation",
                    "identifier": "ARC-004",
                },
                {
                    "@id": "ro-crate-metadata.json",
                    "@type": "CreativeWork",
                    "conformsTo": {"@id": "https://w3id.org/ro/crate/1.1"},
                    "about": {"@id": "./"},
                },
            ],
        },
    ],
)
async def test_create_arc_success(service: BusinessLogic, rocrate: dict[str, Any]) -> None:
    """Test creating an ARC with valid RO-Crate JSON."""
    result = await service.create_or_update_arc(rdi="TestRDI", arc=rocrate, client_id="TestClient")

    assert isinstance(result, CreateOrUpdateArcResponse)  # nosec
    assert result.client_id == "TestClient"  # nosec
    assert isinstance(result.arc, ArcResponse)  # nosec
    assert is_valid_sha256(result.arc.id)  # nosec
    assert result.arc.status == "created"  # nosec


@pytest.mark.asyncio
async def test_update_arc_success(service: BusinessLogic) -> None:
    """Test updating an existing ARC."""
    rocrate = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [
            {
                "@id": "./",
                "@type": "Dataset",
                "additionalType": "Investigation",
                "identifier": "ARC-001",
            },
            {
                "@id": "ro-crate-metadata.json",
                "@type": "CreativeWork",
                "conformsTo": {"@id": "https://w3id.org/ro/crate/1.1"},
                "about": {"@id": "./"},
            },
        ],
    }

    # pylint: disable=protected-access
    service._store.exists = AsyncMock(return_value=True)  # type: ignore
    result = await service.create_or_update_arc(rdi="TestRDI", arc=rocrate, client_id="TestClient")

    assert isinstance(result, CreateOrUpdateArcResponse)  # nosec
    assert result.client_id == "TestClient"  # nosec
    assert isinstance(result.arc, ArcResponse)  # nosec
    assert is_valid_sha256(result.arc.id)  # nosec
    assert result.arc.status == "updated"  # nosec


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "rocrate",
    [
        {"@context": "https://w3id.org/ro/crate/1.1/context"},  # No @graph
        {  # No @context
            "@graph": [
                {
                    "@id": "./",
                    "@type": "Dataset",
                    "additionalType": "Investigation",
                    "identifier": "ARC-006",
                },
                {
                    "@id": "ro-crate-metadata.json",
                    "@type": "CreativeWork",
                    "conformsTo": {"@id": "https://w3id.org/ro/crate/1.1"},
                    "about": {"@id": "./"},
                },
            ]
        },
        {  # No Dataset
            "@context": "https://w3id.org/ro/crate/1.1/context",
            "@graph": [
                {
                    "@id": "ro-crate-metadata.json",
                    "@type": "CreativeWork",
                    "about": {"@id": "./"},
                }
            ],
        },
        {
            "@context": "https://w3id.org/ro/crate/1.1/context",
            "@graph": [
                {
                    "@id": "./",
                    "@type": "Dataset",
                    "additionalType": "Investigation",
                    # Missing Identifier
                },
                {
                    "@id": "ro-crate-metadata.json",
                    "@type": "CreativeWork",
                    "conformsTo": {"@id": "https://w3id.org/ro/crate/1.1"},
                    "about": {"@id": "./"},
                },
            ],
        },
    ],
)
async def test_element_missing(service: BusinessLogic, rocrate: dict[str, Any]) -> None:
    """Test handling of RO-Crate JSON missing required elements."""
    with pytest.raises(InvalidJsonSemanticError):
        await service.create_or_update_arc(rdi="TestRDI", arc=rocrate, client_id="TestClient")
