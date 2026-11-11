"""Shared v3 lifecycle APIRouters."""

from middleware.api_v3.routers.arcs import router as arcs_router
from middleware.api_v3.routers.harvests import router as harvests_router
from middleware.api_v3.routers.liveness import router as liveness_router

__all__ = ["arcs_router", "harvests_router", "liveness_router"]
