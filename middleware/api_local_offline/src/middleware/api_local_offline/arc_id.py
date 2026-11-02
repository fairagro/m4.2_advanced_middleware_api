"""ARC id helper (same contract as middleware.api.utils.calculate_arc_id)."""

from __future__ import annotations

import hashlib


def calculate_arc_id(identifier: str, rdi: str) -> str:
    """SHA256 of ``strip(identifier):strip(rdi)`` (no Unicode NFC; see api #537)."""
    input_str = f"{identifier.strip()}:{rdi.strip()}"
    return hashlib.sha256(input_str.encode("utf-8")).hexdigest()
