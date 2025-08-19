import hashlib
import json
from enum import Enum
from datetime import datetime, timezone
from typing import List, Dict
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from arctrl.arc import ARC

app = FastAPI(title="FAIR Middleware API",
              description="API for managing ARC (Advanced Research Context) objects")


class ARCStatus(str, Enum):
    created = "created"
    updated = "updated"
    deleted = "deleted"

class ARCResponse(BaseModel):
    id: str
    status: ARCStatus
    updated_at: str


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal Server Error. Please contact support if the problem persists."
        },
    )

def get_client_id(client_cert: str | None) -> str:
    """Extract client ID from X509 certificate.
    
    Args:
        client_cert: PEM formatted certificate string
        
    Returns:
        str: Client ID from certificate CN
        
    Raises:
        HTTPException: If certificate is missing or invalid
    """
    if not client_cert:
        raise HTTPException(
            status_code=401,
            detail="Client certificate missing"
        )

    try:
        pem = client_cert.replace("\n", "\n")
        cert_obj = x509.load_pem_x509_certificate(pem.encode(), default_backend())
        value = cert_obj.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)[0].value
        return bytes(value).decode() if isinstance(value, (bytes, bytearray, memoryview)) else str(value)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid certificate format: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=400, 
            detail=f"Certificate parsing error: {str(e)}"
        )

@app.get("/v1/whoami")
async def whoami(request: Request) -> JSONResponse:
    client_cert = request.headers.get("X-Client-Cert")
    client_id = get_client_id(client_cert)

    accept = request.headers.get("accept", SUPPORTED_ACCEPT_TYPE)
    validate_accept_type(accept)
    
    return JSONResponse(
        content={
            "client_id": client_id,
            "message": "Client authenticated successfully"
        },
        status_code=200
    )

# Constants
SUPPORTED_CONTENT_TYPE = "application/ro-crate+json"
SUPPORTED_ACCEPT_TYPE = "application/json"

# Helper functions
def validate_content_type(content_type: str) -> None:
    if content_type != SUPPORTED_CONTENT_TYPE:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported Media Type. Supported types: '{SUPPORTED_CONTENT_TYPE}'."
        )

def validate_accept_type(accept: str) -> None:
    if accept not in [SUPPORTED_ACCEPT_TYPE, "*/*"]:
        raise HTTPException(
            status_code=406,
            detail=f"Unsupported Response Type. Supported types: '{SUPPORTED_ACCEPT_TYPE}'."
        )

def parse_rocrate_json(raw_data: str) -> List[Dict]:
    try:
        crates = json.loads(raw_data)
        if not isinstance(crates, list):
            raise HTTPException(
                status_code=400,
                detail="Expected a JSON array of RO-Crates."
            )
        return crates
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid RO-Crate JSON: {str(e)}"
        )

def create_arc_id(identifier: str, client_id: str) -> str:
    input_str = f"{identifier}:{client_id}"
    arc_id = hashlib.sha256(input_str.encode("utf-8")).hexdigest()
    return arc_id

def create_arc_from_rocrate(crate: Dict, client_id: str) -> ARCResponse:
    try:
        crate_json = json.dumps(crate)
        arc = ARC.from_rocrate_json_string(crate_json)
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail=f"Error processing RO-Crate JSON: {str(e)}"
        )

    identifier = getattr(arc.ISA, "Identifier", None)
    if not identifier:
        raise HTTPException(
            status_code=400,
            detail="RO-Crate JSON must contain an 'Identifier' in the ISA object."
        )

    exists = False  # TODO: Check if ARC already exists
    status = ARCStatus.updated if exists else ARCStatus.created
    
    return ARCResponse(
        id=create_arc_id(identifier, client_id),
        status=status,
        updated_at=datetime.now(timezone.utc).isoformat() + "Z",
    )

async def process_arcs(raw_data: str, client_id: str) -> List[ARCResponse]:
    crates = parse_rocrate_json(raw_data)
    result = []
    
    for crate in crates:
        arc_response = create_arc_from_rocrate(crate, client_id)
        result.append(arc_response)
        # TODO: persist ARC to database or file system
    
    return result

# API Endpoint
@app.post("/v1/arcs")
async def create_or_update_arcs(request: Request) -> JSONResponse:
    content_type = request.headers.get("content-type", SUPPORTED_CONTENT_TYPE)
    accept = request.headers.get("accept", SUPPORTED_ACCEPT_TYPE)
    client_cert = request.headers.get("X-Client-Cert")

    validate_content_type(content_type)
    validate_accept_type(accept)
    client_id = get_client_id(client_cert)

    raw_data = (await request.body()).decode("utf-8")
    result = await process_arcs(raw_data, client_id)
    
    status_code = 201 if any(r.status == ARCStatus.created for r in result) else 200
    headers = {"Location": f"/v1/arcs/{result[0].id}" if result else ""}
    
    return JSONResponse(
        content=[r.model_dump() for r in result],
        status_code=status_code,
        headers=headers,
        media_type=SUPPORTED_ACCEPT_TYPE
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
