"""RO-Crate wire-format helpers for API unit tests."""

from typing import Any

_ARCTRL_METADATA_ENTITY: dict[str, Any] = {
    "@id": "ro-crate-metadata.json",
    "@type": "CreativeWork",
    "conformsTo": {"@id": "https://w3id.org/ro/crate/1.1"},
    "about": {"@id": "./"},
}


def arctrl_metadata_descriptor() -> dict[str, Any]:
    """Return the RO-Crate metadata descriptor node required by arctrl."""
    return dict(_ARCTRL_METADATA_ENTITY)


def minimal_rocrate_dict(identifier: str, **root_fields: Any) -> dict[str, Any]:
    """Build a minimal RO-Crate wire document (arctrl-compatible for worker-path tests)."""
    root: dict[str, Any] = {
        "@id": "./",
        "@type": "Dataset",
        "additionalType": "Investigation",
        "identifier": identifier,
        **root_fields,
    }
    return {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [root, arctrl_metadata_descriptor()],
    }
