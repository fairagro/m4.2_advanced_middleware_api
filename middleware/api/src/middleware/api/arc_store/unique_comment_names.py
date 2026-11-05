"""Collapse duplicate Comment names per ARC holder before ``ARC.Write``.

ISA-XLSX keys Comments by name on a given holder. ARCtrl rejects duplicates on Write.
Ingest / CouchDB / content_hash intentionally leave duplicates alone; Git sync applies
last-wins here and logs a warning (#562).
"""

from __future__ import annotations

import logging
from typing import Protocol

from arctrl import ARC

logger = logging.getLogger(__name__)

_MIN_COMMENTS_FOR_NAME_COLLISION = 2


class _CommentLike(Protocol):
    Name: str | None
    Value: str | None


def ensure_unique_comment_names(arc: ARC) -> None:
    """Apply last-wins Comment-name uniqueness on every supported holder (mutates ``arc``)."""
    _collapse_holder_comments(
        arc.Comments,
        holder_kind="Investigation",
        holder_id=_arc_identifier(arc),
    )
    for person in arc.Contacts:
        _collapse_holder_comments(
            person.Comments,
            holder_kind="Person",
            holder_id=_person_identity(person),
        )
    for publication in arc.Publications:
        _collapse_holder_comments(
            publication.Comments,
            holder_kind="Publication",
            holder_id=_publication_identity(publication),
        )
    for study in arc.Studies:
        study_id = _optional_str(getattr(study, "Identifier", None)) or ""
        _collapse_holder_comments(
            study.Comments,
            holder_kind="Study",
            holder_id=study_id,
        )
        for person in study.Contacts:
            _collapse_holder_comments(
                person.Comments,
                holder_kind="Person",
                holder_id=_person_identity(person),
            )
        for publication in study.Publications:
            _collapse_holder_comments(
                publication.Comments,
                holder_kind="Publication",
                holder_id=_publication_identity(publication),
            )
    for assay in arc.Assays:
        _collapse_holder_comments(
            assay.Comments,
            holder_kind="Assay",
            holder_id=_optional_str(getattr(assay, "Identifier", None)) or "",
        )


def _collapse_holder_comments(
    comments: list[_CommentLike],
    *,
    holder_kind: str,
    holder_id: str,
) -> None:
    if len(comments) < _MIN_COMMENTS_FOR_NAME_COLLISION:
        return

    result: list[_CommentLike] = []
    index_by_name: dict[str, int] = {}
    collapsed_names: set[str] = set()

    for comment in comments:
        name = comment.Name
        if not isinstance(name, str) or not name.strip():
            result.append(comment)
            continue
        existing = index_by_name.get(name)
        if existing is not None:
            result[existing] = comment
            collapsed_names.add(name)
            continue
        index_by_name[name] = len(result)
        result.append(comment)

    if not collapsed_names:
        return

    comments[:] = result
    for name in sorted(collapsed_names):
        logger.warning(
            "Collapsed duplicate Comment name %r on %s %r (last-wins before ARC.Write)",
            name,
            holder_kind,
            holder_id,
        )


def _arc_identifier(arc: ARC) -> str:
    return _optional_str(getattr(arc, "Identifier", None)) or ""


def _person_identity(person: object) -> str:
    first = _optional_str(getattr(person, "FirstName", None)) or ""
    last = _optional_str(getattr(person, "LastName", None)) or ""
    email = _optional_str(getattr(person, "Email", None)) or ""
    named = f"{first} {last}".strip()
    if named and email:
        return f"{named} <{email}>"
    return named or email or ""


def _publication_identity(publication: object) -> str:
    doi = _optional_str(getattr(publication, "DOI", None)) or ""
    if doi:
        return doi
    return _optional_str(getattr(publication, "Title", None)) or ""


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None
