"""Modular V3 ARC endpoints using APIRouter."""

import logging
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from middleware.api.business_logic import BusinessLogic
from middleware.api.common.dependencies import (
    CommonApiDependencies,
    get_accept_type,
    get_business_logic,
    get_client_id,
    get_common_deps,
    get_content_type,
)
from middleware.shared.api_models.v3 import models

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v3/arcs", tags=["v3", "arcs"])


@router.post("", response_model=models.ArcResponse)
async def create_or_update_arc(
    request: Request,
    request_body: models.CreateArcRequest,
    bl: Annotated[BusinessLogic, Depends(get_business_logic)],
    deps: Annotated[CommonApiDependencies, Depends(get_common_deps)],
    client_id: Annotated[str, Depends(get_client_id)],
    _: Annotated[None, Depends(get_content_type)],
    __: Annotated[None, Depends(get_accept_type)],
) -> models.ArcResponse:
    """Process an ARC and return the result directly."""
    # Note: RDI validation is currently missing here, let's add it based on request body or params if needed.
    rdi = request_body.rdi
    await deps.validate_rdi_authorized(rdi, request)

    try:
        result = await bl.create_or_update_arc(rdi, request_body.arc, client_id)

        arc_id = result.arc.id
        metadata = await bl.get_metadata(arc_id)

        if not metadata:
            raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail="Failed to retrieve ARC metadata")

        return models.ArcResponse(
            client_id=client_id,
            message="ARC processed successfully",
            arc_id=arc_id,
            status=result.arc.status,
            metadata=models.ArcMetadata(
                arc_hash=metadata.arc_hash,
                status=metadata.status,
                first_seen=metadata.first_seen.isoformat() + "Z",
                last_seen=metadata.last_seen.isoformat() + "Z",
            ),
            events=[
                models.ArcEventSummary(
                    timestamp=event.timestamp.isoformat() + "Z",
                    type=event.type,
                    message=event.message,
                )
                for event in metadata.events
            ],
        )
    except Exception as e:
        logger.error("Error in v3 ARC endpoint: %s", e, exc_info=True)
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(e)) from e
