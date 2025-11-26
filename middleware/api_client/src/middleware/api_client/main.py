"""Client for the FAIRagro Middleware API."""

from typing import Any

from httpx import AsyncClient
from pydantic import BaseModel

from middleware.shared.api_models.models import (
    CreateOrUpdateArcsRequest,
    CreateOrUpdateArcsResponse,
    LivenessResponse,
    WhoamiResponse,
)


class MiddlewareClient:
    """Client for the FAIRagro Middleware API."""

    """Client for the FAIRagro Middleware API."""

    def __init__(
        self,
        base_url: str,
        client_cert: str,
        client_verify: str = "SUCCESS",
        timeout: float = 10.0,
    ) -> None:
        """
        Initialize the MiddlewareClient.

        Args:
            base_url (str): The base URL of the FAIRagro Middleware API.
            client_cert (str): The client certificate for authentication.
            client_verify (str, optional): SSL client verification status. Defaults to "SUCCESS".
            timeout (float, optional): Timeout for HTTP requests in seconds. Defaults to 10.0.
        """
        self.base_url = base_url

        self._client = AsyncClient(
            base_url=base_url,
            timeout=timeout,
            headers={
                "ssl-client-cert": client_cert,
                "ssl-client-verify": client_verify,
                "accept": "application/json",
            },
        )

    async def _get(self, path: str) -> Any:
        resp = await self._client.get(path)
        resp.raise_for_status()
        return resp.json()

    async def _post(
        self,
        path: str,
        body: BaseModel,
    ) -> Any:
        resp = await self._client.post(
            path,
            json=body.model_dump(),
            headers={"content-type": "application/json"},
        )
        resp.raise_for_status()
        return resp.json()

    #
    # --------- Public API ----------
    #

    async def whoami(self) -> WhoamiResponse:
        """
        Retrieve information about the authenticated user from the FAIRagro Middleware API.

        Returns:
            WhoamiResponse: The response containing user information.
        """
        result = await self._get("/v1/whoami")
        return WhoamiResponse.model_validate(result)

    async def liveness(self) -> LivenessResponse:
        """
        Check the liveness of the FAIRagro Middleware API.

        Returns:
            LivenessResponse: The response indicating the API's liveness status.
        """
        result = await self._get("/v1/liveness")
        return LivenessResponse.model_validate(result)

    async def create_or_update_arcs(
        self,
        request: CreateOrUpdateArcsRequest,
    ) -> CreateOrUpdateArcsResponse:
        """
        Create or update ARCs in the FAIRagro Middleware API.

        Args:
            request (CreateOrUpdateArcsRequest): The request payload containing ARC data.

        Returns:
            CreateOrUpdateArcsResponse: The response containing the result of the operation.
        """
        result = await self._post("/v1/arcs", request)
        return CreateOrUpdateArcsResponse.model_validate(result)

    #
    # --------- Cleanup ----------
    #
    async def aclose(self) -> None:
        """
        Close the underlying HTTP client connection.

        This should be called to properly clean up resources when the client is no longer needed.
        """
        await self._client.aclose()
