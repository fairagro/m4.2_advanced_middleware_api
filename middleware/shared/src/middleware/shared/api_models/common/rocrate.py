"""RO-Crate payload validation for ARC upload requests."""

from functools import cached_property
from typing import Annotated, Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


def _root_dataset_entity(graph: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return the RO-Crate root data entity (``@id``: ``./``) from ``@graph``."""
    for item in graph:
        if isinstance(item, dict) and item.get("@id") == "./":
            return item
    return None


def _normalize_text_field(value: object) -> str | None:
    if isinstance(value, list):
        value = value[0] if value else None
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _extract_identifier(root: dict[str, Any]) -> str:
    """Extract and normalize the required ``identifier`` from the root data entity."""
    identifier = _normalize_text_field(root.get("identifier"))
    if not identifier:
        msg = "RO-Crate root data entity must contain a non-empty identifier"
        raise ValueError(msg)
    return identifier


def _extract_optional_text(root: dict[str, Any], field: str) -> str | None:
    """Extract an optional text field from the root data entity."""
    return _normalize_text_field(root.get(field))


def validate_root_dataset(graph: list[dict[str, Any]]) -> dict[str, Any]:
    """Validate ``@graph`` contains a root data entity with a non-empty ``identifier``."""
    root = _root_dataset_entity(graph)
    if root is None:
        msg = "RO-Crate must contain a root data entity with @id './'"
        raise ValueError(msg)
    _extract_identifier(root)
    return root


class RoCratePayload(BaseModel):
    """RO-Crate metadata document as received on the API wire format."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    context: Annotated[Any, Field(alias="@context")]
    graph: Annotated[list[dict[str, Any]], Field(alias="@graph", min_length=1)]

    @model_validator(mode="after")
    def validate_root_dataset_fields(self) -> Self:
        """Require a root data entity with API-mandated fields; leave other properties untouched."""
        validate_root_dataset(self.graph)
        return self

    @cached_property
    def _root(self) -> dict[str, Any]:
        """Root data entity dict (validated during model construction)."""
        root = _root_dataset_entity(self.graph)
        if root is None:
            msg = "RO-Crate must contain a root data entity with @id './'"
            raise ValueError(msg)
        return root

    @cached_property
    def identifier(self) -> str:
        """Non-empty ``identifier`` from the root data entity (``@graph`` → ``@id`` ``./``)."""
        return _extract_identifier(self._root)

    @cached_property
    def name(self) -> str | None:
        """Optional RO-Crate ``name`` from the root data entity."""
        return _extract_optional_text(self._root, "name")

    @cached_property
    def description(self) -> str | None:
        """Optional RO-Crate ``description`` from the root data entity."""
        return _extract_optional_text(self._root, "description")
