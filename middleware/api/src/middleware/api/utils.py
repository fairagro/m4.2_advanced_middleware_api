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


def extract_identifier(arc_content: dict[str, Any]) -> str:
    """Extract identifier from RO-Crate content.

    Args:
        arc_content: The ARC/RO-Crate content as a dictionary.

    Returns:
        The extracted identifier or "unknown" if not found.
    """
    identifier = "unknown"
    if "@graph" in arc_content:
        for item in arc_content["@graph"]:
            if item.get("@id") == "./":
                identifier = item.get("identifier", "unknown")
                if isinstance(identifier, list):
                    identifier = identifier[0] if identifier else "unknown"
                break

    if identifier == "unknown":
        identifier = arc_content.get("identifier", "unknown")

    return identifier
