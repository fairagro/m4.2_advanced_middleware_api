"""Unit tests for last-wins Comment-name collapse before ARC.Write."""

from __future__ import annotations

from pathlib import Path

import pytest
from arctrl import ARC, ArcAssay, ArcInvestigation, ArcStudy, Comment, Person, Publication

from middleware.api.arc_store.unique_comment_names import ensure_unique_comment_names


def test_collapse_duplicate_investigation_comment_last_wins(caplog: pytest.LogCaptureFixture) -> None:
    """Two same-name Investigation Comments keep the last value and warn."""
    arc = ARC.from_arc_investigation(ArcInvestigation.create(identifier="inv-1", title="T"))
    arc.Comments.append(Comment.create("note", "first"))
    arc.Comments.append(Comment.create("note", "second"))
    arc.Comments.append(Comment.create("other", "keep"))

    with caplog.at_level("WARNING"):
        ensure_unique_comment_names(arc)

    by_name = {c.Name: c.Value for c in arc.Comments}
    assert by_name == {"note": "second", "other": "keep"}
    assert any("note" in r.message and "Investigation" in r.message for r in caplog.records)


def test_same_name_on_investigation_and_study_kept() -> None:
    """Same Comment name on different holders must not collapse across holders."""
    arc = ARC.from_arc_investigation(ArcInvestigation.create(identifier="inv-2", title="T"))
    arc.Comments.append(Comment.create("RDI", "edal"))
    study = ArcStudy.init("S1")
    study.Comments.append(Comment.create("RDI", "other"))
    arc.Studies.append(study)

    ensure_unique_comment_names(arc)

    assert {c.Name: c.Value for c in arc.Comments}["RDI"] == "edal"
    assert {c.Name: c.Value for c in study.Comments}["RDI"] == "other"


def test_person_and_publication_and_assay_holders(caplog: pytest.LogCaptureFixture) -> None:
    """Person, Publication, and Assay duplicate names collapse independently."""
    arc = ARC.from_arc_investigation(ArcInvestigation.create(identifier="inv-3", title="T"))

    person = Person(first_name="Ada", last_name="Lovelace")
    person.Comments.append(Comment.create("role", "a"))
    person.Comments.append(Comment.create("role", "b"))
    arc.Contacts.append(person)

    publication = Publication(doi="10.1/example", title="Paper")
    publication.Comments.append(Comment.create("tag", "x"))
    publication.Comments.append(Comment.create("tag", "y"))
    arc.Publications.append(publication)

    assay = ArcAssay.create("A1")
    assay.Comments.append(Comment.create("param", "1"))
    assay.Comments.append(Comment.create("param", "2"))
    arc.Assays.append(assay)

    with caplog.at_level("WARNING"):
        ensure_unique_comment_names(arc)

    assert {c.Name: c.Value for c in person.Comments} == {"role": "b"}
    assert {c.Name: c.Value for c in publication.Comments} == {"tag": "y"}
    assert {c.Name: c.Value for c in assay.Comments} == {"param": "2"}
    assert len([r for r in caplog.records if "Collapsed duplicate" in r.message]) == 3


def test_write_succeeds_after_collapse(tmp_path: Path) -> None:
    """ARC.Write succeeds after collapsing Investigation duplicate Comment names."""
    arc = ARC.from_arc_investigation(ArcInvestigation.create(identifier="inv-write", title="T"))
    arc.Comments.append(Comment.create("note", "first"))
    arc.Comments.append(Comment.create("note", "second"))
    ensure_unique_comment_names(arc)
    out = tmp_path / "arc"
    out.mkdir()
    arc.Write(str(out))
    assert (out / "isa.investigation.xlsx").is_file()


def test_blank_comment_names_collapse_last_wins(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """Empty/whitespace Comment names collapse so ARC.Write succeeds."""
    arc = ARC.from_arc_investigation(ArcInvestigation.create(identifier="inv-blank", title="T"))
    arc.Comments.append(Comment.create("", "first"))
    arc.Comments.append(Comment.create("  ", "second"))

    with caplog.at_level("WARNING"):
        ensure_unique_comment_names(arc)

    assert len(arc.Comments) == 1
    assert arc.Comments[0].Value == "second"
    assert any("blank" in r.message for r in caplog.records)
    out = tmp_path / "arc"
    out.mkdir()
    arc.Write(str(out))
    assert (out / "isa.investigation.xlsx").is_file()
