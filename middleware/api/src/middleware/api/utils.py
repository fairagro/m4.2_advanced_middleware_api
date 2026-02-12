"""Utility functions for the FAIRagro Middleware API."""

import hashlib
from typing import Any


def calculate_arc_id(identifier: str, rdi: str) -> str:
    """Calculate the unique ARC ID from its identifier and RDI.

    Args:
        identifier: The ARC's internal identifier (e.g., from ISA or RO-Crate).
        rdi: The Research Data Infrastructure identifier.

    Returns:
        A SHA256 hash string.
    """
    input_str = f"{identifier}:{rdi}"
    return hashlib.sha256(input_str.encode("utf-8")).hexdigest()


def extract_identifier(arc_content: dict[str, Any]) -> str | None:
    """Extract identifier from RO-Crate content.

    Following the RO-Crate/ARC specification, the identifier is located
    in the Root Data Entity (marked with "@id": "./") within the @graph.
    Also ensures the basic RO-Crate structure (e.g., @context) is present.

    Args:
        arc_content: The ARC/RO-Crate content as a dictionary.

    Returns:
        The extracted identifier or None if not found or invalid structure.
    """
    if "@context" not in arc_content:
        return None

    graph = arc_content.get("@graph")
    if isinstance(graph, list):
        for item in graph:
            if item.get("@id") == "./":
                identifier = item.get("identifier")
                if isinstance(identifier, list) and identifier:
                    return str(identifier[0])
                return str(identifier) if identifier else None

    return None
