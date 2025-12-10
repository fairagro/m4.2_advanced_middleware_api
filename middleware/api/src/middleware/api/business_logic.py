"""Business logic module for handling ARC (Automated Research Compendium) operations.

This module provides:
- ARC status management and responses
- JSON validation and processing
- Business logic for creating, updating, and managing ARCs
"""

import asyncio
import json
from datetime import UTC, datetime
from typing import Any

from arctrl import ARC  # type: ignore[import-untyped]

from middleware.shared.api_models.models import (
    ArcResponse,
    ArcStatus,
    CreateOrUpdateArcsResponse,
)

from .arc_store import ArcStore


class BusinessLogicError(Exception):
    """Base exception class for all business logic errors."""


class InvalidJsonSemanticError(BusinessLogicError):
    """Arises when the ARC JSON syntax is valid but semantically incorrect.

    For example, missing required fields or invalid values.
    """


class BusinessLogic:
    """Core business logic for handling ARC operations."""

    def __init__(self, store: ArcStore) -> None:
        """Initialize the BusinessLogic with the given ArcStore.

        Args:
            store (ArcStore): An instance of ArcStore for ARC persistence.

        """
        self._store = store

    async def _create_arc_from_rocrate(self, rdi: str, arc_dict: dict) -> ArcResponse:
        try:
            arc_json = json.dumps(arc_dict)
            arc = ARC.from_rocrate_json_string(arc_json)
        except Exception as e:
            raise InvalidJsonSemanticError(f"Error processing RO-Crate JSON: {e!r}") from e

        identifier = getattr(arc, "Identifier", None)
        if not identifier or identifier == "":
            raise InvalidJsonSemanticError("RO-Crate JSON must contain an 'Identifier' in the ISA object.")

        arc_id = self._store.arc_id(identifier, rdi)
        exists = self._store.exists(arc_id)
        await self._store.create_or_update(arc_id, arc)
        status = ArcStatus.UPDATED if exists else ArcStatus.CREATED

        return ArcResponse(
            id=arc_id,
            status=status,
            timestamp=datetime.now(UTC).isoformat() + "Z",
        )

    async def _process_arcs(self, rdi: str, arcs: list[Any]) -> list[ArcResponse]:
        tasks = [self._create_arc_from_rocrate(rdi, arc) for arc in arcs]
        return await asyncio.gather(*tasks)

    # -------------------------- Create or Update ARCs --------------------------
    # TODO: in the first implementation, we accepted string data for ARC JSON,
    # now we accept list[Any] that is already validated using Pydantic in the API layer.
    # The question is: do we need validation on the BusinessLogic layer as well?
    # Depending on the answer, we need to refactor the current validation approach.
    async def create_or_update_arcs(
        self, rdi: str, arcs: list[Any], client_id: str | None
    ) -> CreateOrUpdateArcsResponse:
        """Create or update ARCs based on the provided RO-Crate JSON data.

        Args:
            rdi: Research Data Infrastructure identifier.
            arcs: List of ARC definitions.
            client_id: The client identifier, or None if not authenticated.

        Raises:
            InvalidJsonSemanticError: If the JSON is semantically incorrect.
            BusinessLogicError: If an error occurs during the operation.

        Returns:
            CreateOrUpdateArcsResponse: Response containing details of the processed
            ARCs.

        """
        try:
            result = await self._process_arcs(rdi, arcs)
            return CreateOrUpdateArcsResponse(
                client_id=client_id,
                rdi=rdi,
                message="ARCs processed successfully",
                arcs=result,
            )
        except BusinessLogicError:
            raise
        except Exception as e:
            raise BusinessLogicError(f"unexpected error encountered: {str(e)}") from e

    # # -------------------------
    # # READ ARCs
    # # -------------------------
    # @app.get("/arcs", response_model=List[ARC])
    # async def get_arcs():
    #     return list(ARC_DB.values())

    # @app.get("/arcs/{arc_id}")
    # async def get_arc(arc_id: str, request: Request):
    #     arc = ARC_DB.get(arc_id)
    #     if not arc:
    #         raise HTTPException(status_code=404, detail="ARC not found")
    #     accept = request.headers.get("accept", "application/json")
    #     return JSONResponse(content=serialize_arc(arc, accept))

    # # -------------------------
    # # UPDATE ARC
    # # -------------------------
    # @app.put("/arcs/{arc_id}")
    # async def update_arc(arc_id: str, updated: ARC):
    #     if arc_id not in ARC_DB:
    #         raise HTTPException(status_code=404, detail="ARC not found")
    #     updated.id = arc_id
    #     updated.created_at = ARC_DB[arc_id]["created_at"]
    #     updated.updated_at = datetime.now(UTC).isoformat() + "Z"
    #     ARC_DB[arc_id] = updated.dict()
    #     return updated

    # @app.patch("/arcs/{arc_id}")
    # async def patch_arc(arc_id: str, patch_data: dict):
    #     if arc_id not in ARC_DB:
    #         raise HTTPException(status_code=404, detail="ARC not found")
    #     arc = ARC_DB[arc_id]
    #     arc.update(patch_data)
    #     arc["updated_at"] = datetime.now(UTC).isoformat() + "Z"
    #     ARC_DB[arc_id] = arc
    #     return arc

    # # -------------------------
    # # DELETE ARC
    # # -------------------------
    # @app.delete("/arcs/{arc_id}", status_code=204)
    # async def delete_arc(arc_id: str):
    #     if arc_id not in ARC_DB:
    #         raise HTTPException(status_code=404, detail="ARC not found")
    #     del ARC_DB[arc_id]
    #     return Response(status_code=204)
