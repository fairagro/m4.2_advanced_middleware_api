"""Entry point for running the Middleware API with Uvicorn or Celery."""

import sys


def main() -> None:
    """Call uvicorn.main() or celery.main() to pass control.

    If the first argument is 'celery', we pass control to celery.
    Otherwise we default to uvicorn with the hardcoded app path.
    """
    # Handle --version flag
    if len(sys.argv) > 1 and sys.argv[1] in ("--version", "-v"):
        try:
            from importlib.metadata import PackageNotFoundError, version  # pylint: disable=import-outside-toplevel

            print(f"middleware-api version {version('api')}")
        except (PackageNotFoundError, Exception):  # pylint: disable=broad-exception-caught
            print("middleware-api version unknown")
        sys.exit(0)

    # Late imports to avoid side effects (like config loading) when just checking version or help
    import uvicorn  # pylint: disable=import-outside-toplevel
    from celery.__main__ import main as celery_main  # pylint: disable=import-outside-toplevel

    if len(sys.argv) > 1 and sys.argv[1] == "worker-health":
        from middleware.api.worker_health import check_worker_health  # pylint: disable=import-outside-toplevel

        sys.exit(0 if check_worker_health() else 1)

    if len(sys.argv) > 1 and sys.argv[1] == "setup-couchdb":
        import asyncio  # pylint: disable=import-outside-toplevel

        from middleware.api.cli import setup_couchdb  # pylint: disable=import-outside-toplevel

        asyncio.run(setup_couchdb())
        sys.exit(0)

    if len(sys.argv) > 1 and sys.argv[1] == "celery":
        # Remove the executable name and the 'celery' command, so sys.argv[0] becomes 'celery'
        # effectively mimicking 'python -m celery ...'

        sys.argv = sys.argv[1:]  # ['celery', '-A', ...]
        celery_main()
        sys.exit(0)

    from middleware.api.api import middleware_api  # pylint: disable=import-outside-toplevel

    # Construct the app path string
    app_path = f"{middleware_api.__module__}:middleware_api.app"

    # Rebuild sys.argv for uvicorn.main()
    sys.argv = ["uvicorn", app_path] + sys.argv[1:]

    uvicorn.main()  # pylint: disable=no-value-for-parameter


if __name__ == "__main__":
    main()
