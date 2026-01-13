"""Tool to convert ARC files to RO-Crate JSON format."""

import time

from arctrl import ARC  # type: ignore[import-untyped]


def arc_to_rocrate_json(arc_path: str, rocrate_output_path: str) -> None:
    """Convert an ARC file to RO-Crate JSON format and save to a file."""
    # Lade ARC aus Datei
    start = time.perf_counter()
    arc = ARC.load(arc_path)
    end = time.perf_counter()
    print(f"Loading ARC took {end - start:.2f} seconds")

    # Exportiere als RO-Crate JSON-Objekt
    start = time.perf_counter()
    rocrate = arc.ToROCrateJsonString()
    end = time.perf_counter()
    print(f"Converting ARC to RO-Crate JSON took {end - start:.2f} seconds")

    # Schreibe die JSON-Repräsentation in eine Datei
    with open(rocrate_output_path, "w", encoding="utf-8") as f:
        f.write(rocrate)


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 3:  # noqa: PLR2004
        print("Usage: python arc2rocrate.py <input.arc> <output.json>")
        sys.exit(1)
    arc_to_rocrate_json(sys.argv[1], sys.argv[2])
