"""CLI entry point ``fairagro-arc-validate``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from middleware.arc_validation.pipeline import validate_rocrate


def build_parser() -> argparse.ArgumentParser:
    """Build the ``fairagro-arc-validate`` argument parser."""
    parser = argparse.ArgumentParser(
        prog="fairagro-arc-validate",
        description=(
            "Validate a RO-Crate JSON file with ARCtrl write + Docker arc-export (DataHUB-equivalent defaults)."
        ),
    )
    parser.add_argument(
        "rocrate_path",
        type=Path,
        help="Path to a RO-Crate JSON-LD file",
    )
    parser.add_argument(
        "--image",
        default=None,
        help=("Override arc-export image (default: FAIRAGRO_ARC_EXPORT_IMAGE or ghcr.io/nfdi4plants/arc-export:main)"),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Validate a RO-Crate path; return process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    path: Path = args.rocrate_path
    if not path.is_file():
        print(f"RO-Crate file not found: {path}", file=sys.stderr)
        return 2
    rocrate = path.read_text(encoding="utf-8")
    result = validate_rocrate(rocrate, image=args.image)
    if result.ok:
        return 0
    excerpt = result.cause_excerpt or result.stderr or "arc-export failed"
    print(excerpt, file=sys.stderr)
    return result.exit_code if result.exit_code != 0 else 1


if __name__ == "__main__":
    sys.exit(main())
