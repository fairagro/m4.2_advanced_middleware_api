"""V3 ARC endpoints.

Standalone ``POST /v3/arcs`` is registered by ``middleware.api_v3``. This module remains
as a stable import path for versioned package layout; it currently exports an empty
router so deferred ARC routes can land here without changing ``fastapi_app`` mounts.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/v3/arcs", tags=["v3", "arcs"])
