"""Unit tests for API-layer RO-Crate parsing."""

from rocrate_fixtures import minimal_rocrate_dict

from middleware.api.rocrate import parse_rocrate


def test_parse_rocrate_validates_wire_format() -> None:
    """parse_rocrate applies RoCratePayload validation without arctrl parsing."""
    payload = parse_rocrate(minimal_rocrate_dict("ARC-001"))
    assert payload.identifier == "ARC-001"
