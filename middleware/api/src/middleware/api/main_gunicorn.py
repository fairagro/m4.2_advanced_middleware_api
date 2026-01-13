"""Entry point for running the Middleware API with Gunicorn + Uvicorn workers.

This provides multi-process parallelism for I/O-bound operations.
"""

import os.path
import sys

from gunicorn.app.wsgiapp import run  # type: ignore[import-untyped]

from middleware.api.api import middleware_api


def main() -> None:
    """Start Gunicorn with Uvicorn workers for parallel request handling.

    Gunicorn spawns multiple worker processes, each running an async Uvicorn server.
    This allows the API to handle multiple I/O-bound requests in parallel across
    multiple CPU cores.
    """
    # Construct the app path for Gunicorn
    app_path = f"{middleware_api.__module__}:app"

    # Get config path relative to this module
    if getattr(sys, "frozen", False):
        # In PyInstaller (onedir), we place the config file in the root of the dist folder.
        # However, due to how pyinstaller extracts things, it might end up in _internal depending on how we add it.
        # But we added it to "." which is the directory containing the executable.
        config_path = os.path.join(os.path.dirname(sys.executable), "gunicorn_config.py")

        # Fallback: check if it is in _internal which is sys._MEIPASS
        if not os.path.exists(config_path):
            # pylint: disable=no-member,protected-access
            config_path = os.path.join(sys._MEIPASS, "gunicorn_config.py")  # type: ignore
    else:
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gunicorn_config.py")

    # Build Gunicorn command line
    sys.argv = [
        "gunicorn",
        app_path,
        "--config",
        config_path,
    ] + sys.argv[1:]

    run()


if __name__ == "__main__":
    main()
