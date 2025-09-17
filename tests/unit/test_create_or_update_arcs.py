"""Unit tests for the create_or_update_arcs functionality in BusinessLogic."""

import json
from typing import Any
from unittest.mock import patch
import pytest

from middleware_api.business_logic import (
    ArcResponse,
    CreateOrUpdateArcsResponse,
    InvalidJsonSemanticError,
    InvalidJsonSyntaxError,
    BusinessLogic
)


def is_valid_sha256(s: str) -> bool:
    """Check if a string is a valid SHA-256 hash."""
    if len(s) != 64:
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
        [],  # Empty list
        [{  # One item
            "@context": "https://w3id.org/ro/crate/1.1/context",
            "@graph": [
                {
                    "@id": "./",
                    "@type": "Dataset",
                    "additionalType": "Investigation",
                    "identifier": "ARC-001"
                },
                {
                    "@id": "ro-crate-metadata.json",
                    "@type": "CreativeWork",
                    "conformsTo": {"@id": "https://w3id.org/ro/crate/1.1"},
                    "about": {"@id": "./"}
                }
            ]
        }],
        [{  # Multiple items
            "@context": "https://w3id.org/ro/crate/1.1/context",
            "@graph": [
                {
                    "@id": "./",
                    "@type": "Dataset",
                    "additionalType": "Investigation",
                    "identifier": "ARC-004"
                },
                {
                    "@id": "ro-crate-metadata.json",
                    "@type": "CreativeWork",
                    "conformsTo": {"@id": "https://w3id.org/ro/crate/1.1"},
                    "about": {"@id": "./"}
                }
            ]
        }, {
            "@context": "https://w3id.org/ro/crate/1.1/context",
            "@graph": [
                {
                    "@id": "./",
                    "@type": "Dataset",
                    "additionalType": "Investigation",
                    "identifier": "ARC-005"
                },
                {
                    "@id": "ro-crate-metadata.json",
                    "@type": "CreativeWork",
                    "conformsTo": {"@id": "https://w3id.org/ro/crate/1.1"},
                    "about": {"@id": "./"}
                }
            ]
        }]
    ]
)
async def test_create_arc_success(
        service: BusinessLogic, rocrate: list[dict[str, Any]]):
    """Test creating ARCs with valid RO-Crate JSON."""
    result = await service.create_or_update_arcs(
        data=json.dumps(rocrate),
        client_id="TestClient")

    assert isinstance(result, CreateOrUpdateArcsResponse) # nosec
    assert result.client_id == "TestClient" # nosec
    assert isinstance(result.arcs, list) # nosec
    assert all(isinstance(a, ArcResponse) for a in result.arcs) # nosec
    assert len(result.arcs) == len(rocrate) # nosec
    assert all(is_valid_sha256(a.id) for a in result.arcs) # nosec
    assert all(a.status == "created" for a in result.arcs) # nosec

@pytest.mark.asyncio
async def test_update_arc_success(service: BusinessLogic):
    """Test updating an existing ARC."""
    rocrate = [{  # One item
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [
            {
                "@id": "./",
                "@type": "Dataset",
                "additionalType": "Investigation",
                "identifier": "ARC-001"
            },
            {
                "@id": "ro-crate-metadata.json",
                "@type": "CreativeWork",
                "conformsTo": {"@id": "https://w3id.org/ro/crate/1.1"},
                "about": {"@id": "./"}
            }
        ]
    }]

    with patch.object(service._store, "exists", return_value=True):
        result = await service.create_or_update_arcs(
            data=json.dumps(rocrate),
            client_id="TestClient")

        assert isinstance(result, CreateOrUpdateArcsResponse) # nosec
        assert result.client_id == "TestClient" # nosec
        assert isinstance(result.arcs, list) # nosec
        assert all(isinstance(a, ArcResponse) for a in result.arcs) # nosec
        assert len(result.arcs) == len(rocrate) # nosec
        assert all(is_valid_sha256(a.id) for a in result.arcs) # nosec
        assert all(a.status == "updated" for a in result.arcs) # nosec


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "rocrate",
    [
        "not a valid json",  # Invalid JSON syntax
        {   # Not a list
            "@context": "https://w3id.org/ro/crate/1.1/context",
            "@graph": [
                {
                    "@id": "./",
                    "@type": "Dataset",
                    "additionalType": "Investigation",
                    "identifier": "ARC-006"
                },
                {
                    "@id": "ro-crate-metadata.json",
                    "@type": "CreativeWork",
                    "conformsTo": {"@id": "https://w3id.org/ro/crate/1.1"},
                    "about": {"@id": "./"}
                }
            ]
        }
    ]
)
async def test_invalid_json(service: BusinessLogic, rocrate: str | dict[str, Any]):
    """Test handling of invalid JSON syntax or structure."""
    # Send invalid JSON (not a list)
    with pytest.raises(InvalidJsonSyntaxError):
        await service.create_or_update_arcs(
            data=json.dumps(rocrate) if isinstance(rocrate, dict) else rocrate,
            client_id="TestClient")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "rocrate",
    [
        [{  # No @graph
            "@context": "https://w3id.org/ro/crate/1.1/context"
        }],
        [{  # No @context
            "@graph": [
                {
                    "@id": "./",
                    "@type": "Dataset",
                    "additionalType": "Investigation",
                    "identifier": "ARC-006"
                },
                {
                    "@id": "ro-crate-metadata.json",
                    "@type": "CreativeWork",
                    "conformsTo": {"@id": "https://w3id.org/ro/crate/1.1"},
                    "about": {"@id": "./"}
                }
            ]
        }],
        [{  # No Dataset
            "@context": "https://w3id.org/ro/crate/1.1/context",
            "@graph": [
                {
                    "@id": "ro-crate-metadata.json",
                    "@type": "CreativeWork",
                    "about": {"@id": "./"}
                }
            ]
        }],
        [{
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
                    "about": {"@id": "./"}
                }
            ]
        }]
    ]
)
async def test_element_missing(
        service: BusinessLogic, cert: str, rocrate: list[dict[str, Any]]):
    """Test handling of RO-Crate JSON missing required elements."""
    with pytest.raises(InvalidJsonSemanticError):
        await service.create_or_update_arcs(
            data=json.dumps(rocrate),
            client_id="TestClient")
