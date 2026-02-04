"""Client for the FAIRagro Middleware API."""

import asyncio
import json
import logging
import ssl
from typing import TYPE_CHECKING, Any, cast

import httpx
from pydantic import BaseModel, ValidationError

from middleware.shared.api_models.models import (
    ArcOperationResult,
    CreateOrUpdateArcRequest,
    CreateOrUpdateArcResponse,
    GetTaskStatusResponseV2,
    TaskStatus,
)

from .config import Config

if TYPE_CHECKING:
    from arctrl import ARC  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)


class ApiClientError(Exception):
    """Base exception for ApiClient errors."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        """Initialize with message and optional status code."""
        super().__init__(message)
        self.status_code = status_code


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
            path = path.lstrip("/")
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
            raise ApiClientError(error_msg, status_code=e.response.status_code) from e
        except httpx.RequestError as e:
            error_msg = f"Request error: {str(e)}"
            logger.error(error_msg)
            raise ApiClientError(error_msg) from e

    async def _get(self, path: str) -> Any:
        """Send a GET request to the API.

        Args:
            path (str): API endpoint path.

        Returns:
            Any: JSON response data.

        Raises:
            ApiClientError: If the request fails.
        """
        client = self._get_client()
        try:
            path = path.lstrip("/")
            logger.debug("Sending GET request to %s", path)
            resp = await client.get(path)
            resp.raise_for_status()
            logger.debug("GET request successful, status code: %s", resp.status_code)
            return resp.json()
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP error {e.response.status_code}: {e.response.text}"
            logger.error(error_msg)
            raise ApiClientError(error_msg, status_code=e.response.status_code) from e
        except httpx.RequestError as e:
            error_msg = f"Request error: {str(e)}"
            logger.error(error_msg)
            raise ApiClientError(error_msg) from e

    def _serialize_arc(self, arc: "ARC | dict[str, Any]") -> dict[str, Any]:
        """Serialize ARC to RO-Crate JSON dict."""
        if isinstance(arc, dict):
            return arc
        return cast(dict[str, Any], json.loads(arc.ToROCrateJsonString()))

    async def create_or_update_arc(
        self,
        rdi: str,
        arc: "ARC | dict[str, Any]",
    ) -> ArcOperationResult:
        """Create or update a single ARC in the FAIRagro Middleware API.

        Args:
            rdi: The RDI identifier.
            arc: ARC object or already serialized ARC (as dict).

        Returns:
            The response containing the result of the operation.

        Raises:
            ApiClientError: If the request fails.
        """
        logger.info("Creating/updating ARC for RDI: %s", rdi)
        serialized_arc = self._serialize_arc(arc)

        # Prepare and submit request
        request = CreateOrUpdateArcRequest(rdi=rdi, arc=serialized_arc)
        response_data = await self._post("v2/arcs", request)
        try:
            submission = CreateOrUpdateArcResponse.model_validate(response_data)
        except ValidationError as e:
            raise ApiClientError(f"Invalid response from API during submission: {str(e)}") from e

        logger.info("Task submitted, ID: %s. Polling for results...", submission.task_id)

        # Poll for results
        return await self._poll_for_result(submission.task_id)

    async def _poll_for_result(self, task_id: str) -> ArcOperationResult:
        """Poll the API for the result of a background task.

        Args:
            task_id: The ID of the task to poll.

        Returns:
            The result of the operation.

        Raises:
            ApiClientError: If the task fails or times out.
        """
        delay = 1.0  # Start with 1 second delay
        while True:
            await asyncio.sleep(delay)
            status_data = await self._get(f"v2/tasks/{task_id}")
            try:
                status_response = GetTaskStatusResponseV2.model_validate(status_data)
            except ValidationError as e:
                raise ApiClientError(f"Invalid response from API during polling: {str(e)}") from e

            logger.debug("Task %s status: %s (next poll in %.1fs)", task_id, status_response.status, delay)

            if status_response.status == TaskStatus.SUCCESS:
                if status_response.result is None:
                    raise ApiClientError("Task succeeded but no result was returned")
                return status_response.result

            if status_response.status in (TaskStatus.FAILURE, TaskStatus.REVOKED):
                error_msg = status_response.message or "Unknown error"
                raise ApiClientError(f"Task {status_response.status.value}: {error_msg}")

            # Increase delay with exponential backoff (max 30s)
            delay = min(delay * 1.5, 30.0)

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
