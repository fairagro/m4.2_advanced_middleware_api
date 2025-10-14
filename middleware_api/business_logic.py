"""Business logic module for handling ARC (Automated Research Compendium) operations.

This module provides:
- ARC status management and responses
- JSON validation and processing
- Business logic for creating, updating, and managing ARCs
"""

import asyncio
import hashlib
import json
from datetime import UTC, datetime
from enum import Enum

from arctrl import ARC  # type: ignore[import-untyped]
from pydantic import BaseModel

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

    client_id: str
    message: str


class ArcResponse(BaseModel):
    """Response model for individual ARC operations.

    Args:
        BaseModel (_type_): Pydantic BaseModel for data validation and serialization.

    """

    id: str
    status: ArcStatus
    timestamp: str


class CreateOrUpdateArcsResponse(BusinessLogicResponse):
    """Response model for create or update ARC operations."""

    arcs: list[ArcResponse]


class BusinessLogicError(Exception):
    """Base exception class for all business logic errors."""


class InvalidJsonSyntaxError(BusinessLogicError):
    """Arises when there are issues parsing the ARC JSON syntax."""


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

    def _parse_rocrate_json(self, data: str) -> list[dict]:
        try:
            crates = json.loads(data)
            if not isinstance(crates, list):
                raise InvalidJsonSyntaxError("Expected a JSON array of RO-Crates.")
            return crates
        except json.JSONDecodeError as e:
            raise InvalidJsonSyntaxError(f"Invalid RO-Crate JSON: {str(e)}") from e

    def _create_arc_id(self, identifier: str, client_id: str) -> str:
        input_str = f"{identifier}:{client_id}"
        arc_id = hashlib.sha256(input_str.encode("utf-8")).hexdigest()
        return arc_id

    async def _create_arc_from_rocrate(self, crate: dict, client_id: str) -> ArcResponse:
        try:
            crate_json = json.dumps(crate)
            arc = ARC.from_rocrate_json_string(crate_json)
        except Exception as e:
            raise InvalidJsonSemanticError(f"Error processing RO-Crate JSON: {str(e)}") from e

        identifier = getattr(arc, "Identifier", None)
        if not identifier or identifier == "":
            raise InvalidJsonSemanticError("RO-Crate JSON must contain an 'Identifier' in the ISA object.")

        exists = self._store.exists(identifier)
        await self._store.create_or_update(identifier, arc)
        status = ArcStatus.UPDATED if exists else ArcStatus.CREATED

        return ArcResponse(
            id=self._create_arc_id(identifier, client_id),
            status=status,
            timestamp=datetime.now(UTC).isoformat() + "Z",
        )

    async def _process_arcs(self, data: str, client_id: str) -> list[ArcResponse]:
        crates = self._parse_rocrate_json(data)
        tasks = [self._create_arc_from_rocrate(crate, client_id) for crate in crates]
        return await asyncio.gather(*tasks)

    # -------------------------- Whoami --------------------------

    async def whoami(self, client_id: str) -> BusinessLogicResponse:
        """Whoami operation to identify the client.

        Args:
            client_id (str): The client identifier.

        Raises:
            BusinessLogicError: If an error occurs during the operation.

        Returns:
            BusinessLogicResponse: Response containing the client ID and message.

        """
        try:
            return BusinessLogicResponse(client_id=client_id, message="Client authenticated successfully")
        except BusinessLogicError:
            raise
        except Exception as e:
            raise BusinessLogicError(f"unexpected error encountered: {str(e)}") from e

    # -------------------------- Create or Update ARCs --------------------------
    async def create_or_update_arcs(self, data: str, client_id: str) -> CreateOrUpdateArcsResponse:
        """Create or update ARCs based on the provided RO-Crate JSON data.

        Args:
            data (str): JSON string containing one or more RO-Crates.
            client_id (str): The client identifier.

        Raises:
            InvalidJsonSyntaxError: If the JSON syntax is invalid.
            InvalidJsonSemanticError: If the JSON is semantically incorrect.
            BusinessLogicError: If an error occurs during the operation.

        Returns:
            CreateOrUpdateArcsResponse: Response containing details of the processed
            ARCs.

        """
        try:
            result = await self._process_arcs(data, client_id)
            return CreateOrUpdateArcsResponse(
                client_id=client_id,
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
