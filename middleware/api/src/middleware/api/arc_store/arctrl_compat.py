"""Compatibility shims for arctrl / fable-library Python packaging quirks."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_state: dict[str, bool] = {"patched": False}

_FableInt32: Any | None
try:
    from fable_library.core import Int32 as _FableInt32  # type: ignore[import-untyped, no-redef]
except ImportError:
    _FableInt32 = None


def patch_fable_int32_for_openpyxl() -> None:
    """Teach ``fable.Int32`` ``divmod`` so openpyxl can write XLSX under arctrl 3.2+.

    ``openpyxl.utils.cell.get_column_letter`` calls ``divmod(col_idx, 26)``. Column
    indices from arctrl 3.2 / fable-library 5.13 are ``fable.Int32``, which
    implements ``//`` and ``%`` but not ``__divmod__``, so builtins ``divmod``
    raises ``TypeError``. Adding ``__divmod__`` / ``__rdivmod__`` restores Write
    for study/assay ISA files (see ARCtrl#638). Duplicated in ``middleware/tools/rocrate2arc.py``
    (no api dependency); remove both when fixed (fairagro/m4.2_advanced_middleware_api#339).
    """
    if _state["patched"]:
        return
    if _FableInt32 is None:
        logger.debug("fable_library.core.Int32 unavailable; skipping openpyxl divmod patch")
        _state["patched"] = True
        return

    def divmod_method(self: object, other: object) -> tuple[int, int]:
        result = divmod(int(self), int(other))  # type: ignore[call-overload]
        return int(result[0]), int(result[1])

    def rdivmod_method(self: object, other: object) -> tuple[int, int]:
        result = divmod(int(other), int(self))  # type: ignore[call-overload]
        return int(result[0]), int(result[1])

    changed = False
    if "__divmod__" not in _FableInt32.__dict__:
        _FableInt32.__divmod__ = divmod_method
        changed = True
    if "__rdivmod__" not in _FableInt32.__dict__:
        _FableInt32.__rdivmod__ = rdivmod_method
        changed = True
    _state["patched"] = True
    if changed:
        logger.debug("Patched fable.Int32.__divmod__ for openpyxl column letters")


def reset_fable_int32_patch_for_tests() -> None:
    """Allow unit tests to re-apply the patch after import-order side effects."""
    _state["patched"] = False
