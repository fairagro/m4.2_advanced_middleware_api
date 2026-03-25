"""Modular V3 Harvest endpoints using APIRouter."""

from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from middleware.api.api.common.dependencies import (
    CommonApiDependencies,
    get_accept_type,
    get_business_logic,
    get_client_id,
    get_common_deps,
    get_content_type,
)
from middleware.api.business_logic import BusinessLogic
from middleware.api.document_store.harvest_document import HarvestDocument
from middleware.shared.api_models.v3 import models as v3_models

router = APIRouter(prefix="/v3/harvests", tags=["v3", "harvests"])


@router.post("", response_model=v3_models.HarvestResponse)
async def create_harvest(  # noqa: PLR0913, PLR0917
    request: Request,
    request_body: v3_models.CreateHarvestRequest,
    bl: Annotated[BusinessLogic, Depends(get_business_logic)],
    deps: Annotated[CommonApiDependencies, Depends(get_common_deps)],
    client_id: Annotated[str | None, Depends(get_client_id)],
    _content_type: Annotated[None, Depends(get_content_type)],
    _accept_type: Annotated[None, Depends(get_accept_type)],
) -> v3_models.HarvestResponse:
    """Start a new harvest run."""
    await deps.validate_rdi_authorized(request_body.rdi, request)

    harvest_id = await bl.harvest_manager.create_harvest(
        request_body.rdi, client_id=client_id, expected_datasets=request_body.expected_datasets
    )

    harvest = await bl.harvest_manager.get_harvest(harvest_id)
    if not harvest:
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail="Failed to create harvest")

    return _map_harvest(harvest)


@router.get("", response_model=list[v3_models.HarvestResponse])
async def list_harvests(
    request: Request,
    bl: Annotated[BusinessLogic, Depends(get_business_logic)],
    deps: Annotated[CommonApiDependencies, Depends(get_common_deps)],
    _client_id: Annotated[str | None, Depends(get_client_id)],
    _accept_type: Annotated[None, Depends(get_accept_type)],
    rdi: str | None = None,
) -> list[v3_models.HarvestResponse]:
    """List harvest runs."""
    if rdi:
        await deps.validate_rdi_authorized(rdi, request)

    harvests = await bl.harvest_manager.list_harvests(rdi)
    return [_map_harvest(h) for h in harvests]


@router.get("/{harvest_id}", response_model=v3_models.HarvestResponse)
async def get_harvest(
    request: Request,
    harvest_id: str,
    bl: Annotated[BusinessLogic, Depends(get_business_logic)],
    deps: Annotated[CommonApiDependencies, Depends(get_common_deps)],
    _client_id: Annotated[str | None, Depends(get_client_id)],
) -> v3_models.HarvestResponse:
    """Get harvest details."""
    harvest = await bl.harvest_manager.get_harvest(harvest_id)
    if not harvest:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Harvest not found")

    await deps.validate_rdi_authorized(harvest.rdi, request)
    return _map_harvest(harvest)


@router.post("/{harvest_id}/complete", response_model=v3_models.HarvestResponse)
async def complete_harvest(  # noqa: PLR0913, PLR0917
    request: Request,
    harvest_id: str,
    bl: Annotated[BusinessLogic, Depends(get_business_logic)],
    deps: Annotated[CommonApiDependencies, Depends(get_common_deps)],
    client_id: Annotated[str | None, Depends(get_client_id)],
) -> v3_models.HarvestResponse:
    """Mark a harvest as completed."""
    harvest = await bl.harvest_manager.get_harvest(harvest_id)
    if not harvest:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Harvest not found")

    await deps.validate_rdi_authorized(harvest.rdi, request)

    harvest = await bl.harvest_manager.complete_harvest(harvest_id, client_id=client_id)
    return _map_harvest(harvest)


@router.delete("/{harvest_id}", status_code=HTTPStatus.NO_CONTENT)
async def cancel_harvest(
    request: Request,
    harvest_id: str,
    bl: Annotated[BusinessLogic, Depends(get_business_logic)],
    deps: Annotated[CommonApiDependencies, Depends(get_common_deps)],
    client_id: Annotated[str | None, Depends(get_client_id)],
) -> None:
    """Cancel a harvest run."""
    harvest = await bl.harvest_manager.get_harvest(harvest_id)
    if not harvest:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Harvest not found")

    await deps.validate_rdi_authorized(harvest.rdi, request)
    await bl.harvest_manager.cancel_harvest(harvest_id, client_id=client_id)


@router.post("/{harvest_id}/arcs", response_model=v3_models.ArcResponse)
async def submit_arc_in_harvest(  # noqa: PLR0913, PLR0917
    request: Request,
    harvest_id: str,
    request_body: v3_models.SubmitHarvestArcRequest,
    bl: Annotated[BusinessLogic, Depends(get_business_logic)],
    deps: Annotated[CommonApiDependencies, Depends(get_common_deps)],
    client_id: Annotated[str | None, Depends(get_client_id)],
) -> v3_models.ArcResponse:
    """Submit an ARC within a harvest context.

    The ``rdi`` is resolved automatically from the harvest run.
    """
    harvest = await bl.harvest_manager.get_harvest(harvest_id)
    if not harvest:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Harvest not found")

    rdi = harvest.rdi
    await deps.validate_rdi_authorized(rdi, request)

    result = await bl.create_or_update_arc(rdi, request_body.arc, client_id, harvest_id=harvest_id)

    arc_id = result.arc.id
    metadata = await bl.get_metadata(arc_id)

    if not metadata:
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail="Failed to retrieve ARC metadata")

    return v3_models.ArcResponse(
        client_id=client_id,
        message="ARC processed successfully in harvest",
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
    )
