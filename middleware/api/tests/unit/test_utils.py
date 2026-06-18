"""Unit tests for middleware.api.utils."""

from middleware.api.utils import calculate_arc_id


def test_calculate_arc_id_strips_whitespace() -> None:
    """Leading and trailing whitespace in identifier and rdi does not change arc_id."""
    base = calculate_arc_id("my-arc", "my-rdi")
    assert calculate_arc_id("  my-arc  ", "my-rdi") == base
    assert calculate_arc_id("my-arc", "  my-rdi  ") == base
    assert calculate_arc_id("  my-arc  ", "  my-rdi  ") == base
