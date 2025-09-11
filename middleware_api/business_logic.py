import hashlib
import json
from enum import Enum
from datetime import datetime, timezone
from typing import List, Dict
from pydantic import BaseModel
from arctrl import ARC

from .arc_store import ArcStore


class ArcStatus(str, Enum):
    created = "created"
    updated = "updated"
    deleted = "deleted"
    requested = "requested"


class BusinessLogicResponse(BaseModel):
    client_id: str
    message: str


class ArcResponse(BaseModel):
    id: str
    status: ArcStatus
    timestamp: str


class CreateOrUpdateArcsResponse(BusinessLogicResponse):
    arcs: List[ArcResponse]


class BusinessLogicError(Exception):
    """Basisklasse für Fehler in MiddlewareService"""
    pass


class InvalidJsonSyntaxError(BusinessLogicError):
    """Wird geworfen, wenn es Probleme beim Parsen des ARC JSON gibt"""
    pass


class InvalidJsonSemanticError(BusinessLogicError):
    """Wird geworfen, wenn es Probleme beim Parsen des ARC JSON gibt"""
    pass


class BusinessLogic:

    def __init__(self, store: ArcStore):
        self._store = store

    def _parse_rocrate_json(self, data: str) -> List[Dict]:
        try:
            crates = json.loads(data)
            if not isinstance(crates, list):
                raise InvalidJsonSyntaxError(
                    "Expected a JSON array of RO-Crates.")
            return crates
        except json.JSONDecodeError as e:
            raise InvalidJsonSyntaxError(f"Invalid RO-Crate JSON: {str(e)}") from e

    def _create_arc_id(self, identifier: str, client_id: str) -> str:
        input_str = f"{identifier}:{client_id}"
        arc_id = hashlib.sha256(input_str.encode("utf-8")).hexdigest()
        return arc_id

    def _create_arc_from_rocrate(self, crate: Dict, client_id: str) -> ArcResponse:
        try:
            crate_json = json.dumps(crate)
            arc = ARC.from_rocrate_json_string(crate_json)
        except Exception as e:
            raise InvalidJsonSemanticError(
                f"Error processing RO-Crate JSON: {str(e)}") from e

        identifier = getattr(arc, "Identifier", None)
        if not identifier or identifier == "":
            raise InvalidJsonSemanticError(
                "RO-Crate JSON must contain an 'Identifier' in the ISA object."
            )

        exists = self._store.exists(identifier)
        self._store.create_or_update(identifier, arc)
        status = ArcStatus.updated if exists else ArcStatus.created

        return ArcResponse(
            id=self._create_arc_id(identifier, client_id),
            status=status,
            timestamp=datetime.now(timezone.utc).isoformat() + "Z",
        )

    async def _process_arcs(self, data: str, client_id: str) -> List[ArcResponse]:
        crates = self._parse_rocrate_json(data)
        result = []

        for crate in crates:
            arc_response = self._create_arc_from_rocrate(crate, client_id)
            result.append(arc_response)

        return result

    # -------------------------- Whoami --------------------------

    async def whoami(self, client_id: str) -> BusinessLogicResponse:
        try:
            return BusinessLogicResponse(
                client_id=client_id,
                message="Client authenticated successfully"
            )
        except BusinessLogicError:
            raise
        except Exception as e:
            raise BusinessLogicError(
                f"unexpected error encountered: {str(e)}") from e

    # -------------------------- Create or Update ARCs --------------------------
    async def create_or_update_arcs(
            self, data: str, client_id: str) -> CreateOrUpdateArcsResponse:
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
            raise BusinessLogicError(
                f"unexpected error encountered: {str(e)}") from e

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
    #     updated.updated_at = datetime.utcnow()
    #     ARC_DB[arc_id] = updated.dict()
    #     return updated

    # @app.patch("/arcs/{arc_id}")
    # async def patch_arc(arc_id: str, patch_data: dict):
    #     if arc_id not in ARC_DB:
    #         raise HTTPException(status_code=404, detail="ARC not found")
    #     arc = ARC_DB[arc_id]
    #     arc.update(patch_data)
    #     arc["updated_at"] = datetime.utcnow()
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
