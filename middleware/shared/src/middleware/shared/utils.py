"""Shared utility functions for the FAIRagro Middleware."""

import hashlib


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
