"""Entry point for running the Middleware API with Uvicorn or Celery."""

import sys

import uvicorn
from celery.__main__ import main as celery_main

from middleware.api.api import middleware_api


def main() -> None:
    """Call uvicorn.main() or celery.main() to pass control.

    If the first argument is 'celery', we pass control to celery.
    Otherwise we default to uvicorn with the hardcoded app path.
    """
    if len(sys.argv) > 1 and sys.argv[1] == "celery":
        # Remove the executable name and the 'celery' command, so sys.argv[0] becomes 'celery'
        # effectively mimicking 'python -m celery ...'

        sys.argv = sys.argv[1:]  # ['celery', '-A', ...]
        celery_main()
        sys.exit(0)

    # Construct the app path string
    app_path = f"{middleware_api.__module__}:middleware_api.app"

    # Rebuild sys.argv for uvicorn.main()
    sys.argv = ["uvicorn", app_path] + sys.argv[1:]

    uvicorn.main()  # pylint: disable=no-value-for-parameter


if __name__ == "__main__":
    main()
