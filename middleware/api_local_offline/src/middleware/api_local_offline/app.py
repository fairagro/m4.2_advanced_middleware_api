"""Thin FastAPI stand-in: enough HTTP for ApiClient, ARCs on disk."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from arctrl import ARC
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from middleware.api_local_offline.arc_id import calculate_arc_id
from middleware.api_local_offline.config import LocalOfflineConfig
from middleware.api_local_offline.filesystem_store import FilesystemArcStore, FilesystemArcStoreError

logger = logging.getLogger(__name__)

_TERMINAL = frozenset({"COMPLETED", "FAILED", "CANCELLED"})


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class _HarvestRecord:
    harvest_id: str
    rdi: str
    status: str
    started_at: str
    expected_datasets: int | None = None
    completed_at: str | None = None
    arcs_submitted: int = 0
    arcs_new: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)


def _harvest_json(record: _HarvestRecord) -> dict[str, Any]:
    return {
        "harvest_id": record.harvest_id,
        "rdi": record.rdi,
        "status": record.status,
        "started_at": record.started_at,
        "completed_at": record.completed_at,
        "statistics": {
            "expected_datasets": record.expected_datasets,
            "arcs_submitted": record.arcs_submitted,
            "arcs_new": record.arcs_new,
            "arcs_updated": 0,
            "arcs_unchanged": 0,
            "arcs_missing": 0,
            "errors": len(record.errors),
        },
        "errors": record.errors,
        "message": "",
        "client_id": None,
    }


def _arc_json(arc_id: str, *, now: str) -> dict[str, Any]:
    return {
        "arc_id": arc_id,
        "status": "created",
        "metadata": {
            "arc_hash": "local-offline",
            "status": "ACTIVE",
            "first_seen": now,
            "last_seen": now,
        },
        "events": [],
        "message": "",
        "client_id": None,
    }


def _extract_identifier(arc_payload: dict[str, Any]) -> str:
    raw = arc_payload.get("identifier")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    graph = arc_payload.get("@graph")
    if isinstance(graph, list):
        for node in graph:
            if not isinstance(node, dict):
                continue
            if node.get("@id") in {"./", ""}:
                ident = node.get("identifier")
                if isinstance(ident, str) and ident.strip():
                    return ident.strip()
    return f"arc-{uuid.uuid4().hex[:8]}"


def _as_object(data: Any) -> dict[str, Any] | None:
    return data if isinstance(data, dict) else None


def _optional_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


async def _persist_arc(store: FilesystemArcStore, rdi: str, arc_payload: dict[str, Any]) -> dict[str, Any]:
    now = _now_iso()
    identifier = _extract_identifier(arc_payload)
    arc_id = calculate_arc_id(identifier, rdi)
    try:
        arc_obj = ARC.from_rocrate_json_string(json.dumps(arc_payload))
        await store.create_or_update(arc_id, arc_obj, rdi=rdi)
    except FilesystemArcStoreError as exc:
        logger.exception("Filesystem ArcStore write failed for %s", arc_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to persist ARC %s", arc_id)
        raise HTTPException(status_code=500, detail=f"Failed to persist ARC: {exc}") from exc
    return _arc_json(arc_id, now=now)


@dataclass
class _OfflineHandlers:
    store: FilesystemArcStore
    harvests: dict[str, _HarvestRecord]

    def require_harvest(self, harvest_id: str) -> _HarvestRecord:
        record = self.harvests.get(harvest_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Harvest not found")
        return record

    @staticmethod
    def live() -> dict[str, str]:
        return {"status": "ok"}

    def readiness(self) -> JSONResponse:
        if self.store.check_health():
            return JSONResponse({"status": "ready"})
        return JSONResponse({"status": "not ready"}, status_code=503)

    async def create_harvest(self, request: Request) -> dict[str, Any]:
        data = _as_object(await request.json()) or {}
        rdi_val = data.get("rdi")
        rdi = str(rdi_val) if rdi_val is not None else "unknown"
        harvest_id = f"harvest-{uuid.uuid4()}"
        record = _HarvestRecord(
            harvest_id=harvest_id,
            rdi=rdi,
            status="RUNNING",
            started_at=_now_iso(),
            expected_datasets=_optional_int(data.get("expected_datasets")),
        )
        self.harvests[harvest_id] = record
        return _harvest_json(record)

    async def get_harvest(self, harvest_id: str) -> dict[str, Any]:
        return _harvest_json(self.require_harvest(harvest_id))

    async def submit_arc_in_harvest(self, harvest_id: str, request: Request) -> dict[str, Any]:
        record = self.require_harvest(harvest_id)
        if record.status != "RUNNING":
            raise HTTPException(status_code=409, detail=f"Harvest is {record.status}")
        data = _as_object(await request.json()) or {}
        arc_payload = _as_object(data.get("arc", data))
        if arc_payload is None:
            raise HTTPException(status_code=400, detail="ARC payload must be an object")
        result = await _persist_arc(self.store, record.rdi, arc_payload)
        record.arcs_submitted += 1
        record.arcs_new += 1
        return result

    async def complete_harvest(self, harvest_id: str) -> dict[str, Any]:
        record = self.require_harvest(harvest_id)
        record.status = "COMPLETED"
        record.completed_at = _now_iso()
        return _harvest_json(record)

    async def patch_harvest(self, harvest_id: str, request: Request) -> dict[str, Any]:
        record = self.require_harvest(harvest_id)
        data = _as_object(await request.json()) or {}
        status = str(data.get("status") or "").upper()
        if status not in _TERMINAL:
            raise HTTPException(status_code=400, detail=f"Unsupported status: {status}")
        record.status = status
        record.completed_at = _now_iso()
        return _harvest_json(record)

    async def upload_arc(self, request: Request) -> dict[str, Any]:
        rdi_param = request.query_params.get("rdi")
        data = _as_object(await request.json()) or {}
        arc_payload = _as_object(data.get("arc", data))
        if arc_payload is None:
            raise HTTPException(status_code=400, detail="ARC payload must be an object")
        rdi = rdi_param if rdi_param is not None else str(data.get("rdi", "unknown"))
        return await _persist_arc(self.store, rdi, arc_payload)


def create_local_offline_app(config: LocalOfflineConfig) -> FastAPI:
    """Build the local offline FastAPI application."""
    store = FilesystemArcStore(config)
    handlers = _OfflineHandlers(store=store, harvests={})
    app = FastAPI(title="Middleware API (local offline)", version="local-offline")
    app.state.local_offline_config = config
    app.state.filesystem_arc_store = store
    app.add_api_route("/live", handlers.live, methods=["GET"])
    app.add_api_route("/v3/readiness", handlers.readiness, methods=["GET"])
    app.add_api_route("/v3/harvests", handlers.create_harvest, methods=["POST"])
    app.add_api_route("/v3/harvests/{harvest_id}", handlers.get_harvest, methods=["GET"])
    app.add_api_route("/v3/harvests/{harvest_id}/arcs", handlers.submit_arc_in_harvest, methods=["POST"])
    app.add_api_route("/v3/harvests/{harvest_id}/complete", handlers.complete_harvest, methods=["POST"])
    app.add_api_route("/v3/harvests/{harvest_id}", handlers.patch_harvest, methods=["PATCH"])
    app.add_api_route("/v3/arcs", handlers.upload_arc, methods=["POST"])
    return app
