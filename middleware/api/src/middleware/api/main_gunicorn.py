"""Entry point for running the Middleware API with Gunicorn + Uvicorn workers.

This provides multi-process parallelism for I/O-bound operations.
"""

import os.path
import sys

import middleware.api
from middleware.api.api import middleware_api


def main() -> None:
    """Start Gunicorn with Uvicorn workers for parallel request handling.

    Gunicorn spawns multiple worker processes, each running an async Uvicorn server.
    This allows the API to handle multiple I/O-bound requests in parallel across
    multiple CPU cores.
    """
    # Construct the app path for Gunicorn
    app_path = f"{middleware_api.__module__}:middleware_api.app"

    # Get config path relative to this module
    config_path = os.path.join(os.path.dirname(middleware.api.__file__), "gunicorn_config.py")

    # Build Gunicorn command line
    sys.argv = [
        "gunicorn",
        app_path,
        "--config",
        config_path,
    ] + sys.argv[1:]

    # Import and run Gunicorn
    from gunicorn.app.wsgiapp import run  # type: ignore[import-untyped]

    run()


if __name__ == "__main__":
    main()
