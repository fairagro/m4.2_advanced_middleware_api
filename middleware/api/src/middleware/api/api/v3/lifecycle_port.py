"""Production HarvestArcLifecyclePort over BusinessLogic + RDI auth."""

from __future__ import annotations

from http import HTTPStatus

from fastapi import HTTPException, Request

from middleware.api.api.common.dependencies import CommonApiDependencies, get_client_id
from middleware.api.business_logic import BusinessLogic, ConflictError
from middleware.api.business_logic.exceptions import ArcIdentityMismatchError, DuplicateArcInHarvestError
from middleware.api.document_store.harvest_document import HarvestDocument
from middleware.api.health_service import ApiHealthService
from middleware.shared.api_models.common.models import ArcOperationResult, HarvestStatus
from middleware.shared.api_models.v3 import models as v3_models
from middleware.shared.v3_lifecycle import CreateHarvestOutcome


def _map_harvest(harvest: HarvestDocument) -> v3_models.HarvestResponse:
    """Map DB harvest record to API response model."""
    completed_at = None
    if harvest.completed_at:
        completed_at = harvest.completed_at.isoformat().replace("+00:00", "Z")

    return v3_models.HarvestResponse(
        harvest_id=harvest.doc_id,
        rdi=harvest.rdi,
        status=v3_models.HarvestStatus(harvest.status),
        started_at=harvest.started_at.isoformat().replace("+00:00", "Z"),
        completed_at=completed_at,
        statistics=harvest.statistics.model_dump() if harvest.statistics else {},
        errors=list(harvest.errors),
    )


