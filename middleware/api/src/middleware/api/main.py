"""Entry point for running the Middleware API with Uvicorn or Celery."""

import asyncio
import multiprocessing
import sys

from middleware.api.worker_health import check_worker_health


def main() -> None:
    """Call uvicorn.main() or celery.main() to pass control.

    If the first argument is 'celery', we pass control to celery.
    Otherwise we default to uvicorn with the hardcoded app path.
    """
    # Required for PyInstaller binaries using multiprocessing (workers)
    multiprocessing.freeze_support()

    # Handle --version flag
    if len(sys.argv) > 1 and sys.argv[1] in {"--version", "-v"}:
        try:
            from importlib.metadata import version  # pylint: disable=import-outside-toplevel

            print(f"middleware-api version {version('api')}")
        except Exception:  # noqa: BLE001
            print("middleware-api version unknown")
        sys.exit(0)

    # Late imports to avoid side effects (like config loading) when just checking version or help
    import uvicorn  # pylint: disable=import-outside-toplevel
    from celery.__main__ import main as celery_main  # pylint: disable=import-outside-toplevel

    if len(sys.argv) > 1 and sys.argv[1] == "worker-health":
        sys.exit(0 if asyncio.run(check_worker_health()) else 1)

    if len(sys.argv) > 1 and sys.argv[1] == "celery":
        # Remove the executable name and the 'celery' command, so sys.argv[0] becomes 'celery'
        # effectively mimicking 'python -m celery ...'

        sys.argv = sys.argv[1:]  # ['celery', '-A', ...]
        celery_main()
        sys.exit(0)

    from middleware.api.api.fastapi_app import middleware_api  # pylint: disable=import-outside-toplevel

    # Construct the app path string
    app_path = f"{middleware_api.__module__}:middleware_api.app"

    # Filter out non-uvicorn flags that might leak in from multiprocessing or wrappers
    non_uvicorn_args_to_filter = {
        "--multiprocessing-fork",  # Internal multiprocessing flag from PyInstaller workers
        "-B",  # Python interpreter flag (no .pyc) that might be passed by wrappers
        "-u",  # Python interpreter flag (unbuffered I/O) that might be passed by wrappers
    }
    filtered_args = [arg for arg in sys.argv[1:] if arg not in non_uvicorn_args_to_filter]

    # Rebuild sys.argv for uvicorn.main()
    sys.argv = ["uvicorn", app_path] + filtered_args

    uvicorn.main()  # pylint: disable=no-value-for-parameter


if __name__ == "__main__":
    main()
