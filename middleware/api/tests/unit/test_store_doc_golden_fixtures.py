"""Golden fixtures: tip store models must load supported document shapes (#652)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from middleware.api.document_store.arc_document import ArcDocument
from middleware.api.document_store.harvest_document import HarvestDocument

_FIXTURES_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "store_docs"

_ALLOWLIST: dict[str, type[Any]] = {
    "harvest": HarvestDocument,
    "arc": ArcDocument,
}


def _supported_fixture_cases() -> list[pytest.ParameterSet]:
    cases: list[pytest.ParameterSet] = []
    for dirname, model in _ALLOWLIST.items():
        directory = _FIXTURES_ROOT / dirname
        assert directory.is_dir(), f"missing fixture directory {directory}"
        for path in sorted(directory.glob("*.json")):
            cases.append(pytest.param(path, model, id=f"{dirname}/{path.name}"))
    return cases


def test_allowlist_directories_exist_with_fixtures() -> None:
    """MVP allowlist covers harvest and ARC with at least one supported fixture each."""
    by_type = {name: 0 for name in _ALLOWLIST}
    for dirname, _model in _ALLOWLIST.items():
        by_type[dirname] = len(list((_FIXTURES_ROOT / dirname).glob("*.json")))
    assert by_type["harvest"] >= 1
    assert by_type["arc"] >= 1


@pytest.mark.parametrize(("path", "model"), _supported_fixture_cases())
def test_supported_fixture_validates(path: Path, model: type[Any]) -> None:
    """Every supported golden fixture must model_validate on tip."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    doc = model.model_validate(payload)
    assert doc is not None


def test_incompatible_shape_fails_validation() -> None:
    """Smoke: a still-required field missing without backfill must fail (suite guard mechanism)."""
    with pytest.raises(ValidationError):
        HarvestDocument.model_validate({
            "_id": "harvest-broken",
            "type": "harvest",
            # rdi missing — required
            "started_at": "2024-01-01T00:00:00",
            "status": "RUNNING",
        })


def test_arc_fixture_backfills_last_changed() -> None:
    """pre_last_changed fixture omits last_changed; tip backfills from last_seen."""
    path = _FIXTURES_ROOT / "arc" / "pre_last_changed.json"
    doc = ArcDocument.model_validate(json.loads(path.read_text(encoding="utf-8")))
    assert doc.metadata.last_changed == doc.metadata.last_seen


def test_harvest_fixture_ignores_legacy_source() -> None:
    """pre_client_id fixture keeps source for ignore; client_id stays None."""
    path = _FIXTURES_ROOT / "harvest" / "pre_client_id_with_source.json"
    doc = HarvestDocument.model_validate(json.loads(path.read_text(encoding="utf-8")))
    assert doc.client_id is None
    assert not hasattr(doc, "source")
