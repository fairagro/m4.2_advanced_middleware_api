"""Version 1 of the API — deprecated system endpoints only.

.. deprecated::
    Version 1 of the API is deprecated and will be removed in a future release.
    Migrate system clients to ``/v3/whoami``, ``/v3/liveness``, ``/v3/readiness``,
    and ``/v3/health``.

``POST /v1/arcs`` and ``GET /v1/tasks`` have been removed. Remaining routes are
``/v1/whoami``, ``/v1/liveness``, and ``/v1/health`` (kept for compatibility).
"""
