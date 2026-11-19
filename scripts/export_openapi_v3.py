#!/usr/bin/env python3
"""Export production FastAPI OpenAPI filtered to /v3 paths (#651).

Builds the API with an in-memory dummy config (no secrets / no lifespan I/O).
Optional ``--repo-root`` prepends that tree's ``middleware/*/src`` so a detached
git worktree at ``main`` can be exported with this HEAD script.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import tempfile
from collections.abc import Mapping, MutableMapping, Sequence
from pathlib import Path
from typing import Any

_DUMMY_CONFIG: dict[str, Any] = {
    "log_level": "WARNING",
    "known_rdis": [],
    "otel": {"endpoint": None},
    "arc_store": {
        "git_repo": {
            "url": "http://localhost",
            "group": "openapi-export",
            "branch": "main",
        },
    },
    "celery": {"broker_url": "amqp://guest:guest@localhost:5672//"},
    "couchdb": {"url": "http://localhost:5984"},
}

_SRC_PACKAGES = (
    "middleware/api/src",
    "middleware/api_v3/src",
    "middleware/shared/src",
    "middleware/api_client/src",
)


def middleware_src_paths(repo_root: Path) -> list[Path]:
    """Return existing middleware package src dirs under ``repo_root``."""
    return [repo_root / rel for rel in _SRC_PACKAGES if (repo_root / rel).is_dir()]


def prepend_middleware_src(repo_root: Path) -> None:
    """Prefer ``repo_root`` package sources over the editable install at HEAD."""
    for path in reversed(middleware_src_paths(repo_root)):
        text = str(path)
        if text in sys.path:
            sys.path.remove(text)
        sys.path.insert(0, text)


def filter_v3_paths(spec: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copy of ``spec`` whose ``paths`` contain only ``/v3`` entries.

    ``components`` are retained in full so ``$ref`` targets remain resolvable for
    oasdiff even when unused by the filtered paths.
    """
    paths = spec.get("paths")
    if not isinstance(paths, Mapping):
        msg = "OpenAPI document missing mapping 'paths'"
        raise SystemExit(msg)
    filtered_paths = {key: value for key, value in paths.items() if str(key).startswith("/v3")}
    out: dict[str, Any] = dict(spec)
    out["paths"] = filtered_paths
    return out


def _write_dummy_config(path: Path) -> None:
    import yaml

    path.write_text(yaml.safe_dump(_DUMMY_CONFIG), encoding="utf-8")


def build_openapi(*, repo_root: Path) -> dict[str, Any]:
    """Construct the production API and return its OpenAPI document."""
    prepend_middleware_src(repo_root)
    with tempfile.TemporaryDirectory(prefix="openapi-v3-config-") as tmp:
        config_path = Path(tmp) / "config.yaml"
        _write_dummy_config(config_path)
        os.environ["MIDDLEWARE_API_CONFIG"] = str(config_path)
        # Import only after env + sys.path are ready (fastapi_app loads config at import).
        from middleware.api.api.fastapi_app import Api  # pylint: disable=import-outside-toplevel
        from middleware.api.config import Config  # pylint: disable=import-outside-toplevel

        logging.getLogger("middleware_api").setLevel(logging.WARNING)
        logging.getLogger("middleware.api.api.tracing").setLevel(logging.WARNING)
        logging.getLogger("middleware.shared.tracing").setLevel(logging.WARNING)
        config = Config.from_yaml_file(config_path)
        api = Api(config)
        return api.app.openapi()


def export_filtered_openapi(*, repo_root: Path) -> dict[str, Any]:
    """Build OpenAPI for ``repo_root`` and keep only ``/v3`` paths."""
    return filter_v3_paths(build_openapi(repo_root=repo_root))


def main(argv: Sequence[str] | None = None) -> int:
    """CLI: write filtered /v3 OpenAPI JSON to ``--output``."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repository root whose middleware/*/src to import (default: cwd)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        required=True,
        help="Write filtered OpenAPI JSON here",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    repo_root = (args.repo_root or Path.cwd()).resolve()
    if not (repo_root / "middleware").is_dir():
        print(f"error: no middleware/ under {repo_root}", file=sys.stderr)
        return 2
    try:
        spec = export_filtered_openapi(repo_root=repo_root)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 — surface export failures as gate errors
        print(f"error: failed to generate OpenAPI from {repo_root}: {exc}", file=sys.stderr)
        return 2
    paths = spec.get("paths")
    if not isinstance(paths, MutableMapping) or not paths:
        print(f"error: no /v3 paths in OpenAPI from {repo_root}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(spec, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {len(paths)} /v3 path(s) to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
