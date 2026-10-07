"""Unit tests for Investigation RDI Comment enrichment."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from arctrl import ARC, ArcInvestigation, ArcStudy, Comment
from rocrate_fixtures import minimal_rocrate_dict

from middleware.api.business_logic.exceptions import InvalidJsonSemanticError
from middleware.api.business_logic.rdi_comments import (
    COMMENT_NAME_DESCRIPTION,
    COMMENT_NAME_RDI,
    COMMENT_NAME_URL,
    enrich_investigation_rdi_comments,
)
from middleware.shared.json_types import JsonObject, RoCrateContent


def _graph_nodes(arc_content: RoCrateContent) -> list[JsonObject]:
    graph = arc_content["@graph"]
    assert isinstance(graph, list)
    return [node for node in graph if isinstance(node, dict)]


def _comment_map(arc_content: RoCrateContent) -> dict[str, str]:
    result: dict[str, str] = {}
    for node in _graph_nodes(arc_content):
        node_type = node.get("@type")
        if isinstance(node_type, str):
            types: set[str] = {node_type}
        elif isinstance(node_type, list):
            types = {item for item in node_type if isinstance(item, str)}
        else:
            types = set()
        if "Comment" not in types:
            continue
        name = node.get("name")
        text = node.get("text")
        if isinstance(name, str) and isinstance(text, str):
            result[name] = text
    return result


def test_enrich_injects_missing_comments() -> None:
    """Absent RDI Comments are created from authorized rdi + registry metadata."""
    arc = minimal_rocrate_dict("ARC-1")
    enrich_investigation_rdi_comments(
        arc,
        rdi="edal",
        description="e!DAL repo",
        url="https://edal.example",
    )
    comments = _comment_map(arc)
    assert comments[COMMENT_NAME_RDI] == "edal"
    assert comments[COMMENT_NAME_DESCRIPTION] == "e!DAL repo"
    assert comments[COMMENT_NAME_URL] == "https://edal.example"
    root = next(n for n in _graph_nodes(arc) if n.get("@id") == "./")
    comment_refs = root.get("comment")
    assert isinstance(comment_refs, list)
    assert {"@id": "#Comment_RDI"} in comment_refs


def test_enrich_overwrites_description_and_url() -> None:
    """Registry description/URL replace client-supplied values when RDI matches."""
    arc = minimal_rocrate_dict("ARC-1")
    enrich_investigation_rdi_comments(arc, rdi="edal", description="old", url="https://old.example")
    enrich_investigation_rdi_comments(arc, rdi="edal", description="new", url="https://new.example")
    comments = _comment_map(arc)
    assert comments[COMMENT_NAME_RDI] == "edal"
    assert comments[COMMENT_NAME_DESCRIPTION] == "new"
    assert comments[COMMENT_NAME_URL] == "https://new.example"
    # Stable ids — no duplicate Comment nodes for the same name
    names = [n.get("name") for n in _graph_nodes(arc) if n.get("@type") == "Comment"]
    assert names.count(COMMENT_NAME_DESCRIPTION) == 1


def test_enrich_rejects_conflicting_rdi_comment() -> None:
    """Non-empty Comment[RDI] that disagrees with authorized rdi raises 422-class error."""
    arc = minimal_rocrate_dict("ARC-1")
    enrich_investigation_rdi_comments(arc, rdi="edaphobase", description="", url="")
    with pytest.raises(InvalidJsonSemanticError, match="conflicts with authorized RDI"):
        enrich_investigation_rdi_comments(arc, rdi="edal", description="", url="")


def test_enrich_accepts_matching_rdi_comment() -> None:
    """Matching Comment[RDI] is kept; description/URL still come from registry args."""
    arc = minimal_rocrate_dict("ARC-1")
    enrich_investigation_rdi_comments(arc, rdi="edal", description="from-registry", url="https://r.example")
    comments = _comment_map(arc)
    assert comments[COMMENT_NAME_RDI] == "edal"
    assert comments[COMMENT_NAME_DESCRIPTION] == "from-registry"


def test_enrich_round_trip_through_arctrl() -> None:
    """Enriched JSON exposes the three Comments after arctrl RO-Crate round-trip."""
    arc = minimal_rocrate_dict("ARC-RT")
    enrich_investigation_rdi_comments(
        arc,
        rdi="edal",
        description="desc",
        url="https://edal.example",
    )
    parsed = ARC.from_rocrate_json_string(json.dumps(arc))
    by_name = {c.Name: c.Value for c in parsed.Comments}
    assert by_name[COMMENT_NAME_RDI] == "edal"
    assert by_name[COMMENT_NAME_DESCRIPTION] == "desc"
    assert by_name[COMMENT_NAME_URL] == "https://edal.example"


def _rocrate_with_study_rdi_comments(*, investigation_rdi: str, study_rdi: str, study_url: str) -> RoCrateContent:
    """Build a crate whose Study Comments reuse RDI names (arctrl graph flattening)."""
    inv = ArcInvestigation.create(identifier="inv-rdi-test", title="T", description="d")
    inv.Comments.append(Comment.create(COMMENT_NAME_RDI, investigation_rdi))
    arc_obj = ARC.from_arc_investigation(inv)
    study = ArcStudy.create(identifier="S1", title="Study 1")
    study.Comments.append(Comment.create(COMMENT_NAME_RDI, study_rdi))
    study.Comments.append(Comment.create(COMMENT_NAME_URL, study_url))
    arc_obj.AddRegisteredStudy(study)
    payload = json.loads(arc_obj.ToROCrateJsonString())
    assert isinstance(payload, dict)
    return payload


def test_enrich_ignores_study_rdi_comment_conflict() -> None:
    """Study Comment[RDI] must not 422 when Investigation Comment[RDI] matches."""
    crate = _rocrate_with_study_rdi_comments(
        investigation_rdi="edal",
        study_rdi="other",
        study_url="https://study.example",
    )
    enrich_investigation_rdi_comments(crate, rdi="edal", description="desc", url="https://edal.example")
    parsed = ARC.from_rocrate_json_string(json.dumps(crate))
    inv_comments = {c.Name: c.Value for c in parsed.Comments}
    assert inv_comments[COMMENT_NAME_RDI] == "edal"
    study = next(s for s in parsed.Studies if s.Identifier == "S1")
    study_comments = {c.Name: c.Value for c in study.Comments}
    assert study_comments[COMMENT_NAME_RDI] == "other"
    assert study_comments[COMMENT_NAME_URL] == "https://study.example"


def test_enrich_does_not_duplicate_shared_stable_comment_ids() -> None:
    """Root + Study sharing a stable Comment @id must not produce two graph nodes."""
    crate: RoCrateContent = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [
            {
                "@id": "./",
                "@type": "Dataset",
                "comment": {"@id": "#Comment_RDI"},
            },
            {
                "@id": "#study-s1",
                "@type": "Study",
                "comment": {"@id": "#Comment_RDI"},
            },
            {
                "@id": "#Comment_RDI",
                "@type": "Comment",
                "name": COMMENT_NAME_RDI,
                "text": "edal",
            },
        ],
    }
    enrich_investigation_rdi_comments(crate, rdi="edal", description="desc", url="https://edal.example")
    graph_ids = [node.get("@id") for node in _graph_nodes(crate)]
    assert graph_ids.count("#Comment_RDI") == 1
    comments = [node for node in _graph_nodes(crate) if node.get("@id") == "#Comment_RDI"]
    assert comments == [
        {
            "@id": "#Comment_RDI",
            "@type": "Comment",
            "name": COMMENT_NAME_RDI,
            "text": "edal",
        }
    ]


def test_enrich_keeps_shared_study_rdi_comment_nodes() -> None:
    """Shared investigation/study Comment nodes stay in the graph for the study."""
    crate = _rocrate_with_study_rdi_comments(
        investigation_rdi="edal",
        study_rdi="edal",
        study_url="https://study.example",
    )
    enrich_investigation_rdi_comments(crate, rdi="edal", description="desc", url="https://edal.example")
    parsed = ARC.from_rocrate_json_string(json.dumps(crate))
    assert {c.Name: c.Value for c in parsed.Comments}[COMMENT_NAME_RDI] == "edal"
    study = next(s for s in parsed.Studies if s.Identifier == "S1")
    study_comments = {c.Name: c.Value for c in study.Comments}
    assert study_comments[COMMENT_NAME_RDI] == "edal"
    assert study_comments[COMMENT_NAME_URL] == "https://study.example"


def test_enrich_with_study_rdi_comments_survives_arc_write(tmp_path: Path) -> None:
    """ARCtrl#641 is per holder: Investigation+Study Comment[RDI] must still Write."""
    crate = _rocrate_with_study_rdi_comments(
        investigation_rdi="edal",
        study_rdi="other",
        study_url="https://study.example",
    )
    enrich_investigation_rdi_comments(crate, rdi="edal", description="desc", url="https://edal.example")
    parsed = ARC.from_rocrate_json_string(json.dumps(crate))
    out = tmp_path / "arc"
    out.mkdir()
    parsed.Write(str(out))
    assert (out / "isa.investigation.xlsx").is_file()
    assert (out / "studies" / "S1" / "isa.study.xlsx").is_file()
