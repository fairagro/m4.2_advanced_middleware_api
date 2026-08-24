"""RO-Crate wire-format helpers for API unit tests."""

from middleware.shared.json_types import JsonValue, RoCrateContent, RoCrateGraphNode

_ARCTRL_METADATA_ENTITY: RoCrateGraphNode = {
    "@id": "ro-crate-metadata.json",
    "@type": "CreativeWork",
    "conformsTo": {"@id": "https://w3id.org/ro/crate/1.1"},
    "about": {"@id": "./"},
}


def arctrl_metadata_descriptor() -> RoCrateGraphNode:
    """Return the RO-Crate metadata descriptor node required by arctrl."""
    return dict(_ARCTRL_METADATA_ENTITY)


def minimal_rocrate_dict(identifier: str, **root_fields: JsonValue) -> RoCrateContent:
    """Build a minimal RO-Crate wire document (arctrl-compatible for worker-path tests)."""
    root: RoCrateGraphNode = {
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
