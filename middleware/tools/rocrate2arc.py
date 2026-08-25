"""Tool to convert RO-Crate JSON files to ARC format."""

import cProfile
import pstats

from arctrl import ARC  # type: ignore[import-untyped]


def _patch_fable_int32_for_openpyxl() -> None:
    """Apply openpyxl/fable Int32 divmod shim (tools has no dependency on api)."""
    try:
        from fable_library.core import Int32  # type: ignore[import-untyped]
    except ImportError:
        return

    def divmod_method(self: object, other: object) -> tuple[int, int]:
        result = divmod(int(self), int(other))  # type: ignore[call-overload]
        return int(result[0]), int(result[1])

    def rdivmod_method(self: object, other: object) -> tuple[int, int]:
        result = divmod(int(other), int(self))  # type: ignore[call-overload]
        return int(result[0]), int(result[1])

    Int32.__divmod__ = divmod_method  # type: ignore[method-assign, assignment]
    Int32.__rdivmod__ = rdivmod_method  # type: ignore[method-assign, assignment]


_patch_fable_int32_for_openpyxl()


def rocrate_json_to_arc(rocrate_input_path: str, arc_path: str) -> None:
    """Convert a RO-Crate JSON file to ARC format and save to a file."""
    with open(rocrate_input_path, encoding="utf-8") as f:
        rocrate_json = f.read()
        arc = ARC.from_rocrate_json_string(rocrate_json)
    arc.Write(arc_path)


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 3:  # noqa: PLR2004
        print("Usage: python rocrate2arc.py <input.json> <output.arc>")
        sys.exit(1)

    # Profiling
    cProfile.run("rocrate_json_to_arc(sys.argv[1], sys.argv[2])", "profile.stats")

    # Stats laden
    stats = pstats.Stats("profile.stats")
    stats.sort_stats(pstats.SortKey.TIME).print_stats(20)
