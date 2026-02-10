"""Entry point for running the Middleware API with Uvicorn or Celery."""

import multiprocessing
import sys

# Workaround for Pydantic v2 + PyInstaller + Python 3.12 crash
# See: https://github.com/pydantic/pydantic/issues/11054
# This MUST be applied before any other imports that might trigger pydantic
if getattr(sys, "frozen", False):
    import importlib.metadata
    import os

    # 1. Clean sys.path from None values which cause os.stat crashes in importlib.metadata
    sys.path = [p for p in sys.path if p is not None]

    # 2. Disable plugins via environment variable as first line of defense
    os.environ["PYDANTIC_DISABLE_PLUGINS"] = "1"

    # 3. Aggressively patch importlib.metadata to handle None paths if they leak in
    try:
        # Patch FastPath.mtime which is a common crash point
        from importlib.metadata import FastPath  # type: ignore

        orig_mtime = FastPath.mtime

        def safe_mtime(self: FastPath) -> float:  # type: ignore
            """Get the modification time of the root path, or return 0.0 if the path is invalid.

            Returns
            -------
            float
                The modification time of the root path, or 0.0 if the root is None or an error occurs.
            """
            if self.root is None:
                return 0.0
            try:
                return os.stat(self.root).st_mtime
            except (OSError, TypeError):
                return 0.0

        FastPath.mtime = safe_mtime  # type: ignore
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"Warning: Failed to apply Pydantic workaround for FastPath.mtime: {e}", file=sys.stderr)

    # 4. Patch distributions() and Distribution.discover() as backup
    orig_distributions = importlib.metadata.distributions

    def patched_distributions(**kwargs):  # type: ignore
        """Filter distributions to avoid None path crashes."""
        try:
            for dist in orig_distributions(**kwargs):
                try:
                    if getattr(dist, "path", None) is not None:
                        yield dist
                except (AttributeError, TypeError, ValueError, OSError):
                    continue
        except Exception:  # pylint: disable=broad-exception-caught
            return

    importlib.metadata.distributions = patched_distributions  # type: ignore

    try:
        from importlib.metadata import Distribution

        orig_discover = Distribution.discover

        def patched_discover(**kwargs):  # type: ignore
            """Discover distributions while filtering out those with None paths.

            Parameters
            ----------
            **kwargs : dict
                Additional keyword arguments to pass to the original discover method.

            Yields
            ------
            Distribution
                Valid distributions with non-None paths.
            """
            try:
                for dist in orig_discover(**kwargs):
                    try:
                        if getattr(dist, "path", None) is not None:
                            yield dist
                    except (AttributeError, TypeError, ValueError, OSError):
                        continue
            except (Exception, ImportError):  # pylint: disable=broad-exception-caught
                return

        Distribution.discover = patched_discover  # type: ignore
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"Warning: Failed to apply Pydantic workaround for Distribution.discover: {e}", file=sys.stderr)


def main() -> None:
    """Call uvicorn.main() or celery.main() to pass control.

    If the first argument is 'celery', we pass control to celery.
    Otherwise we default to uvicorn with the hardcoded app path.
    """
    # Required for PyInstaller binaries using multiprocessing (workers)
    multiprocessing.freeze_support()

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
