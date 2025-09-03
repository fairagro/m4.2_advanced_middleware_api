import hashlib
import json
from enum import Enum
from datetime import datetime, timezone
from typing import List, Dict
from pydantic import BaseModel
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from arctrl import ARC

from .arc_store import ARCStore


class ARCStatus(str, Enum):
    created = "created"
    updated = "updated"
    deleted = "deleted"
    requested = "requested"


class MiddlewareResponse(BaseModel):
    client_id: str
    message: str

class ARCResponse(BaseModel):
    id: str
    status: ARCStatus
    timestamp: str

class CreateOrUpdateResponse(MiddlewareResponse):
    arcs: List[ARCResponse]


class MiddlewareError(Exception):
    """Basisklasse für Fehler in MiddlewareService"""
    pass

class ClientCertMissingError(MiddlewareError):
    """Wird geworfen, wenn kein Zertifikat vorhanden ist"""
    pass

class ClientCertParsingError(MiddlewareError):
    """Wird geworfen, wenn es Probleme beim Parsen des Client-Zertifikats gibt"""
    pass

class InvalidContentTypeError(MiddlewareError):
    """Wird geworfen, wenn der Content-Type nicht passt"""
    pass

class InvalidAcceptTypeError(MiddlewareError):
    """Wird geworfen, wenn der Accept-Type nicht passt"""
    pass

class InvalidJsonSyntaxError(MiddlewareError):
    """Wird geworfen, wenn es Probleme beim Parsen des ARC JSON gibt"""
    pass

class InvalidJsonSemanticError(MiddlewareError):
    """Wird geworfen, wenn es Probleme beim Parsen des ARC JSON gibt"""
    pass


class MiddlewareService:

    # Constants
    SUPPORTED_CONTENT_TYPE = "application/ro-crate+json"
    SUPPORTED_ACCEPT_TYPE = "application/json"

    def __init__(self, store: ARCStore):
        self._store = store

    def _get_client_id(self, client_cert: str | None) -> str:
        if not client_cert:
            raise ClientCertMissingError("Client certificate missing")

        try:
            pem = client_cert.replace("\n", "\n")
            cert_obj = x509.load_pem_x509_certificate(
                pem.encode(), default_backend())
            value = cert_obj.subject.get_attributes_for_oid(
                x509.NameOID.COMMON_NAME)[0].value
            return bytes(value).decode() if isinstance(value, (bytes, bytearray, memoryview)) else str(value)
        except ValueError as e:
            raise ClientCertParsingError(
                f"Invalid certificate format: {str(e)}")
        except Exception as e:
            raise ClientCertParsingError(
                f"Certificate parsing error: {str(e)}")

    def _validate_content_type(self, content_type: str | None) -> None:
        if not content_type:
            raise InvalidContentTypeError(
                f"Content-Type header is missing. Expected '{self.SUPPORTED_CONTENT_TYPE}'.")
        if content_type != self.SUPPORTED_CONTENT_TYPE:
            raise InvalidContentTypeError(
                f"Unsupported Media Type. Supported types: '{self.SUPPORTED_CONTENT_TYPE}'."
            )

    def _validate_accept_type(self, accept: str | None) -> None:
        if accept not in [self.SUPPORTED_ACCEPT_TYPE, "*/*"]:
            raise InvalidAcceptTypeError(
                f"Unsupported Response Type. Supported types: '{self.SUPPORTED_ACCEPT_TYPE}'."
            )

    def _parse_rocrate_json(self, data: str) -> List[Dict]:
        try:
            crates = json.loads(data)
            if not isinstance(crates, list):
                raise InvalidJsonSyntaxError(
                    "Expected a JSON array of RO-Crates.")
            return crates
        except json.JSONDecodeError as e:
            raise InvalidJsonSyntaxError(f"Invalid RO-Crate JSON: {str(e)}")

    def _create_arc_id(self, identifier: str, client_id: str) -> str:
        input_str = f"{identifier}:{client_id}"
        arc_id = hashlib.sha256(input_str.encode("utf-8")).hexdigest()
        return arc_id

    def _create_arc_from_rocrate(self, crate: Dict, client_id: str) -> ARCResponse:
        try:
            crate_json = json.dumps(crate)
            arc = ARC.from_rocrate_json_string(crate_json)
        except Exception as e:
            raise InvalidJsonSemanticError(
                f"Error processing RO-Crate JSON: {str(e)}")

        identifier = getattr(arc, "Identifier", None)
        if not identifier:
            raise InvalidJsonSemanticError(
                "RO-Crate JSON must contain an 'Identifier' in the ISA object."
            )

        exists = False  # TODO: Check if ARC already exists
        status = ARCStatus.updated if exists else ARCStatus.created

        return ARCResponse(
            id=self._create_arc_id(identifier, client_id),
            status=status,
            timestamp=datetime.now(timezone.utc).isoformat() + "Z",
        )

    async def _process_arcs(self, data: str, client_id: str) -> List[ARCResponse]:
        crates = self._parse_rocrate_json(data)
        result = []

        for crate in crates:
            arc_response = self._create_arc_from_rocrate(crate, client_id)
            result.append(arc_response)
            # TODO: persist ARC to database or file system

        return result

    # -------------------------- Whoami --------------------------

    async def whoami(self, client_cert: str | None, accept_type: str | None) -> MiddlewareResponse:
        client_id = self._get_client_id(client_cert)

        self._validate_accept_type(accept_type)

        return MiddlewareResponse(
            client_id=client_id,
            message="Client authenticated successfully"
        )

    # -------------------------- Create or Update ARCs --------------------------
    async def create_or_update_arcs(self, data: str, client_cert: str | None, content_type: str | None, accept_type: str | None) -> CreateOrUpdateResponse:
        self._validate_content_type(content_type)
        self._validate_accept_type(accept_type)
        client_id = self._get_client_id(client_cert)

        result = await self._process_arcs(data, client_id)

        return CreateOrUpdateResponse(
            client_id=client_id,
            message="ARCs processed successfully",
            arcs=result,
        )

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
