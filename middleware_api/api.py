import os
from pathlib import Path
from typing import Annotated
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.datastructures import Headers
from fastapi.responses import JSONResponse
from cryptography import x509
from cryptography.hazmat.backends import default_backend

from .config import Config
from .arc_store.gitlab_api import GitlabApi
from .business_logic import (
    InvalidJsonSemanticError,
    InvalidJsonSyntaxError,
    BusinessLogic
)


class Api:

    # Constants
    SUPPORTED_CONTENT_TYPE = "application/ro-crate+json"
    SUPPORTED_ACCEPT_TYPE = "application/json"
    CONFIG_ENV_VAR_NAME = "MIDDLEWARE_API_CONFIG"

    def __init__(self, config_path: Path | None = None):
        config_path_from_env =  os.environ.get(Api.CONFIG_ENV_VAR_NAME)
        if config_path_from_env:
            config_path = Path(config_path_from_env)
        if config_path is None:
            config_path = Path("./config.yaml")
        self._config = Config.from_yaml_file(config_path)

        self._store = GitlabApi(self._config.gitlab_api)
        self._service = BusinessLogic(self._store)
        self._app = FastAPI(
            title="FAIR Middleware API",
            description="API for managing ARC (Advanced Research Context) objects"
        )
        self._setup_routes()
        self._setup_exception_handlers()

    @property
    def app(self) -> FastAPI:
        return self._app

    def get_service(self) -> BusinessLogic:
        return self._service

    def _get_client_id(self, headers: Headers) -> str:
        client_cert = headers.get("X-Client-Cert")
        if not client_cert:
            msg = "Client certificate missing"
            raise HTTPException(status_code=401, detail=msg)

        try:
            pem = client_cert.replace("\n", "\n")
            cert_obj = x509.load_pem_x509_certificate(
                pem.encode(), default_backend())
            value = cert_obj.subject.get_attributes_for_oid(
                x509.NameOID.COMMON_NAME)[0].value
            return bytes(value).decode() if isinstance(value, (bytes, bytearray, memoryview)) else str(value)
        except ValueError as e:
            raise HTTPException(
                status_code=400, detail=f"Invalid certificate format: {str(e)}") from e
        except Exception as e:
            raise HTTPException(
                status_code=400, detail=f"Certificate parsing error: {str(e)}") from e

    def _validate_content_type(self, headers: Headers) -> None:
        content_type = headers.get("content-type")
        if not content_type:
            msg = f"Content-Type header is missing. Expected '{self.SUPPORTED_CONTENT_TYPE}'."
            raise HTTPException(status_code=415, detail=msg)
        if content_type != self.SUPPORTED_CONTENT_TYPE:
            msg = f"Unsupported Media Type. Supported types: '{self.SUPPORTED_CONTENT_TYPE}'."
            raise HTTPException(status_code=415, detail=msg)

    def _validate_accept_type(self, headers: Headers) -> None:
        accept = headers.get("accept")
        if accept not in [self.SUPPORTED_ACCEPT_TYPE, "*/*"]:
            msg = f"Unsupported Response Type. Supported types: '{self.SUPPORTED_ACCEPT_TYPE}'."
            raise HTTPException(status_code=406, detail=msg)

    def _setup_exception_handlers(self):

        @self._app.exception_handler(Exception)
        async def unhandled_exception_handler(_request: Request, _exc: Exception):
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal Server Error. Please contact support if the problem persists."},
            )

    def _setup_routes(self):

        @self._app.get("/v1/whoami")
        async def whoami(
            request: Request,
            service: Annotated[BusinessLogic, Depends(self.get_service)]
        ) -> JSONResponse:
            client_id = self._get_client_id(request.headers)
            self._validate_accept_type(request.headers)
            result = await service.whoami(client_id)
            return JSONResponse(content=result.model_dump())

        @self._app.get("/v1/liveness")
        async def liveness(request: Request) -> JSONResponse:
            self._validate_accept_type(request.headers)
            return JSONResponse(content={"message": "living"})

        @self._app.post("/v1/arcs")
        async def create_or_update_arcs(
            request: Request,
            service: Annotated[BusinessLogic, Depends(self.get_service)]
        ) -> JSONResponse:
            client_id = self._get_client_id(request.headers)
            self._validate_accept_type(request.headers)
            self._validate_content_type(request.headers)
            data = (await request.body()).decode("utf-8")
            try:
                result = await service.create_or_update_arcs(data, client_id)
                return JSONResponse(
                    content=result.model_dump(),
                    status_code=201 if any(a.status == "created" for a in result.arcs) else 200,
                    headers={"Location": f"/v1/arcs/{result.arcs[0].id}" if result.arcs else ""}
                )
            except InvalidJsonSyntaxError as e:
                raise HTTPException(status_code=400, detail=str(e)) from e
            except InvalidJsonSemanticError as e:
                raise HTTPException(status_code=422, detail=str(e)) from e


middleware_api = Api()
app = middleware_api.app


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
