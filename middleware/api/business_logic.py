"""Business logic module for handling ARC (Automated Research Compendium) operations.

This module provides:
- ARC status management and responses
- JSON validation and processing
- Business logic for creating, updating, and managing ARCs
"""

import asyncio
import json
from datetime import UTC, datetime
from enum import Enum
from typing import Annotated, Any

from arctrl import ARC  # type: ignore[import-untyped]
from pydantic import BaseModel, Field

from .arc_store import ArcStore


class ArcStatus(str, Enum):
    """Enumeration of possible ARC status values.

    Values:
        created: ARC was newly created
        updated: ARC was updated
        deleted: ARC was deleted
        requested: ARC was requested

    """

    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"
    REQUESTED = "requested"


class BusinessLogicResponse(BaseModel):
    """Base response model for business logic operations.

    Args:
        BaseModel (_type_): Pydantic BaseModel for data validation and serialization.

    """

    client_id: Annotated[str, Field(description="Client identifier which is the CN from the client certificate")]
    message: Annotated[str, Field(description="Response message")]


class WhoamiResponse(BusinessLogicResponse):
    """Response model for whoami operation."""

    accessible_rdis: Annotated[
        list[str], Field(description="List of Research Data Infrastructures the client is authorized for")
    ]


class ArcResponse(BaseModel):
    """Response model for individual ARC operations.

    Args:
        BaseModel (_type_): Pydantic BaseModel for data validation and serialization.

    """

    id: Annotated[str, Field(description="ARC identifier, as hashed value of the original identifier and RDI")]
    status: Annotated[ArcStatus, Field(description="Status of the ARC operation")]
    timestamp: Annotated[str, Field(description="Timestamp of the ARC operation in ISO 8601 format")]


class CreateOrUpdateArcsResponse(BusinessLogicResponse):
    """Response model for create or update ARC operations."""

    rdi: Annotated[str, Field(description="Research Data Infrastructure identifier the ARCs belong to")]
    arcs: Annotated[list[ArcResponse], Field(description="List of ARC responses for the operation")]


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

    # -------------------------- Whoami --------------------------

    async def whoami(self, client_id: str, accessible_rdis: list[str]) -> WhoamiResponse:
        """Whoami operation to identify the client.

        Args:
            client_id (str): The client identifier.
            accessible_rdis (list[str]): List of accessible RDIs for the client.

        Raises:
            BusinessLogicError: If an error occurs during the operation.

        Returns:
            WhoamiResponse: Response containing the client ID, message, and accessible RDIs.

        """
        try:
            return WhoamiResponse(
                client_id=client_id, message="Client authenticated successfully", accessible_rdis=accessible_rdis
            )
        except BusinessLogicError:
            raise
        except Exception as e:
            raise BusinessLogicError(f"unexpected error encountered: {str(e)}") from e

    # -------------------------- Create or Update ARCs --------------------------
    # TODO: in the first implementation, we accepted string data for ARC JSON,
    # now we accept list[Any] that is already validated using Pydantic in the API layer.
    # The question is: do we need validation on the BusinessLogic layer as well?
    # Depending on the answer, we need to refactor the current validation approach.
    async def create_or_update_arcs(self, rdi: str, arcs: list[Any], client_id: str) -> CreateOrUpdateArcsResponse:
        """Create or update ARCs based on the provided RO-Crate JSON data.

        Args:
            rdi: Research Data Infrastructure identifier.
            arcs: List of ARC definitions.
            client_id: The client identifier.

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
