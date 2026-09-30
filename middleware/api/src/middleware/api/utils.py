"""Utility functions for the FAIRagro Middleware API."""

import hashlib


def calculate_arc_id(identifier: str, rdi: str) -> str:
    """Calculate the unique ARC ID from its identifier and RDI.

    Normalization is whitespace ``.strip()`` only on both inputs (no Unicode NFC;
    canonicalize-before-hash is tracked in issue #537).

    Args:
        identifier: The ARC's internal identifier (e.g., from ISA or RO-Crate).
        rdi: The Research Data Infrastructure identifier.

    Returns:
        A SHA256 hash string.
    """
    input_str = f"{identifier.strip()}:{rdi.strip()}"
    return hashlib.sha256(input_str.encode("utf-8")).hexdigest()
