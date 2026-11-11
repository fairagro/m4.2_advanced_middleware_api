"""Offline HarvestArcLifecyclePort: filesystem ARC write + in-memory harvests."""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from arctrl import ARC
from fastapi import HTTPException, Request

from middleware.api_local_offline.filesystem_store import FilesystemArcStore, FilesystemArcStoreError
from middleware.shared.api_models.common.models import ArcLifecycleStatus, ArcStatus, HarvestStatus
from middleware.shared.api_models.common.rocrate import RoCratePayload
from middleware.shared.api_models.v3.models import (
    ArcMetadata,
    ArcResponse,
    CreateArcRequest,
    CreateHarvestRequest,
    HarvestResponse,
    LivenessResponse,
    PatchHarvestRequest,
    StatusResponse,
    SubmitHarvestArcRequest,
)
from middleware.shared.identity import calculate_arc_id
from middleware.shared.v3_lifecycle import CreateHarvestOutcome

logger = logging.getLogger(__name__)

_TERMINAL = frozenset({HarvestStatus.COMPLETED, HarvestStatus.FAILED, HarvestStatus.CANCELLED})


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class _HarvestRecord:
    harvest_id: str
    rdi: str
    status: HarvestStatus
    started_at: str
    expected_datasets: int | None = None
    completed_at: str | None = None
    arcs_submitted: int = 0
    arcs_new: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)


def _harvest_response(record: _HarvestRecord) -> HarvestResponse:
    return HarvestResponse(
        harvest_id=record.harvest_id,
        rdi=record.rdi,
        status=record.status,
        started_at=record.started_at,
        completed_at=record.completed_at,
        statistics={
            "expected_datasets": record.expected_datasets,
            "arcs_submitted": record.arcs_submitted,
            "arcs_new": record.arcs_new,
            "arcs_updated": 0,
            "arcs_unchanged": 0,
            "arcs_missing": 0,
            "errors": len(record.errors),
        },
        errors=[],
        message="",
        client_id=None,
    )


def _arc_response(arc_id: str, *, now: str) -> ArcResponse:
    return ArcResponse(
        arc_id=arc_id,
        status=ArcStatus.CREATED,
        metadata=ArcMetadata(
            arc_hash="local-offline",
            status=ArcLifecycleStatus.ACTIVE,
            first_seen=now,
            last_seen=now,
        ),
        events=[],
        message="",
        client_id=None,
    )


@dataclass
class OfflineLifecyclePort:
    """Soft-semantics adapter for the local offline stand-in."""

    store: FilesystemArcStore
    harvests: dict[str, _HarvestRecord]

    def require_harvest(self, harvest_id: str) -> _HarvestRecord:
        """Return the in-memory harvest or raise HTTP 404."""
        record = self.harvests.get(harvest_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Harvest not found")
        return record

    async def create_harvest(
        self,
        body: CreateHarvestRequest,
        *,
        idempotency_key: str | None = None,
    ) -> CreateHarvestOutcome:
        """Create an in-memory harvest run (idempotency key ignored)."""
        _ = idempotency_key  # offline does not persist idempotency keys
        harvest_id = f"harvest-{uuid.uuid4()}"
        record = _HarvestRecord(
            harvest_id=harvest_id,
            rdi=body.rdi,
            status=HarvestStatus.RUNNING,
            started_at=_now_iso(),
            expected_datasets=body.expected_datasets,
        )
        self.harvests[harvest_id] = record
        return CreateHarvestOutcome(harvest=_harvest_response(record), replayed=False)

    async def get_harvest(self, harvest_id: str) -> HarvestResponse:
        """Return harvest details from the in-memory map."""
        return _harvest_response(self.require_harvest(harvest_id))

    async def patch_harvest(self, harvest_id: str, body: PatchHarvestRequest) -> HarvestResponse:
        """Soft-transition a harvest to any terminal client status."""
        record = self.require_harvest(harvest_id)
        if body.status not in _TERMINAL:
            raise HTTPException(status_code=400, detail=f"Unsupported status: {body.status}")
        record.status = body.status
        record.completed_at = _now_iso()
        return _harvest_response(record)

    async def complete_harvest(self, harvest_id: str) -> HarvestResponse:
        """Force-complete a harvest (soft offline semantics)."""
        record = self.require_harvest(harvest_id)
        record.status = HarvestStatus.COMPLETED
        record.completed_at = _now_iso()
        return _harvest_response(record)

    async def submit_arc_in_harvest(self, harvest_id: str, body: SubmitHarvestArcRequest) -> ArcResponse:
        """Persist an ARC under the harvest RDI without conflict checks."""
        record = self.require_harvest(harvest_id)
        if record.status != HarvestStatus.RUNNING:
            raise HTTPException(status_code=409, detail=f"Harvest is {record.status.value}")
        result = await self._persist_arc(record.rdi, body.arc)
        record.arcs_submitted += 1
        record.arcs_new += 1
        return result

    async def create_or_update_arc(self, body: CreateArcRequest) -> ArcResponse:
        """Standalone ARC write to the filesystem store."""
        return await self._persist_arc(body.rdi, body.arc)

    async def liveness(self) -> LivenessResponse:
        """Return a successful stand-in liveness probe."""
        return LivenessResponse(
            status=StatusResponse.OK,
            services={"api": True, "store": self.store.check_health()},
        )

    async def _persist_arc(self, rdi: str, arc: RoCratePayload) -> ArcResponse:
        now = _now_iso()
        identifier = arc.identifier
        arc_id = calculate_arc_id(identifier, rdi)
        arc_payload = arc.to_content()
        try:
            arc_obj = ARC.from_rocrate_json_string(json.dumps(arc_payload))
            await self.store.create_or_update(arc_id, arc_obj, rdi=rdi)
        except FilesystemArcStoreError as exc:
            logger.exception("Filesystem ArcStore write failed for %s", arc_id)
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except Exception as exc:
            logger.exception("Failed to persist ARC %s", arc_id)
            raise HTTPException(status_code=500, detail=f"Failed to persist ARC: {exc}") from exc
        return _arc_response(arc_id, now=now)


def offline_port_factory(port: OfflineLifecyclePort) -> Callable[[Request], OfflineLifecyclePort]:
    """Return a mount-compatible factory that always yields the shared offline port."""

    def _factory(_request: Request) -> OfflineLifecyclePort:
        return port

    return _factory
