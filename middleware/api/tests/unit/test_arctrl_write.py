"""Smoke tests for arctrl Write without local fable Int32 shims."""

from __future__ import annotations

from pathlib import Path

from arctrl import ARC
from fable_library.core import int32


def test_fable_int32_divmod_works_without_local_shim() -> None:
    """Upstream ARCtrl 3.2.2+ must support builtins.divmod for openpyxl."""
    quotient, remainder = divmod(int32(44), 26)
    assert int(quotient) == 1  # noqa: PLR2004
    assert int(remainder) == 18  # noqa: PLR2004


def test_sample_rocrate_write_succeeds(tmp_path: Path) -> None:
    """Regression: sample.json study/assay XLSX write under current arctrl."""
    sample = Path(__file__).resolve().parents[4] / "ro_crates" / "sample.json"
    arc = ARC.from_rocrate_json_string(sample.read_text(encoding="utf-8"))
    out = tmp_path / "arc"
    out.mkdir()
    arc.Write(str(out))
    assert (out / "studies" / "AthalianaColdStress" / "isa.study.xlsx").is_file()
    assert (out / "assays" / "SugarMeasurement" / "isa.assay.xlsx").is_file()
