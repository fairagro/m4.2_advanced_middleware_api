"""Entry point for running the Middleware API with Uvicorn."""

import sys
import uvicorn
from middleware_api.api import middleware_api

def main():
    """Call uvicorn.main() to pass control to uvicorn.

    We wan't uvicorn to evaluate all command line parameters, so we do not
    need to evaluate them ourselves. On the other hand we would like to
    hardcode the app_path, so it does not need to be specified on the
    command line. We achieve this by manipulating the command line args
    before handing over to uvicorn.
    """
    # Construct the app path string
    app_path = f"{middleware_api.__module__}:middleware_api.app"

    # Rebuild sys.argv for uvicorn.main()
    sys.argv = ["uvicorn", app_path] + sys.argv[1:]

    uvicorn.main()

if __name__ == "__main__":
    main()