class ProductionLifecyclePort:
    """Strict production adapter: auth, 409 identity/duplicate, manager semantics."""

    def __init__(
        self,
        request: Request,
        *,
        business_logic: BusinessLogic,
        deps: CommonApiDependencies,
        health_service: ApiHealthService,
    ) -> None:
        """Bind request-scoped production dependencies."""
        self._request = request
        self._bl = business_logic
        self._deps = deps
        self._health_service = health_service
        self._client_id_resolved = False
        self._client_id: str | None = None

    async def _require_client_id(self) -> str | None:
        if not self._client_id_resolved:
            self._client_id = await get_client_id(self._request)
            self._client_id_resolved = True
        return self._client_id

    async def create_harvest(
        self,
        body: v3_models.CreateHarvestRequest,
        *,
        idempotency_key: str | None = None,
    ) -> CreateHarvestOutcome:
        """Create a harvest run (or return the idempotent replay)."""
        await self._deps.validate_content_type(self._request)
        await self._deps.validate_accept_type(self._request)
        await self._deps.validate_rdi_authorized(body.rdi, self._request)
        client_id = await self._require_client_id()
        created = await self._bl.harvest_manager.create_harvest(
            body.rdi,
            client_id=client_id,
            expected_datasets=body.expected_datasets,
            idempotency_key=idempotency_key,
        )
        harvest = await self._bl.harvest_manager.get_harvest(created.harvest_id)
        if not harvest:
            raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail="Failed to create harvest")
        return CreateHarvestOutcome(harvest=_map_harvest(harvest), replayed=created.replayed)

    async def get_harvest(self, harvest_id: str) -> v3_models.HarvestResponse:
        """Return harvest details; missing/unauthorized map to 404."""
        await self._require_client_id()
        harvest = await self._bl.harvest_manager.get_harvest(harvest_id)
        if not harvest:
            raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Harvest not found")
        try:
            await self._deps.validate_rdi_authorized(harvest.rdi, self._request)
        except HTTPException as exc:
            # Return 404 regardless of whether the harvest exists but the caller is
            # not authorised: leaking the existence of a harvest (403 vs 404) is an
            # information-disclosure vulnerability (C1).
            if exc.status_code in {HTTPStatus.FORBIDDEN, HTTPStatus.UNAUTHORIZED}:
                raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Harvest not found") from exc
            raise
        return _map_harvest(harvest)

    async def patch_harvest(
        self,
        harvest_id: str,
        body: v3_models.PatchHarvestRequest,
    ) -> v3_models.HarvestResponse:
        """Transition a harvest to a terminal client status."""
        await self._deps.validate_content_type(self._request)
        harvest = await self._bl.harvest_manager.get_harvest(harvest_id)
        if not harvest:
            raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Harvest not found")
        await self._deps.validate_rdi_authorized(harvest.rdi, self._request)
        client_id = await self._require_client_id()
        try:
            harvest = await self._bl.transition_harvest(harvest, body.status, client_id=client_id)
        except ConflictError as exc:
            raise HTTPException(status_code=HTTPStatus.CONFLICT, detail=str(exc)) from exc
        return _map_harvest(harvest)

    async def complete_harvest(self, harvest_id: str) -> v3_models.HarvestResponse:
        """Complete a harvest (deprecated POST complete path)."""
        harvest = await self._bl.harvest_manager.get_harvest(harvest_id)
        if not harvest:
            raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Harvest not found")
        await self._deps.validate_rdi_authorized(harvest.rdi, self._request)
        client_id = await self._require_client_id()
        harvest = await self._bl.complete_harvest(harvest, client_id=client_id)
        return _map_harvest(harvest)

    async def submit_arc_in_harvest(
        self,
        harvest_id: str,
        body: v3_models.SubmitHarvestArcRequest,
    ) -> v3_models.ArcResponse:
        """Submit an ARC within a harvest context."""
        harvest = await self._bl.harvest_manager.get_harvest(harvest_id)
        if not harvest:
            raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Harvest not found")
        rdi = harvest.rdi
        await self._deps.validate_rdi_authorized(rdi, self._request)
        if harvest.status != HarvestStatus.RUNNING:
            raise ConflictError(
                f"Cannot submit ARC to harvest {harvest_id}: harvest status is {harvest.status.value}, expected RUNNING"
            )
        client_id = await self._require_client_id()
        try:
            result = await self._bl.create_or_update_arc(rdi, body.arc, client_id, harvest_id=harvest_id)
        except DuplicateArcInHarvestError as exc:
            await self._bl.harvest_manager.try_append_error(
                harvest_id,
                arc_id=body.arc.identifier,
                error_type=v3_models.HarvestErrorType.DUPLICATE,
                message=str(exc),
            )
            raise HTTPException(status_code=HTTPStatus.CONFLICT, detail=str(exc)) from exc
        except ArcIdentityMismatchError as exc:
            await self._bl.harvest_manager.try_append_error(
                harvest_id,
                arc_id=body.arc.identifier,
                error_type=v3_models.HarvestErrorType.SUBMISSION_FAILED,
                message=str(exc),
            )
            raise HTTPException(status_code=HTTPStatus.CONFLICT, detail=str(exc)) from exc

        return await self._arc_response(result, client_id=client_id, message="ARC processed successfully in harvest")

    async def create_or_update_arc(self, body: v3_models.CreateArcRequest) -> v3_models.ArcResponse:
        """Standalone ARC create/update."""
        await self._deps.validate_content_type(self._request)
        await self._deps.validate_accept_type(self._request)
        await self._deps.validate_rdi_authorized(body.rdi, self._request)
        client_id = await self._require_client_id()
        result = await self._bl.create_or_update_arc(body.rdi, body.arc, client_id)
        return await self._arc_response(result, client_id=client_id, message="ARC processed successfully")

    async def liveness(self) -> v3_models.LivenessResponse:
        """Return process liveness from the production health service."""
        await self._deps.validate_accept_type(self._request)
        checks = await self._health_service.liveness_checks()
        return v3_models.LivenessResponse(
            status=v3_models.StatusResponse.OK if all(checks.values()) else v3_models.StatusResponse.ERROR,
            services=checks,
        )

    async def _arc_response(
        self,
        result: ArcOperationResult,
        *,
        client_id: str | None,
        message: str,
    ) -> v3_models.ArcResponse:
        arc_id = result.arc.id
        metadata = await self._bl.get_metadata(arc_id)
        if not metadata:
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve ARC metadata",
            )
        return v3_models.ArcResponse(
            client_id=client_id,
            message=message,
            arc_id=arc_id,
            status=result.arc.status,
            metadata=v3_models.ArcMetadata(
                arc_hash=metadata.arc_hash,
                status=metadata.status,
                first_seen=metadata.first_seen.isoformat() + "Z",
                last_seen=metadata.last_seen.isoformat() + "Z",
            ),
            events=[
                v3_models.ArcEventSummary(
                    timestamp=event.timestamp.isoformat() + "Z",
                    type=event.type,
                    message=event.message,
                )
                for event in metadata.events
            ],
        )


def production_port_factory(request: Request) -> ProductionLifecyclePort:
    """Build a request-scoped production lifecycle port.

    Client-cert resolution is deferred until harvest/ARC mutations so probes like
    ``GET /v3/liveness`` stay unauthenticated (same as the former system route).
    """
    return ProductionLifecyclePort(
        request,
        business_logic=request.app.state.business_logic,
        deps=request.app.state.common_deps,
        health_service=request.app.state.health_service,
    )
