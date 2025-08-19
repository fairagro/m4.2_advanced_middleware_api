import json
from enum import Enum
from datetime import datetime, timezone
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from typing import List
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

async def create_or_update_arcs_from_rocrate(raw_data: str) -> List[ARCResponse]:
    try:
        crates: List[dict] = json.loads(raw_data)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid RO-Crate JSON: {str(e)}"
        )
    if not isinstance(crates, list):
        raise HTTPException(
            status_code=400,
            detail="Expected a JSON array of RO-Crates."
        )
    
    result: List[ARCResponse] = []
    for crate in crates:
        try:
            crate_json: str = json.dumps(crate)
            arc: ARC = ARC.from_rocrate_json_string(crate_json)
        except Exception as e:
            raise HTTPException(
                status_code=422,
                detail=f"Error processing RO-Crate JSON: {str(e)}"
            )
        exists = False  # TODO: Check if ARC already exists in the database or file system
        status = ARCStatus.updated if exists else ARCStatus.created
        id = getattr(arc.ISA, "Identifier", None)
        if not id:
            raise HTTPException(
                status_code=400,
                detail="RO-Crate JSON must contain an 'Identifier' in the ISA object."
            )
        result.append(ARCResponse(
            id=id,  # TODO: think about unique ARC IDs
            status=status,
            updated_at=datetime.now(timezone.utc).isoformat() + "Z",
        ))
        #TODO: perist ARC to database or file system
    return result

# -------------------------
# CREATE ARC(S)
# -------------------------
@app.post("/v1/arcs")
async def create_or_update_arcs(request: Request) -> JSONResponse:
    content_type: str = request.headers.get("content-type", "application/ro-crate+json")
    accept: str = request.headers.get("accept", "application/json")
    
    raw_bytes: bytes = await request.body()
    raw_data: str = raw_bytes.decode("utf-8")

    if content_type == "application/ro-crate+json":
        result: list = await create_or_update_arcs_from_rocrate(raw_data)
    else:
        raise HTTPException(
            status_code=415,
            detail="Unsupported Media Type. Supported types: 'application/ro-crate+json'."
        )
    
    if accept == "application/json" or accept == "*/*":
        status_code = 201 if any(r.status==ARCStatus.created for r in result) else 200
        # set a Location header to be RESTful
        headers = {
            "Location": f"/v1/arcs/{result[0].id}" if result else ""
        }
        return JSONResponse(
            content=[r.dict() for r in result],
            status_code=status_code,
            headers=headers,
            media_type="application/json"
        )
    else:
        raise HTTPException(
            status_code=406,
            detail="Unsupprted Response Type. Supported types: 'application/json'."
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
