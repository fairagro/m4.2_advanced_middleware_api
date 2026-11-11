"""Shared FastAPI /v3 harvest and ARC lifecycle HTTP surface."""

from middleware.api_v3.mount import MVP_LIFECYCLE_ROUTES, mount_lifecycle_routes

__all__ = ["MVP_LIFECYCLE_ROUTES", "mount_lifecycle_routes"]
