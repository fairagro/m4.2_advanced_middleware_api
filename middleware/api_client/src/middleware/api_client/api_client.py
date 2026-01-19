"""Client for the FAIRagro Middleware API."""

import asyncio
import json
import logging
import ssl
from typing import TYPE_CHECKING, Any

import httpx
from pydantic import BaseModel

from middleware.shared.api_models.models import (
    CreateOrUpdateArcsRequest,
    CreateOrUpdateArcsResponse,
)

from .config import Config

if TYPE_CHECKING:
    from arctrl import ARC  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)


class ApiClientError(Exception):
    """Base exception for ApiClient errors."""


class ApiClient:
    """Client for the FAIRagro Middleware API.

    This client provides access to the Middleware API with certificate-based
    authentication (mTLS). It supports creating and updating ARCs.

    Example:
        ```python
        from pathlib import Path
        from middleware.api_client import Config, ApiClient

        # Load configuration from YAML file
        config = Config.from_yaml_file(Path("config.yaml"))

        # Create client instance
        async with ApiClient(config) as client:
            # Send request
            response = await client.create_or_update_arcs(
                rdi="my-rdi",
                arcs=[{"@context": "...", "@id": "...", ...}]
            )
            print(f"Created/Updated {len(response.arcs)} ARCs")
        ```
    """

    def __init__(self, config: Config) -> None:
        """Initialize the ApiClient.

        Args:
            config (Config): Configuration object containing API URL and certificate paths.

        Raises:
            ApiClientError: If certificate or key files don't exist.
        """
        self._config = config
        self._client: httpx.AsyncClient | None = None

        # Validate certificate files exist (if provided)
        cert_path = config.client_cert_path
        key_path = config.client_key_path

        if cert_path is not None and not cert_path.exists():
            raise ApiClientError(f"Client certificate not found: {cert_path}")
        if key_path is not None and not key_path.exists():
            raise ApiClientError(f"Client key not found: {key_path}")

        # Validate CA cert if provided
        ca_path = config.ca_cert_path
        if ca_path and not ca_path.exists():
            raise ApiClientError(f"CA certificate not found: {ca_path}")

        logger.debug(
            "ApiClient initialized with API URL: %s, cert: %s, key: %s",
            config.api_url,
            cert_path,
            key_path,
        )

    def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client instance.

        Returns:
            httpx.AsyncClient: Configured async HTTP client.
        """
        if self._client is None:
            # Prepare verify parameter
            if not self._config.verify_ssl:
                verify: bool | ssl.SSLContext = False
            elif self._config.ca_cert_path:
                # Create SSL context with CA certificate
                ctx = ssl.create_default_context(cafile=str(self._config.ca_cert_path))
                # Load client certificate chain for mTLS
                if self._config.client_cert_path and self._config.client_key_path:
                    ctx.load_cert_chain(
                        str(self._config.client_cert_path),
                        str(self._config.client_key_path),
                    )
                verify = ctx
            elif self._config.client_cert_path and self._config.client_key_path:
                # No CA cert, but load client certs if available
                ctx = ssl.create_default_context()
                ctx.load_cert_chain(
                    str(self._config.client_cert_path),
                    str(self._config.client_key_path),
                )
                verify = ctx
            else:
                verify = True

            self._client = httpx.AsyncClient(
                base_url=self._config.api_url,
                verify=verify,
                timeout=self._config.timeout,
                follow_redirects=self._config.follow_redirects,
                headers={
                    "accept": "application/json",
                },
            )
            logger.debug("Created new httpx.AsyncClient instance")

        return self._client

    async def _post(
        self,
        path: str,
        body: BaseModel,
    ) -> Any:
        """Send a POST request to the API.

        Args:
            path (str): API endpoint path.
            body (BaseModel): Request body as Pydantic model.

        Returns:
            Any: JSON response data.

        Raises:
            ApiClientError: If the request fails.
        """
        client = self._get_client()

        try:
            logger.debug("Sending POST request to %s", path)
            resp = await client.post(
                path,
                json=body.model_dump(),
                headers={"content-type": "application/json"},
            )
            resp.raise_for_status()
            logger.debug("POST request successful, status code: %s", resp.status_code)
            return resp.json()
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP error {e.response.status_code}: {e.response.text}"
            logger.error(error_msg)
            raise ApiClientError(error_msg) from e
        except httpx.RequestError as e:
            error_msg = f"Request error: {str(e)}"
            logger.error(error_msg)
            raise ApiClientError(error_msg) from e

    async def _get(self, path: str) -> Any:
        """Send a GET request to the API."""
        client = self._get_client()
        try:
            resp = await client.get(path)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            raise ApiClientError(f"GET request failed: {e}") from e

    async def create_or_update_arcs(
        self,
        rdi: str,
        arcs: list["ARC"],
    ) -> CreateOrUpdateArcsResponse:
        """Create or update ARCs in the FAIRagro Middleware API.

        Args:
            rdi (str): The RDI identifier.
            arcs (list[ARC]): List of ARC objects from arctrl library.

        Returns:
            CreateOrUpdateArcsResponse: The response containing the result of the operation.

        Raises:
            ApiClientError: If the request fails.
        """
        logger.info("Creating/updating %d ARCs for RDI: %s", len(arcs), rdi)

        # Serialize each ARC to RO-Crate JSON format
        serialized_arcs: list[dict[str, Any]] = []
        for arc in arcs:
            json_str = arc.ToROCrateJsonString()
            serialized_arcs.append(json.loads(json_str))

        request = CreateOrUpdateArcsRequest(rdi=rdi, arcs=serialized_arcs)
        logger.debug("Request payload: %s", json.dumps(request.model_dump(), indent=2))

        # 1. Submit task
        result = await self._post("/v1/arcs", request)

        task_id = result.get("task_id")
        if not task_id:
            raise ApiClientError("No task_id returned from API")

        logger.info("Task submitted, ID: %s. Polling for results...", task_id)

        # 2. Poll for results
        while True:
            await asyncio.sleep(1.0)  # Poll every second
            status_response = await self._get(f"/v1/tasks/{task_id}")
            status = status_response.get("status")

            if status == "SUCCESS":
                result_data = status_response.get("result")
                response = CreateOrUpdateArcsResponse.model_validate(result_data)
                logger.info(
                    "Successfully created/updated %d ARCs for RDI: %s",
                    len(response.arcs),
                    response.rdi,
                )
                return response

            if status == "FAILURE":
                error_msg = status_response.get("error", "Unknown error")
                raise ApiClientError(f"Task failed: {error_msg}")

            # continue polling if PENDING, STARTED, RETRY etc.

    async def aclose(self) -> None:
        """Close the underlying HTTP client connection.

        This should be called to properly clean up resources when the client
        is no longer needed.
        """
        if self._client is not None:
            logger.debug("Closing httpx.AsyncClient")
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "ApiClient":
        """Async context manager entry.

        Returns:
            ApiClient: This client instance.
        """
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit.

        Args:
            exc_type: Exception type if an error occurred.
            exc_val: Exception value if an error occurred.
            exc_tb: Exception traceback if an error occurred.
        """
        await self.aclose()
