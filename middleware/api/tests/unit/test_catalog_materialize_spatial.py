"""Unit tests for Study Bounding Box → root spatialCoverage materialization."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import cast

from middleware.api.arc_store.consolidated_git.catalog_jsonld import (
    build_catalog_compact_context,
    build_catalog_emitted_context,
    compact_catalog_dataset,
)
from middleware.api.arc_store.consolidated_git.catalog_materialize import materialize_catalog_dataset
from middleware.api.arc_store.consolidated_git.catalog_serialize import extract_catalog_dataset
from middleware.api.arc_store.consolidated_git.schema_org_context import load_schema_org_context
from middleware.shared.json_types import RoCrateContent


def _spatial_bbox_arc(
    *,
    study_boxes: list[tuple[str, str]],
    existing_coverage: Mapping[str, object] | None = None,
    invalid_box: str | None = None,
) -> RoCrateContent:
    graph: list[dict[str, object]] = []
    has_part: list[dict[str, str]] = []
    for index, box_text in study_boxes:
        study_id = f"studies/study-{index}/"
        process_id = f"#Process_bbox_{index}"
        param_id = f"#ParameterValue_Bounding_Box_{index}"
        graph.append({
            "@id": param_id,
            "@type": "PropertyValue",
            "additionalType": "ParameterValue",
            "name": "Bounding Box",
            "value": box_text,
        })
        graph.append({
            "@id": process_id,
            "@type": "LabProcess",
            "name": f"bbox_{index}",
            "parameterValue": {"@id": param_id},
        })
        graph.append({
            "@id": study_id,
            "@type": "Dataset",
            "additionalType": "Study",
            "identifier": f"study-{index}",
            "name": f"Study {index}",
            "about": {"@id": process_id},
        })
        has_part.append({"@id": study_id})
    if invalid_box is not None:
        graph.append({
            "@id": "#ParameterValue_Bounding_Box_bad",
            "@type": "PropertyValue",
            "additionalType": "ParameterValue",
            "name": "Bounding Box",
            "value": invalid_box,
        })
        graph.append({
            "@id": "#Process_bbox_bad",
            "@type": "LabProcess",
            "name": "bbox_bad",
            "parameterValue": {"@id": "#ParameterValue_Bounding_Box_bad"},
        })
        graph.append({
            "@id": "studies/study-bad/",
            "@type": "Dataset",
            "additionalType": "Study",
            "identifier": "study-bad",
            "about": {"@id": "#Process_bbox_bad"},
        })
        has_part.append({"@id": "studies/study-bad/"})
    root: dict[str, object] = {
        "@id": "./",
        "@type": "Dataset",
        "identifier": "DS-SPATIAL",
        "name": "Spatial dataset",
        "hasPart": has_part,
    }
    if existing_coverage is not None:
        root["spatialCoverage"] = existing_coverage
    graph.append(root)
    return cast(RoCrateContent, {"@context": "https://w3id.org/ro/crate/1.1/context", "@graph": graph})


def test_materialize_spatial_coverage_union_from_study_bounding_boxes() -> None:
    """Root spatialCoverage is the axis-aligned union of Study Bounding Box params."""
    # ParameterValue text is schema.org box order (south west north east); source mapping is harvester-side.
    arc = _spatial_bbox_arc(study_boxes=[("a", "48 8 49 9"), ("b", "48.5 8.5 50 10")])
    record = materialize_catalog_dataset(extract_catalog_dataset(arc), arc)
    coverage = record.get("spatialCoverage")
    assert isinstance(coverage, dict)
    assert coverage.get("@type") == "Place"
    geo = coverage.get("geo")
    assert isinstance(geo, dict)
    assert geo.get("@type") == "GeoShape"
    assert geo.get("box") == "48 8 50 10"
    has_parts = record.get("hasPart")
    assert isinstance(has_parts, list) and len(has_parts) == 2
    for part in has_parts:
        assert isinstance(part, dict)
        assert "spatialCoverage" not in part
        assert "about" not in part


def test_materialize_spatial_coverage_comma_separated_string() -> None:
    """Comma-separated schema.org box strings are accepted."""
    arc = _spatial_bbox_arc(study_boxes=[("a", "48,8,49,9")])
    record = materialize_catalog_dataset(extract_catalog_dataset(arc), arc)
    coverage = record.get("spatialCoverage")
    assert isinstance(coverage, dict)
    geo = coverage.get("geo")
    assert isinstance(geo, dict)
    assert geo.get("box") == "48 8 49 9"


def test_materialize_spatial_coverage_numeric_list_value() -> None:
    """Four-number list ParameterValue values are accepted (not only strings)."""
    arc = cast(
        RoCrateContent,
        {
            "@context": "https://w3id.org/ro/crate/1.1/context",
            "@graph": [
                {
                    "@id": "#ParameterValue_Bounding_Box_list",
                    "@type": "PropertyValue",
                    "additionalType": "ParameterValue",
                    "name": "Bounding Box",
                    "value": [48, 8, 49, 9],
                },
                {
                    "@id": "#Process_bbox_list",
                    "@type": "LabProcess",
                    "name": "bbox_list",
                    "parameterValue": {"@id": "#ParameterValue_Bounding_Box_list"},
                },
                {
                    "@id": "studies/study-list/",
                    "@type": "Dataset",
                    "additionalType": "Study",
                    "identifier": "study-list",
                    "about": {"@id": "#Process_bbox_list"},
                },
                {
                    "@id": "./",
                    "@type": "Dataset",
                    "identifier": "DS-SPATIAL-LIST",
                    "hasPart": {"@id": "studies/study-list/"},
                },
            ],
        },
    )
    record = materialize_catalog_dataset(extract_catalog_dataset(arc), arc)
    coverage = record.get("spatialCoverage")
    assert isinstance(coverage, dict)
    geo = coverage.get("geo")
    assert isinstance(geo, dict)
    assert geo.get("box") == "48 8 49 9"


def test_materialize_spatial_coverage_skips_invalid_and_absent() -> None:
    """Unparseable boxes are skipped; no boxes → no invented spatialCoverage."""
    empty = _spatial_bbox_arc(study_boxes=[])
    assert "spatialCoverage" not in materialize_catalog_dataset(extract_catalog_dataset(empty), empty)

    invalid_only = _spatial_bbox_arc(study_boxes=[], invalid_box="not-a-box")
    assert "spatialCoverage" not in materialize_catalog_dataset(extract_catalog_dataset(invalid_only), invalid_only)


def test_materialize_spatial_coverage_preserves_existing() -> None:
    """Existing root spatialCoverage is not overwritten."""
    existing = {"@type": "Place", "geo": {"@type": "GeoShape", "box": "1 2 3 4"}}
    arc = _spatial_bbox_arc(study_boxes=[("a", "48 8 49 9")], existing_coverage=existing)
    record = materialize_catalog_dataset(extract_catalog_dataset(arc), arc)
    assert record.get("spatialCoverage") == existing


def test_materialize_spatial_coverage_survives_compact() -> None:
    """Derived spatialCoverage keeps schema.org short names after compact."""
    arc = _spatial_bbox_arc(study_boxes=[("a", "48 8 49 9")])
    materialized = materialize_catalog_dataset(extract_catalog_dataset(arc), arc)
    compacted = compact_catalog_dataset(
        materialized,
        build_catalog_compact_context(load_schema_org_context()),
        emitted_context=build_catalog_emitted_context(),
    )
    coverage = compacted.get("spatialCoverage")
    assert isinstance(coverage, dict)
    assert coverage.get("type") == "Place" or coverage.get("@type") == "Place"
    geo = coverage.get("geo")
    assert isinstance(geo, dict)
    assert geo.get("box") == "48 8 49 9"
    data_without_context = {key: value for key, value in compacted.items() if key != "@context"}
    dumped = json.dumps(data_without_context)
    assert "PropertyValue" not in dumped
    assert "LabProcess" not in dumped
    assert "#ParameterValue_Bounding_Box" not in dumped
