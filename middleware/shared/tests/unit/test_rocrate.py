"""Unit tests for RO-Crate payload validation."""

import pytest
from pydantic import ValidationError

from middleware.shared.api_models.common.rocrate import RoCratePayload

_MINIMAL_ROCRATE = {
    "@context": "https://w3id.org/ro/crate/1.1/context",
    "@graph": [{"@id": "./", "identifier": "AthalianaColdStressSugar"}],
}


def test_rocrate_payload_accepts_wire_format_only() -> None:
    """RoCratePayload mirrors top-level JSON-LD keys only."""
    payload = RoCratePayload.model_validate(_MINIMAL_ROCRATE)
    dumped = payload.model_dump(by_alias=True)
    assert "@context" in dumped
    assert "@graph" in dumped
    assert "identifier" not in dumped


def test_rocrate_payload_identifier() -> None:
    """Validated identifier is read from the root data entity path."""
    payload = RoCratePayload.model_validate(_MINIMAL_ROCRATE)
    assert payload.identifier == "AthalianaColdStressSugar"


def test_rocrate_payload_name() -> None:
    """Optional RO-Crate ``name`` is extracted from the root data entity."""
    arc = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [
            {
                "@id": "./",
                "identifier": "AthalianaColdStressSugar",
                "name": "Arabidopsis thaliana cold acclimation",
            }
        ],
    }
    assert RoCratePayload.model_validate(arc).name == "Arabidopsis thaliana cold acclimation"


def test_rocrate_payload_missing_name_is_none() -> None:
    """Missing RO-Crate ``name`` is represented as None."""
    assert RoCratePayload.model_validate(_MINIMAL_ROCRATE).name is None


def test_rocrate_payload_description() -> None:
    """Optional RO-Crate ``description`` is extracted from the root data entity."""
    arc = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [
            {
                "@id": "./",
                "identifier": "dataset-1",
                "description": "Cold stress experiment",
            }
        ],
    }
    assert RoCratePayload.model_validate(arc).description == "Cold stress experiment"


@pytest.mark.parametrize(
    ("field", "wire_value", "expected"),
    [
        ("identifier", {"@value": "dataset-jsonld"}, "dataset-jsonld"),
        ("name", {"@value": "Study title"}, "Study title"),
        ("description", {"@value": "Study summary"}, "Study summary"),
    ],
)
def test_rocrate_payload_jsonld_value_objects(field: str, wire_value: object, expected: str) -> None:
    """JSON-LD value objects for text fields are normalized to plain strings."""
    root: dict[str, object] = {"@id": "./"}
    if field == "identifier":
        root["identifier"] = wire_value
    else:
        root["identifier"] = "dataset-1"
        root[field] = wire_value
    arc = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [root],
    }
    payload = RoCratePayload.model_validate(arc)
    assert getattr(payload, field) == expected


def test_rocrate_payload_preserves_extra_root_fields() -> None:
    """Root entity fields beyond the API contract remain in ``@graph`` unchanged."""
    arc = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [
            {
                "@id": "./",
                "@type": "Dataset",
                "additionalType": "Investigation",
                "identifier": "dataset-1",
                "name": "Example study",
                "license": {"@id": "#LICENSE"},
                "datePublished": "2025-12-09T13:41:46.875",
            }
        ],
    }
    payload = RoCratePayload.model_validate(arc)
    root = payload.model_dump(by_alias=True)["@graph"][0]
    assert root["@type"] == "Dataset"
    assert root["additionalType"] == "Investigation"
    assert root["license"] == {"@id": "#LICENSE"}
    assert root["datePublished"] == "2025-12-09T13:41:46.875"


def test_rocrate_payload_rejects_extra_top_level_fields() -> None:
    """RO-Crate metadata documents must not contain keys beyond @context and @graph."""
    arc = {**_MINIMAL_ROCRATE, "unexpected": "field"}
    with pytest.raises(ValidationError):
        RoCratePayload.model_validate(arc)


@pytest.mark.parametrize(
    "arc",
    [
        {"@context": "https://w3id.org/ro/crate/1.1/context"},
        {
            "@graph": [
                {"@id": "./", "identifier": "ARC-006"},
            ]
        },
        {
            "@context": "https://w3id.org/ro/crate/1.1/context",
            "@graph": [{"@id": "ro-crate-metadata.json", "@type": "CreativeWork"}],
        },
        {
            "@context": "https://w3id.org/ro/crate/1.1/context",
            "@graph": [{"@id": "./"}],
        },
        {
            "@context": "https://w3id.org/ro/crate/1.1/context",
            "@graph": [{"@id": "./", "identifier": ""}],
        },
    ],
)
def test_rocrate_payload_rejects_invalid_structure(arc: dict[str, object]) -> None:
    """Reject RO-Crate payloads that violate the API contract."""
    with pytest.raises(ValidationError):
        RoCratePayload.model_validate(arc)
