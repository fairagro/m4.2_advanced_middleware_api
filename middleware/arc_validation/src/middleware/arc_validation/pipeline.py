"""ARCtrl scaffold write and Docker ``arc-export`` validation pipeline."""

from __future__ import annotations

import os
import subprocess
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from arctrl import ARC

from middleware.arc_validation.cause import extract_cause_excerpt

DEFAULT_ARC_EXPORT_IMAGE = "ghcr.io/nfdi4plants/arc-export:main"
DEFAULT_ARC_EXPORT_FORMATS: tuple[str, ...] = (
    "rocrate-metadata-lfs",
    "isa-json",
    "summary-markdown",
)
IMAGE_ENV_VAR = "FAIRAGRO_ARC_EXPORT_IMAGE"
_WRITE_FAILURE_EXIT_CODE = 1


@dataclass(frozen=True)
class ArcExportResult:
    """Outcome of an ``arc-export`` (or pre-export write) attempt."""

    ok: bool
    exit_code: int
    stdout: str
    stderr: str
    cause_excerpt: str


def resolve_arc_export_image(image: str | None = None) -> str:
    """Resolve image: explicit argument, then ``FAIRAGRO_ARC_EXPORT_IMAGE``, then default."""
    if image is not None and image.strip():
        return image.strip()
    env_image = os.environ.get(IMAGE_ENV_VAR, "").strip()
    if env_image:
        return env_image
    return DEFAULT_ARC_EXPORT_IMAGE


def write_arc_scaffold(rocrate: str, out_dir: str | Path) -> Path:
    """Load RO-Crate JSON-LD with ARCtrl and write an ARC directory tree.

    ``out_dir`` MUST be missing or an empty directory so scaffold output is not mixed
    with stale files.

    Raises:
        FileExistsError: If ``out_dir`` exists and is not empty.
        NotADirectoryError: If ``out_dir`` exists and is not a directory.
        Exception: Propagates ARCtrl / filesystem failures when used directly.
    """
    target = Path(out_dir)
    if target.exists():
        if not target.is_dir():
            raise NotADirectoryError(f"out_dir is not a directory: {target}")
        if any(target.iterdir()):
            raise FileExistsError(f"out_dir is not empty: {target}")
    else:
        target.mkdir(parents=True, exist_ok=True)
    arc = ARC.from_rocrate_json_string(rocrate)
    arc.Write(str(target))
    return target


def _build_docker_argv(
    arc_dir: Path,
    *,
    image: str,
    formats: Sequence[str],
) -> list[str]:
    argv: list[str] = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{arc_dir.resolve()}:/arc",
        "-w",
        "/arc",
        image,
        "arc-export",
    ]
    for fmt in formats:
        argv.extend(["-f", fmt])
    argv.extend(["-p", "."])
    return argv


def run_arc_export(
    arc_dir: str | Path,
    *,
    image: str | None = None,
    formats: Sequence[str] | None = None,
) -> ArcExportResult:
    """Run DataHUB-equivalent ``arc-export`` against a written ARC directory."""
    arc_path = Path(arc_dir)
    if not arc_path.is_dir():
        message = f"arc_dir is not an existing directory: {arc_path}"
        return ArcExportResult(
            ok=False,
            exit_code=_WRITE_FAILURE_EXIT_CODE,
            stdout="",
            stderr=message,
            cause_excerpt=extract_cause_excerpt(fallback=message),
        )
    resolved_image = resolve_arc_export_image(image)
    resolved_formats = tuple(formats) if formats is not None else DEFAULT_ARC_EXPORT_FORMATS
    argv = _build_docker_argv(arc_path, image=resolved_image, formats=resolved_formats)
    completed = subprocess.run(  # noqa: S603 — argv is built locally; no shell
        argv,
        check=False,
        capture_output=True,
        text=True,
    )
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    ok = completed.returncode == 0
    excerpt = "" if ok else extract_cause_excerpt(stdout=stdout, stderr=stderr)
    return ArcExportResult(
        ok=ok,
        exit_code=completed.returncode,
        stdout=stdout,
        stderr=stderr,
        cause_excerpt=excerpt,
    )


def validate_rocrate(
    rocrate: str,
    *,
    image: str | None = None,
    formats: Sequence[str] | None = None,
) -> ArcExportResult:
    """Write a temporary ARC scaffold, run ``arc-export``, and clean up."""
    with tempfile.TemporaryDirectory(prefix="fairagro-arc-validate-") as tmp:
        out_dir = Path(tmp) / "arc"
        try:
            write_arc_scaffold(rocrate, out_dir)
        except Exception as exc:  # noqa: BLE001 — map any write failure into ArcExportResult
            message = str(exc) or exc.__class__.__name__
            return ArcExportResult(
                ok=False,
                exit_code=_WRITE_FAILURE_EXIT_CODE,
                stdout="",
                stderr=message,
                cause_excerpt=extract_cause_excerpt(fallback=message),
            )
        return run_arc_export(out_dir, image=image, formats=formats)
