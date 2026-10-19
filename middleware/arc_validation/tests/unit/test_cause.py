"""Tests for cause excerpt extraction."""

from middleware.arc_validation.cause import UNKNOWN_CAUSE, extract_cause_excerpt


def test_extract_internal_error_followers() -> None:
    stderr = "Internal Error:\nValue cannot be null. (Parameter 'array')\n"
    assert extract_cause_excerpt(stderr=stderr) == "Value cannot be null. (Parameter 'array')"


def test_extract_error_hint_line() -> None:
    stderr = "info: starting\nFATAL: export failed for assay\n"
    assert "FATAL" in extract_cause_excerpt(stderr=stderr)


def test_extract_empty_returns_unknown() -> None:
    assert extract_cause_excerpt() == UNKNOWN_CAUSE
