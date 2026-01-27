"""ARC object building logic for the SQL-to-ARC conversion process."""

import json
import logging
from collections import defaultdict
from typing import Any, cast

from arctrl import (  # type: ignore[import-untyped]
    ARC,
    ArcTable,
    CompositeCell,
    CompositeHeader,
    IOType,
    OntologyAnnotation,
)

from middleware.sql_to_arc.mapper import (
    map_assay,
    map_contact,
    map_investigation,
    map_publication,
    map_study,
)
from middleware.sql_to_arc.models import ArcBuildData

logger = logging.getLogger(__name__)


def _add_studies_to_arc(arc: ARC, study_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Add studies to ARC and return study map."""
    study_map = {}
    for s_row in study_rows:
        study = map_study(s_row)
        arc.AddRegisteredStudy(study)
        study_map[str(s_row["identifier"])] = study
    return study_map


def _add_assays_to_arc(arc: ARC, assay_rows: list[dict[str, Any]], study_map: dict[str, Any]) -> dict[str, Any]:
    """Add assays to ARC, link to studies, and return assay map."""
    assay_map = {}
    for a_row in assay_rows:
        assay = map_assay(a_row)
        arc.AddAssay(assay)
        assay_map[str(a_row["identifier"])] = assay

        # Link Assay to Studies
        study_ref_json = a_row.get("study_ref")
        if not study_ref_json:
            continue

        try:
            study_refs = json.loads(study_ref_json)
            if isinstance(study_refs, list):
                for s_ref in study_refs:
                    if s_ref in study_map:
                        study_map[s_ref].RegisterAssay(assay.Identifier)
        except json.JSONDecodeError:
            pass

    return assay_map


def _add_contacts_to_arc(
    arc: ARC,
    inv_id: str,
    contacts: list[dict[str, Any]],
    study_map: dict[str, Any],
    assay_map: dict[str, Any],
) -> None:
    """Add contacts to investigation, studies, and assays."""
    # Investigation contacts
    inv_contacts = [
        c for c in contacts if c.get("investigation_ref") == inv_id and c.get("target_type") == "investigation"
    ]
    for c_row in inv_contacts:
        arc.Contacts.append(map_contact(c_row))

    # Study contacts
    for s_id, study in study_map.items():
        stu_contacts = [
            c
            for c in contacts
            if c.get("investigation_ref") == inv_id and c.get("target_type") == "study" and c.get("target_ref") == s_id
        ]
        for c_row in stu_contacts:
            study.Contacts.append(map_contact(c_row))

    # Assay contacts
    for a_id, assay in assay_map.items():
        ass_contacts = [
            c
            for c in contacts
            if c.get("investigation_ref") == inv_id and c.get("target_type") == "assay" and c.get("target_ref") == a_id
        ]
        for c_row in ass_contacts:
            assay.Performers.append(map_contact(c_row))


def _add_publications_to_arc(
    arc: ARC, inv_id: str, publications: list[dict[str, Any]], study_map: dict[str, Any]
) -> None:
    """Add publications to investigation and studies."""
    # Investigation publications
    inv_pubs = [
        p for p in publications if p.get("investigation_ref") == inv_id and p.get("target_type") == "investigation"
    ]
    for p_row in inv_pubs:
        arc.Publications.append(map_publication(p_row))

    # Study publications
    for s_id, study in study_map.items():
        stu_pubs = [
            p
            for p in publications
            if p.get("investigation_ref") == inv_id and p.get("target_type") == "study" and p.get("target_ref") == s_id
        ]
        for p_row in stu_pubs:
            study.Publications.append(map_publication(p_row))


def _get_column_key(r: dict[str, Any]) -> tuple:
    """Extract a unique key for a column definition."""
    return (
        r.get("column_type"),
        r.get("column_io_type"),
        r.get("column_value"),
        r.get("column_annotation_term"),
        r.get("column_annotation_uri"),
        r.get("column_annotation_version"),
        r.get("column_name"),  # Fallback for simple tests
    )


def _build_header(key: tuple) -> CompositeHeader | None:
    """Build a CompositeHeader from a column key tuple."""
    c_type, c_io, c_val, c_ann_term, c_ann_uri, c_ann_ver, c_name = key
    header: CompositeHeader | None = None
    try:
        oa = OntologyAnnotation(c_ann_term or "", c_ann_uri or "", c_ann_ver or "")
        if c_type == "input":
            header = CompositeHeader.input(IOType.of_string(c_io or "source_name"))
        elif c_type == "output":
            header = CompositeHeader.output(IOType.of_string(c_io or "sample_name"))
        elif c_type == "characteristic":
            header = CompositeHeader.characteristic(oa)
        elif c_type == "factor":
            header = CompositeHeader.factor(oa)
        elif c_type == "parameter":
            header = CompositeHeader.parameter(oa)
        elif c_type == "component":
            header = CompositeHeader.component(oa)
        elif c_type == "comment":
            header = CompositeHeader.comment(c_val or "")
        elif c_type == "performer":
            header = CompositeHeader.performer()
        elif c_type == "date":
            header = CompositeHeader.date()
        elif c_name:
            # Fallback
            header = CompositeHeader.OfHeaderString(c_name)
    except (ValueError, TypeError, AttributeError) as e:
        logger.warning("Failed to create header for type %s: %s", c_type, e)
    return header


def _build_column_cells(
    rows_map: dict[int, dict[str, Any]], max_row_idx: int, header: CompositeHeader
) -> list[CompositeCell]:
    """Build a list of CompositeCell objects for a column."""
    col_cells = []
    for idx in range(max_row_idx + 1):
        cell_row = rows_map.get(idx)
        if not cell_row:
            col_cells.append(CompositeCell.free_text(""))
            continue

        cv = cell_row.get("cell_value")
        cat = cell_row.get("cell_annotation_term")
        cau = cell_row.get("cell_annotation_uri")
        cav = cell_row.get("cell_annotation_version")
        v = cell_row.get("value")  # Fallback for old/simple tests

        # Unitized cell?
        if cv is not None and cat is not None:
            col_cells.append(CompositeCell.unitized(str(cv), OntologyAnnotation(cat, cau or "", cav or "")))
        elif cat is not None:
            col_cells.append(CompositeCell.term(OntologyAnnotation(cat, cau or "", cav or "")))
        elif cv is not None:
            if header.IsTermColumn:
                col_cells.append(CompositeCell.term(OntologyAnnotation(str(cv), "", "")))
            else:
                col_cells.append(CompositeCell.free_text(str(cv)))
        elif v is not None:
            if header.IsTermColumn:
                col_cells.append(CompositeCell.term(OntologyAnnotation(str(v), "", "")))
            else:
                col_cells.append(CompositeCell.free_text(str(v)))
        else:
            col_cells.append(CompositeCell.free_text(""))
    return col_cells


def _build_arc_table(t_name: str, rows: list[dict[str, Any]]) -> ArcTable | None:
    """Build an ArcTable from flat database rows."""
    if not rows:
        return None

    table = ArcTable.init(t_name)

    # Determine max row index
    max_row_idx = max((cast(int, r.get("row_index", 0)) for r in rows), default=-1)
    if max_row_idx < 0:
        return None

    col_keys: list[tuple] = []
    seen_keys = set()
    col_to_rows: dict[tuple, dict[int, dict[str, Any]]] = defaultdict(dict)

    for r in rows:
        key = _get_column_key(r)
        if key not in seen_keys:
            col_keys.append(key)
            seen_keys.add(key)
        col_to_rows[key][cast(int, r.get("row_index", 0))] = r

    for key in col_keys:
        header = _build_header(key)
        if not header:
            continue

        # Build Cells for this column
        col_cells = _build_column_cells(col_to_rows[key], max_row_idx, header)
        table.AddColumn(header, col_cells)

    return table


def _process_annotation_tables(
    inv_id: str, annotations: list[dict[str, Any]], study_map: dict[str, Any], assay_map: dict[str, Any]
) -> None:
    """Process and add annotation tables."""
    tables_groups = defaultdict(list)
    for ann in annotations:
        if ann.get("investigation_ref") == inv_id:
            key = (ann.get("target_type"), ann.get("target_ref"), ann.get("table_name"))
            tables_groups[key].append(ann)

    for (t_type, t_ref, t_name), rows in tables_groups.items():
        if not t_name:
            continue

        target = None
        if t_type == "study" and isinstance(t_ref, str):
            target = study_map.get(t_ref)
        elif t_type == "assay" and isinstance(t_ref, str):
            target = assay_map.get(t_ref)

        if target:
            table = _build_arc_table(t_name, rows)
            if table:
                target.AddTable(table)


def build_single_arc_task(data: ArcBuildData) -> ARC:
    """Build a single ARC object from data.

    This function is designed to run in a separate process.
    """
    inv_id = str(data.investigation_row["identifier"])

    # Map Investigation and create ARC
    arc_inv = map_investigation(data.investigation_row)
    arc = ARC.from_arc_investigation(arc_inv)

    # Identify relevant studies and assays
    relevant_studies = [s for s in data.studies if s.get("investigation_ref") == inv_id]
    relevant_assays = [a for a in data.assays if a.get("investigation_ref") == inv_id]

    # Add studies and assays
    study_map = _add_studies_to_arc(arc, relevant_studies)
    assay_map = _add_assays_to_arc(arc, relevant_assays, study_map)

    # Add contacts and publications
    _add_contacts_to_arc(arc, inv_id, data.contacts, study_map, assay_map)
    _add_publications_to_arc(arc, inv_id, data.publications, study_map)

    # Process annotation tables
    _process_annotation_tables(inv_id, data.annotations, study_map, assay_map)

    return arc
