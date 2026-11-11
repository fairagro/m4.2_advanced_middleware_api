"""Mount helpers for the shared v3 lifecycle route surface."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any, cast

from fastapi import FastAPI

from middleware.api_v3.deps import LIFECYCLE_PORT_FACTORY_ATTR, LifecyclePortFactory
from middleware.api_v3.routers import arcs_router, harvests_router, liveness_router

# Path + methods that both production and offline must expose for the MVP surface.
MVP_LIFECYCLE_ROUTES: frozenset[tuple[str, frozenset[str]]] = frozenset({
    ("/v3/harvests", frozenset({"POST"})),
    ("/v3/harvests/{harvest_id}", frozenset({"GET", "PATCH"})),
    ("/v3/harvests/{harvest_id}/complete", frozenset({"POST"})),
    ("/v3/harvests/{harvest_id}/arcs", frozenset({"POST"})),
    ("/v3/arcs", frozenset({"POST"})),
    ("/v3/liveness", frozenset({"GET"})),
})


def mount_lifecycle_routes(
    app: FastAPI,
    port_factory: LifecyclePortFactory,
    *,
    dependencies: Sequence[Any] | None = None,
) -> None:
    """Register the shared lifecycle routers and bind the port factory on ``app.state``.

    Args:
        app: Target FastAPI application.
        port_factory: Builds a request-scoped :class:`HarvestArcLifecyclePort`.
        dependencies: Optional extra FastAPI ``Depends(...)`` entries applied to all
            lifecycle routers (e.g. production content-type / accept validation).
    """
    setattr(app.state, LIFECYCLE_PORT_FACTORY_ATTR, port_factory)
    extra = list(dependencies) if dependencies else None
    app.include_router(harvests_router, dependencies=extra)
    app.include_router(arcs_router, dependencies=extra)
    app.include_router(liveness_router, dependencies=extra)


def _iter_route_entries(app: FastAPI) -> list[tuple[str, set[str], object | None]]:
    """Flatten FastAPI/Starlette route tables including nested ``_IncludedRouter`` entries.

    Returns triples of ``(path, methods, response_model_or_None)``.
    """
    entries: list[tuple[str, set[str], object | None]] = []

    def _consume(path: object, methods: object, response_model: object | None) -> None:
        if not isinstance(path, str) or not isinstance(methods, Iterable) or isinstance(methods, (str, bytes)):
            return
        method_values = cast(Iterable[object], methods)
        cleaned = {m for m in method_values if isinstance(m, str) and m not in {"HEAD", "OPTIONS"}}
        if cleaned:
            entries.append((path, cleaned, response_model))

    for route in app.routes:
        effective = getattr(route, "effective_candidates", None)
        if callable(effective):
            for candidate in effective():
                _consume(
                    getattr(candidate, "path", None),
                    getattr(candidate, "methods", None),
                    getattr(candidate, "response_model", None),
                )
            continue
        nested = getattr(route, "routes", None)
        if nested is not None:
            for child in nested:
                _consume(
                    getattr(child, "path", None),
                    getattr(child, "methods", None),
                    getattr(child, "response_model", None),
                )
            continue
        _consume(
            getattr(route, "path", None),
            getattr(route, "methods", None),
            getattr(route, "response_model", None),
        )
    return entries


def collect_route_methods(app: FastAPI) -> dict[str, set[str]]:
    """Return ``{path: {HTTP methods}}`` for routes on ``app`` (excludes HEAD/OPTIONS noise)."""
    result: dict[str, set[str]] = {}
    for path, methods, _response_model in _iter_route_entries(app):
        result.setdefault(path, set()).update(methods)
    return result


def collect_route_response_models(app: FastAPI) -> dict[tuple[str, str], object | None]:
    """Return ``{(path, method): response_model}`` for routes that declare one."""
    result: dict[tuple[str, str], object | None] = {}
    for path, methods, response_model in _iter_route_entries(app):
        for method in methods:
            result[(path, method)] = response_model
    return result


def assert_mvp_lifecycle_routes(app: FastAPI) -> None:
    """Raise ``AssertionError`` if ``app`` is missing any MVP lifecycle path/method."""
    present = collect_route_methods(app)
    missing: list[str] = []
    for path, required_methods in sorted(MVP_LIFECYCLE_ROUTES, key=lambda item: item[0]):
        have = present.get(path, set())
        absent = required_methods - have
        if absent:
            missing.append(f"{path} missing methods {sorted(absent)}")
    if missing:
        raise AssertionError("MVP lifecycle routes incomplete: " + "; ".join(missing))
