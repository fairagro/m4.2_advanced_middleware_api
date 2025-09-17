"""Tool to convert RO-Crate JSON files to ARC format."""

import cProfile
import pstats

from arctrl import ARC


def rocrate_json_to_arc(rocrate_input_path: str, arc_path: str):
    """Convert a RO-Crate JSON file to ARC format and save to a file."""
    with open(rocrate_input_path, encoding="utf-8") as f:
        rocrate_json = f.read()
        arc = ARC.from_rocrate_json_string(rocrate_json)
    arc.Write(arc_path)


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 3:
        print("Usage: python rocrate2arc.py <input.json> <output.arc>")
        sys.exit(1)

    # Profiling
    cProfile.run("rocrate_json_to_arc(sys.argv[1], sys.argv[2])", "profile.stats")

    # Stats laden
    stats = pstats.Stats("profile.stats")
    stats.sort_stats(pstats.SortKey.TIME).print_stats(20)
