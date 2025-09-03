import json
from typing import Any
import pytest

from app.middleware_service import (
    ARCResponse,
    CreateOrUpdateResponse,
    InvalidJsonSemanticError,
    InvalidJsonSyntaxError,
    MiddlewareService
)


def is_valid_sha256(s: str) -> bool:
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
async def test_success(service: MiddlewareService, rocrate: list[dict[str, Any]]):
    result = await service.create_or_update_arcs(
        data=json.dumps(rocrate),
        client_id="TestClient")

    assert isinstance(result, CreateOrUpdateResponse) # nosec
    assert result.client_id == "TestClient" # nosec
    assert isinstance(result.arcs, list) # nosec
    assert all(isinstance(a, ARCResponse) for a in result.arcs) # nosec
    assert len(result.arcs) == len(rocrate) # nosec
    assert all(is_valid_sha256(a.id) for a in result.arcs) # nosec
    assert all(a.status == "created" for a in result.arcs) # nosec


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
async def test_invalid_json(service: MiddlewareService, rocrate: str | dict[str, Any]):
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
async def test_element_missing(service: MiddlewareService, cert: str, rocrate: list[dict[str, Any]]):
    with pytest.raises(InvalidJsonSemanticError):
        await service.create_or_update_arcs(
            data=json.dumps(rocrate),
            client_id="TestClient")
