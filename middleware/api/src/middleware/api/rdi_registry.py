"""Deployment RDI registry entries (identifier + optional description/URL)."""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from typing import Annotated, Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

logger = logging.getLogger(__name__)

_RDI_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_.-]+$")

_BARE_STRING_KNOWN_RDIS_REJECTED = (
    "Bare string entries in known_rdis are no longer accepted; use objects with 'id' and "
    "optional 'description'/'url' (e.g. {id: edal, description: …, url: …})."
)


class RdiRegistryEntry(BaseModel):
    """One known RDI with optional portable metadata for Investigation Comments."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    id: Annotated[str, Field(description="RDI identifier (auth allowlist key)")]
    description: Annotated[str, Field(description="Human-readable infrastructure summary")] = ""
    url: Annotated[str, Field(description="Canonical infrastructure URL")] = ""

    @model_validator(mode="before")
    @classmethod
    def reject_string_id(cls, data: Any) -> Any:
        """Reject bare YAML strings; require ``{id: …}`` object form."""
        if isinstance(data, str):
            msg = f"{_BARE_STRING_KNOWN_RDIS_REJECTED} Got {data!r}."
            raise ValueError(msg)
        return data

    @field_validator("id")
    @classmethod
    def validate_id_charset(cls, rdi_id: str) -> str:
        """Reject RDI identifiers outside the deployment charset."""
        if not _RDI_ID_PATTERN.match(rdi_id):
            msg = (
                f"Invalid RDI identifier '{rdi_id}'. Only alphanumeric characters, hyphens, "
                "underscores, and dots are allowed."
            )
            logger.error(msg)
            raise ValueError(msg)
        return rdi_id


def known_rdi_ids(entries: Sequence[RdiRegistryEntry]) -> list[str]:
    """Return RDI identifiers in registry order."""
    return [entry.id for entry in entries]


def lookup_rdi_entry(entries: Sequence[RdiRegistryEntry], rdi: str) -> RdiRegistryEntry:
    """Return the registry entry for ``rdi``, or an empty-metadata entry with that id."""
    for entry in entries:
        if entry.id == rdi:
            return entry
    return RdiRegistryEntry(id=rdi)


def validate_unique_rdi_ids(entries: Sequence[RdiRegistryEntry]) -> list[RdiRegistryEntry]:
    """Ensure registry identifiers are unique; return the same list."""
    seen: set[str] = set()
    for entry in entries:
        if entry.id in seen:
            msg = f"Duplicate RDI identifier in known_rdis: '{entry.id}'"
            logger.error(msg)
            raise ValueError(msg)
        seen.add(entry.id)
    return list(entries)
