"""Thin FastAPI stand-in: enough HTTP for ApiClient, ARCs on disk."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from middleware.api_local_offline.config import LocalOfflineConfig
from middleware.api_local_offline.filesystem_store import FilesystemArcStore
from middleware.api_local_offline.lifecycle_port import OfflineLifecyclePort, offline_port_factory
from middleware.api_v3 import mount_lifecycle_routes


def create_local_offline_app(config: LocalOfflineConfig) -> FastAPI:
    """Build the local offline FastAPI application."""
    store = FilesystemArcStore(config)
    port = OfflineLifecyclePort(store=store, harvests={})
    app = FastAPI(title="Middleware API (local offline)", version="local-offline")
    app.state.local_offline_config = config
    app.state.filesystem_arc_store = store
    app.state.offline_lifecycle_port = port

    mount_lifecycle_routes(app, offline_port_factory(port))

    # Legacy alias kept for smoke clients that still probe /live.
    @app.get("/live")
    def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.api_route("/v3/readiness", methods=["GET", "HEAD"])
    def readiness() -> JSONResponse:
        if store.check_health():
            return JSONResponse({"status": "ready"})
        return JSONResponse({"status": "not ready"}, status_code=503)

    return app
