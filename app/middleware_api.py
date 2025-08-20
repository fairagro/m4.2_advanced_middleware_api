from typing import Any
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.params import Depends

from app.arc_store_gitlab_api import ARCStoreGitlabAPI
from app.middleware_service import ClientCertMissingError, ClientCertParsingError, InvalidAcceptTypeError, InvalidContentTypeError, InvalidJsonSemanticError, InvalidJsonSyntaxError, MiddlewareService


app = FastAPI(title="FAIR Middleware API",
              description="API for managing ARC (Advanced Research Context) objects")

store = ARCStoreGitlabAPI("http://gitlab", "token", 1)
service = MiddlewareService(store)


def get_service() -> MiddlewareService:
    return service


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal Server Error. Please contact support if the problem persists."
        },
    )


@app.get("/v1/whoami")
async def whoami(request: Request, service: Any = Depends(get_service)) -> JSONResponse:
    client_cert = request.headers.get("X-Client-Cert")
    accept_type = request.headers.get("accept")
    try:
        result = await service.whoami(request, client_cert, accept_type)
        return JSONResponse(
            content=result.model_dump(),
            status_code=200
        )
    except ClientCertMissingError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except ClientCertParsingError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except InvalidAcceptTypeError as e:
        raise HTTPException(status_code=406, detail=str(e))


@app.post("/v1/arcs")
async def create_or_update_arcs(request: Request, service: Any = Depends(get_service)) -> JSONResponse:
    client_cert = request.headers.get("X-Client-Cert")
    content_type = request.headers.get("content-type")
    accept_type = request.headers.get("accept")
    data = (await request.body()).decode("utf-8")
    try:
        result = await service.create_or_update_arcs(
            data, client_cert, content_type, accept_type
        )
        return JSONResponse(
            content=result.model_dump(),
            status_code=201 if any(a.status == "created" for a in result.arcs) else 200,
            headers={"Location": f"/v1/arcs/{result.arcs[0].id}" if result.arcs else ""}
        )
    except ClientCertMissingError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except ClientCertParsingError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except InvalidAcceptTypeError as e:
        raise HTTPException(status_code=406, detail=str(e))
    except InvalidContentTypeError as e:
        raise HTTPException(status_code=415, detail=str(e))
    except InvalidJsonSyntaxError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except InvalidJsonSemanticError as e:
        raise HTTPException(status_code=422, detail=str(e))

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
