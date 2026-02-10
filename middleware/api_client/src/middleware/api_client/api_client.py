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

    async def _request_with_retries(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> Any:
        """Send an HTTP request to the API with retries.

        Args:
            method (str): HTTP method (GET, POST, etc.).
            path (str): API endpoint path.
            **kwargs: Additional arguments passed to httpx client.

        Returns:
            Any: JSON response data.

        Raises:
            ApiClientError: If the request fails after all retries.
        """
        client = self._get_client()
        path = path.lstrip("/")
        method = method.upper()

        for attempt in range(self._config.max_retries + 1):
            if attempt > 0:
                delay = self._config.retry_backoff_factor * (2 ** (attempt - 1))
                logger.info(
                    "Retrying %s %s in %.1fs (attempt %d/%d)", method, path, delay, attempt, self._config.max_retries
                )
                await asyncio.sleep(delay)

            try:
                logger.debug("Sending %s request to %s (attempt %d)", method, path, attempt + 1)
                resp = await client.request(method, path, **kwargs)

                # Retry on 502, 503, 504
                if resp.status_code in (502, 503, 504) and attempt < self._config.max_retries:
                    logger.warning("Transient HTTP error %d from server", resp.status_code)
                    continue

                resp.raise_for_status()
                logger.debug("%s request successful, status code: %s", method, resp.status_code)
                return resp.json()
            except httpx.HTTPStatusError as e:
                # If we get here and it's not a retryable error, or we're out of retries
                if e.response.status_code in (502, 503, 504) and attempt < self._config.max_retries:
                    continue

                if e.response.status_code in (502, 503, 504):
                    error_msg = (
                        f"Request failed after {self._config.max_retries} retries: HTTP {e.response.status_code}"
                    )
                else:
                    error_msg = f"HTTP error {e.response.status_code}: {e.response.text}"

                logger.error(error_msg)
                raise ApiClientError(error_msg, status_code=e.response.status_code) from e
            except httpx.RequestError as e:
                if attempt < self._config.max_retries:
                    logger.warning("Request error: %s. Retrying...", str(e))
                    continue
                error_msg = f"Request failed after {self._config.max_retries} retries: {str(e)}"
                logger.error(error_msg)
                raise ApiClientError(error_msg) from e

        raise ApiClientError("Request failed for an unknown reason")

    async def _post(
        self,
        path: str,
        body: BaseModel,
    ) -> Any:
        """Send a POST request to the API with retries.

        Args:
            path (str): API endpoint path.
            body (BaseModel): Request body as Pydantic model.

        Returns:
            Any: JSON response data.

        Raises:
            ApiClientError: If the request fails after all retries.
        """
        return await self._request_with_retries(
            "POST",
            path,
            json=body.model_dump(),
            headers={"content-type": "application/json"},
        )

    async def _get(self, path: str) -> Any:
        """Send a GET request to the API with retries.

        Args:
            path (str): API endpoint path.

        Returns:
            Any: JSON response data.

        Raises:
            ApiClientError: If the request fails after all retries.
        """
        return await self._request_with_retries("GET", path)

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
        delay = self._config.polling_initial_delay
        time_waited = 0.0
        timeout_seconds = self._config.polling_timeout * 60

        while time_waited < timeout_seconds:
            await asyncio.sleep(delay)
            time_waited += delay

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

            # Increase delay with exponential backoff
            delay = min(delay * self._config.polling_backoff_factor, self._config.polling_max_delay)

        raise ApiClientError(f"Polling for task {task_id} timed out after {self._config.polling_timeout} minutes.")

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
