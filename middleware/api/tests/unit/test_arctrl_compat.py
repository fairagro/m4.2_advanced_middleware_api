"""Tests for arctrl / fable-library compatibility shims."""

from __future__ import annotations

import importlib.metadata
from pathlib import Path

import pytest
from arctrl import ARC  # type: ignore[import-untyped]
from packaging.version import Version

from middleware.api.arc_store.arctrl_compat import (
    patch_fable_int32_for_openpyxl,
    reset_fable_int32_patch_for_tests,
)

_ARCTRL_VERSION = Version(importlib.metadata.version("arctrl"))


def test_patch_fable_int32_divmod_is_idempotent() -> None:
    """Patch may run repeatedly (package import + tools) without error."""
    patch_fable_int32_for_openpyxl()
    patch_fable_int32_for_openpyxl()


def test_patch_fable_int32_enables_divmod_with_python_int() -> None:
    """Openpyxl column-letter path needs builtins.divmod(Int32, int)."""
    fable_core = pytest.importorskip("fable_library.core")
    int32 = fable_core.int32

    reset_fable_int32_patch_for_tests()
    patch_fable_int32_for_openpyxl()
    quotient, remainder = divmod(int32(44), 26)
    assert int(quotient) == 1  # noqa: PLR2004
    assert int(remainder) == 18  # noqa: PLR2004


@pytest.mark.skipif(
    Version("3.2") > _ARCTRL_VERSION,
    reason="arctrl < 3.2 Write does not hit the Int32/divmod openpyxl path",
)
def test_sample_rocrate_write_succeeds_with_compat_patch(tmp_path: Path) -> None:
    """Regression: sample.json study/assay XLSX write under arctrl 3.2+."""
    reset_fable_int32_patch_for_tests()
    patch_fable_int32_for_openpyxl()

    sample = Path(__file__).resolve().parents[4] / "ro_crates" / "sample.json"
    arc = ARC.from_rocrate_json_string(sample.read_text(encoding="utf-8"))
    out = tmp_path / "arc"
    out.mkdir()
    arc.Write(str(out))
    assert (out / "studies" / "AthalianaColdStress" / "isa.study.xlsx").is_file()
    assert (out / "assays" / "SugarMeasurement" / "isa.assay.xlsx").is_file()
