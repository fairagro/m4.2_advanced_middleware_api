"""Client for the FAIRagro Middleware API (v3)."""

import asyncio
import json
import logging
import ssl
from http import HTTPStatus
from typing import TYPE_CHECKING, Any, cast

import httpx
from pydantic import BaseModel, ValidationError

from middleware.shared.api_models.v3.models import (
    ArcResponse,
    CreateArcRequest,
    CreateHarvestRequest,
    HarvestResponse,
    SubmitHarvestArcRequest,
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
    """Client for the FAIRagro Middleware API (v3).

    The v3 API is synchronous from the client's perspective: every call
    returns the final result immediately — no task polling required.
    GitLab synchronisation is triggered in the background by the server.

    Example::

        config = Config(api_url="https://api.example.com")
        async with ApiClient(config) as client:
            # Simple ARC submission
            arc_response = await client.create_or_update_arc("my-rdi", arc_dict)

            # Harvest-based batch submission
            harvest = await client.create_harvest("my-rdi", expected_datasets=42)
            for arc in arcs:
                await client.submit_arc_in_harvest(harvest.harvest_id, arc)
            await client.complete_harvest(harvest.harvest_id)
    """

    def __init__(self, config: Config) -> None:
        """Initialize the ApiClient.

        Args:
            config: Configuration object containing API URL and certificate paths.

        Raises:
            ApiClientError: If certificate or key files don't exist.
        """
        self._config = config
        self._client: httpx.AsyncClient | None = None

        cert_path = config.client_cert_path
        key_path = config.client_key_path
        ca_path = config.ca_cert_path

        if cert_path is not None and not cert_path.exists():
            raise ApiClientError(f"Client certificate not found: {cert_path}")
        if key_path is not None and not key_path.exists():
            raise ApiClientError(f"Client key not found: {key_path}")
        if ca_path is not None and not ca_path.exists():
            raise ApiClientError(f"CA certificate not found: {ca_path}")

        logger.debug(
            "ApiClient initialized with API URL: %s, cert: %s, key: %s",
            config.api_url,
            cert_path,
            key_path,
        )

    # ------------------------------------------------------------------
    # HTTP infrastructure
    # ------------------------------------------------------------------

    def _get_client(self) -> httpx.AsyncClient:
        """Return the shared httpx.AsyncClient, creating it on first call."""
        if self._client is None:
            if not self._config.verify_ssl:
                verify: bool | ssl.SSLContext = False
            elif self._config.ca_cert_path:
                ctx = ssl.create_default_context(cafile=str(self._config.ca_cert_path))
                if self._config.client_cert_path and self._config.client_key_path:
                    ctx.load_cert_chain(
                        str(self._config.client_cert_path),
                        str(self._config.client_key_path),
                    )
                verify = ctx
            elif self._config.client_cert_path and self._config.client_key_path:
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
                headers={"accept": "application/json"},
            )
            logger.debug("Created new httpx.AsyncClient instance")

        return self._client

    async def _request_with_retries(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> Any:
        """Send an HTTP request with retry logic for transient errors.

        Returns:
            Parsed JSON body for responses with content, or ``None`` for 204.

        Raises:
            ApiClientError: On permanent HTTP errors or exhausted retries.
        """
        client = self._get_client()
        path = path.lstrip("/")
        method = method.upper()

        _transient = {httpx.codes.BAD_GATEWAY, httpx.codes.SERVICE_UNAVAILABLE, httpx.codes.GATEWAY_TIMEOUT}

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

                # Retry on transient server-side errors before raising
                if resp.status_code in _transient and attempt < self._config.max_retries:
                    logger.warning("Transient HTTP error %d from server, will retry", resp.status_code)
                    continue

                resp.raise_for_status()
                logger.debug("%s %s succeeded with status %d", method, path, resp.status_code)

                if resp.status_code == HTTPStatus.NO_CONTENT:
                    return None
                return resp.json()

            except httpx.HTTPStatusError as e:
                if e.response.status_code in _transient and attempt < self._config.max_retries:
                    continue
                if e.response.status_code in _transient:
                    msg = f"Request failed after {self._config.max_retries} retries: HTTP {e.response.status_code}"
                else:
                    msg = f"HTTP error {e.response.status_code}: {e.response.text}"
                logger.error(msg)
                raise ApiClientError(msg, status_code=e.response.status_code) from e

            except httpx.RequestError as e:
                if attempt < self._config.max_retries:
                    logger.warning("Request error: %s. Retrying...", e)
                    continue
                msg = f"Request failed after {self._config.max_retries} retries: {e}"
                logger.error(msg)
                raise ApiClientError(msg) from e

        raise ApiClientError("Request failed for an unknown reason")  # pragma: no cover

    async def _post(self, path: str, body: BaseModel) -> Any:
        """POST with a Pydantic request body."""
        return await self._request_with_retries(
            "POST",
            path,
            content=body.model_dump_json(),
            headers={"content-type": "application/json"},
        )

    async def _post_empty(self, path: str) -> Any:
        """POST with an empty body (e.g. trigger endpoints)."""
        return await self._request_with_retries(
            "POST",
            path,
            headers={"content-type": "application/json"},
        )

    async def _get(self, path: str) -> Any:
        """GET request."""
        return await self._request_with_retries("GET", path)

    async def _delete(self, path: str) -> None:
        """DELETE request, ignoring a 204 No Content response."""
        await self._request_with_retries("DELETE", path)

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    @classmethod
    def _serialize_arc(cls, arc: "ARC | dict[str, Any]") -> dict[str, Any]:
        """Serialize an ARC object to a plain RO-Crate JSON dict."""
        if isinstance(arc, dict):
            return arc
        return cast(dict[str, Any], json.loads(arc.ToROCrateJsonString()))

    @classmethod
    def _parse_arc_response(cls, data: Any) -> ArcResponse:
        try:
            return ArcResponse.model_validate(data)
        except ValidationError as e:
            raise ApiClientError(f"Invalid ARC response from API: {e}") from e

    @classmethod
    def _parse_harvest_response(cls, data: Any) -> HarvestResponse:
        try:
            return HarvestResponse.model_validate(data)
        except ValidationError as e:
            raise ApiClientError(f"Invalid harvest response from API: {e}") from e

    # ------------------------------------------------------------------
    # ARC endpoints (v3)
    # ------------------------------------------------------------------

    async def create_or_update_arc(
        self,
        rdi: str,
        arc: "ARC | dict[str, Any]",
    ) -> ArcResponse:
        """Create or update an ARC.

        Uses ``POST /v3/arcs``.  The server stores the ARC synchronously and
        triggers the GitLab synchronisation in the background — no polling
        required.

        Args:
            rdi: RDI identifier.
            arc: ARC object or a pre-serialised RO-Crate JSON dict.

        Returns:
            :class:`ArcResponse` with the result of the operation.
        """
        logger.info("Creating/updating ARC for RDI: %s", rdi)
        serialized = self._serialize_arc(arc)
        request = CreateArcRequest(rdi=rdi, arc=serialized)
        data = await self._post("v3/arcs", request)
        return self._parse_arc_response(data)

    # ------------------------------------------------------------------
    # Harvest endpoints (v3)
    # ------------------------------------------------------------------

    async def create_harvest(
        self,
        rdi: str,
        expected_datasets: int | None = None,
    ) -> HarvestResponse:
        """Start a new harvest run.

        Uses ``POST /v3/harvests``.

        Args:
            rdi: RDI identifier.
            expected_datasets: Optional hint about how many datasets will be submitted.

        Returns:
            :class:`HarvestResponse` with the newly created harvest.
        """
        request = CreateHarvestRequest(rdi=rdi, expected_datasets=expected_datasets)
        data = await self._post("v3/harvests", request)
        return self._parse_harvest_response(data)

    async def list_harvests(self, rdi: str | None = None) -> list[HarvestResponse]:
        """List harvest runs.

        Uses ``GET /v3/harvests``.

        Args:
            rdi: Optional RDI filter.

        Returns:
            List of :class:`HarvestResponse` objects.
        """
        path = "v3/harvests"
        if rdi:
            path += f"?rdi={rdi}"
        data = await self._get(path)
        try:
            return [HarvestResponse.model_validate(d) for d in data]
        except ValidationError as e:
            raise ApiClientError(f"Invalid harvest list response from API: {e}") from e

    async def get_harvest(self, harvest_id: str) -> HarvestResponse:
        """Get a single harvest run by ID.

        Uses ``GET /v3/harvests/{harvest_id}``.

        Args:
            harvest_id: Harvest identifier.

        Returns:
            :class:`HarvestResponse`.
        """
        data = await self._get(f"v3/harvests/{harvest_id}")
        return self._parse_harvest_response(data)

    async def complete_harvest(self, harvest_id: str) -> HarvestResponse:
        """Mark a harvest run as completed.

        Uses ``POST /v3/harvests/{harvest_id}/complete``.

        Args:
            harvest_id: Harvest identifier.

        Returns:
            Updated :class:`HarvestResponse`.
        """
        data = await self._post_empty(f"v3/harvests/{harvest_id}/complete")
        return self._parse_harvest_response(data)

    async def cancel_harvest(self, harvest_id: str) -> None:
        """Cancel (delete) a harvest run.

        Uses ``DELETE /v3/harvests/{harvest_id}``.

        Args:
            harvest_id: Harvest identifier.
        """
        await self._delete(f"v3/harvests/{harvest_id}")

    async def submit_arc_in_harvest(
        self,
        harvest_id: str,
        arc: "ARC | dict[str, Any]",
    ) -> ArcResponse:
        """Submit an ARC within an active harvest run.

        Uses ``POST /v3/harvests/{harvest_id}/arcs``.  The RDI is resolved
        automatically from the harvest run on the server side.

        Args:
            harvest_id: Harvest identifier.
            arc: ARC object or a pre-serialised RO-Crate JSON dict.

        Returns:
            :class:`ArcResponse` with the result of the operation.
        """
        serialized = self._serialize_arc(arc)
        request = SubmitHarvestArcRequest(arc=serialized)
        data = await self._post(f"v3/harvests/{harvest_id}/arcs", request)
        return self._parse_arc_response(data)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def aclose(self) -> None:
        """Close the underlying HTTP client and release connections."""
        if self._client is not None:
            logger.debug("Closing httpx.AsyncClient")
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "ApiClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit — closes the client."""
        await self.aclose()
