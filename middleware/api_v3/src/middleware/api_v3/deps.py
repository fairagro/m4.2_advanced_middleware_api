"""FastAPI dependencies for the shared v3 lifecycle routers."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable

from fastapi import Request

from middleware.shared.v3_lifecycle import HarvestArcLifecyclePort

LIFECYCLE_PORT_FACTORY_ATTR = "lifecycle_port_factory"

LifecyclePortFactory = Callable[[Request], HarvestArcLifecyclePort | Awaitable[HarvestArcLifecyclePort]]


async def get_lifecycle_port(request: Request) -> HarvestArcLifecyclePort:
    """Resolve the app-supplied harvest/ARC lifecycle port for this request."""
    factory = getattr(request.app.state, LIFECYCLE_PORT_FACTORY_ATTR, None)
    if factory is None:
        msg = (
            f"FastAPI app.state.{LIFECYCLE_PORT_FACTORY_ATTR} is not set; "
            "call mount_lifecycle_routes(...) when building the app"
        )
        raise RuntimeError(msg)
    port = factory(request)
    if inspect.isawaitable(port):
        port = await port
    return port  # type: ignore[no-any-return]
