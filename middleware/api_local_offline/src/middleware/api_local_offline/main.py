"""CLI entry for the local offline Middleware stand-in."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import uvicorn

from middleware.api_local_offline.app import create_local_offline_app
from middleware.api_local_offline.config import LocalOfflineConfig


def main(argv: list[str] | None = None) -> None:
    """Run the local offline stand-in with uvicorn."""
    parser = argparse.ArgumentParser(description="Middleware API local offline stand-in (ARC on disk)")
    parser.add_argument(
        "--config",
        type=Path,
        required=True,
        help="YAML config for LocalOfflineConfig (output_root; forbids production API keys)",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Bind port (default 8000)")
    args = parser.parse_args(argv)

    config = LocalOfflineConfig.from_yaml_file(args.config)
    app = create_local_offline_app(config)
    uvicorn.run(app, host=args.host, port=args.port, log_level=config.log_level.lower())


if __name__ == "__main__":
    main(sys.argv[1:])
