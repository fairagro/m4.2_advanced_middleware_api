"""Client for the FAIRagro Middleware API (v3)."""

import asyncio
import json
import logging
import ssl
import threading
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager
from http import HTTPStatus
from typing import TYPE_CHECKING, Any, cast

import httpx
from pydantic import BaseModel, ValidationError

from middleware.shared.api_models.v3.models import (
    CreateArcRequest,
    CreateHarvestRequest,
    SubmitHarvestArcRequest,
)

from .config import Config
from .models import ArcResult, HarvestResult

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

    _IDEMPOTENT_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "DELETE"})
    _HTTP_ERROR_BODY_MAX_CHARS = 500
    _global_request_limiter: asyncio.Semaphore | None = None
    _global_max_concurrency: int | None = None
    _global_in_flight_requests: int = 0
    _global_state_lock = threading.Lock()

    @classmethod
    def _configure_global_request_limiter(cls, max_concurrency: int) -> None:
        """Configure the package-wide request concurrency limiter."""
        with cls._global_state_lock:
            if (
                cls._global_max_concurrency is not None
                and cls._global_max_concurrency != max_concurrency
                and cls._global_in_flight_requests > 0
            ):
                msg = (
                    "Cannot change ApiClient max_concurrency while requests are in flight. "
                    "Please reuse one max_concurrency value per process or wait for ongoing requests to finish."
                )
                raise ApiClientError(msg)

            if cls._global_request_limiter is None or cls._global_max_concurrency != max_concurrency:
                cls._global_request_limiter = asyncio.Semaphore(max_concurrency)
                cls._global_max_concurrency = max_concurrency

    @classmethod
    @asynccontextmanager
    async def _acquire_request_slot(cls) -> AsyncGenerator[None, None]:
        """Acquire one slot from the package-wide request limiter."""
        limiter = cls._global_request_limiter
        if limiter is None:
            msg = "ApiClient request limiter is not configured"
            raise ApiClientError(msg)

        await limiter.acquire()
        with cls._global_state_lock:
            cls._global_in_flight_requests += 1

        try:
            yield
        finally:
            with cls._global_state_lock:
                cls._global_in_flight_requests -= 1
            limiter.release()

    @classmethod
    def _should_retry_http_status(cls, method: str, status_code: int) -> bool:
        """Return whether a response status is retryable for a method."""
        transient = {httpx.codes.BAD_GATEWAY, httpx.codes.SERVICE_UNAVAILABLE, httpx.codes.GATEWAY_TIMEOUT}
        return method in cls._IDEMPOTENT_METHODS and status_code in transient

    @classmethod
    def _should_retry_request_error(cls, method: str, error: httpx.RequestError) -> bool:
        """Return whether a request error is retryable for a method."""
        if method not in cls._IDEMPOTENT_METHODS:
            return False
        return not isinstance(error, httpx.TimeoutException)

    @classmethod
    def _should_retry_failure(
        cls,
        method: str,
        *,
        status_code: int | None = None,
        request_error: httpx.RequestError | None = None,
    ) -> bool:
        """Return whether an HTTP failure is retryable for a request method."""
        if status_code is not None:
            return cls._should_retry_http_status(method, status_code)
        if request_error is not None:
            return cls._should_retry_request_error(method, request_error)
        return False

    @classmethod
    def _build_failure_error_message(
        cls,
        failure: httpx.HTTPStatusError | httpx.RequestError,
        *,
        retryable: bool,
        max_retries: int,
    ) -> tuple[str, int | None]:
        """Return normalized error message and optional status code for a request failure."""
        if isinstance(failure, httpx.HTTPStatusError):
            status_code = failure.response.status_code
            if retryable:
                return f"Request failed after {max_retries} retries: HTTP {status_code}", status_code
            return cls._format_http_error_message(status_code, failure.response.text), status_code

        if retryable:
            return f"Request failed after {max_retries} retries: {failure}", None
        return f"Request failed: {failure}", None

    @classmethod
    def _should_retry_or_raise_failure(
        cls,
        failure: httpx.HTTPStatusError | httpx.RequestError,
        *,
        method: str,
        attempt: int,
        max_retries: int,
    ) -> bool:
        """Return True to retry; otherwise raise a normalized ApiClientError."""
        status_code = failure.response.status_code if isinstance(failure, httpx.HTTPStatusError) else None
        request_error = failure if isinstance(failure, httpx.RequestError) else None

        should_retry = cls._should_retry_failure(
            method,
            status_code=status_code,
            request_error=request_error,
        )

        if should_retry and attempt < max_retries:
            if isinstance(failure, httpx.HTTPStatusError):
                logger.warning("Transient HTTP error %d from server, will retry", failure.response.status_code)
            else:
                logger.warning("Request error: %s. Retrying...", failure)
            return True

        msg, normalized_status_code = cls._build_failure_error_message(
            failure,
            retryable=should_retry,
            max_retries=max_retries,
        )
        logger.error(msg)
        raise ApiClientError(msg, status_code=normalized_status_code) from failure

    @classmethod
    def _format_http_error_message(cls, status_code: int, response_text: str) -> str:
        """Build a safe and concise HTTP error message."""
        response_excerpt = " ".join(response_text.splitlines()).strip()
        if len(response_excerpt) > cls._HTTP_ERROR_BODY_MAX_CHARS:
            response_excerpt = response_excerpt[: cls._HTTP_ERROR_BODY_MAX_CHARS] + "..."
        return f"HTTP error {status_code}: {response_excerpt}"

    @classmethod
    def _parse_json_response(cls, resp: httpx.Response, method: str, path: str) -> Any:
        """Parse and return JSON response body with normalized client errors."""
        if resp.status_code == HTTPStatus.NO_CONTENT:
            return None
        try:
            return resp.json()
        except ValueError as e:
            msg = f"Invalid JSON response from API for {method} {path}"
            logger.error(msg)
            raise ApiClientError(msg, status_code=resp.status_code) from e

    @classmethod
    def _is_catastrophic_harvest_error(cls, error: Exception) -> bool:
        """Return whether a harvest submission error should abort the whole harvest."""
        if not isinstance(error, ApiClientError):
            return True

        status_code = error.status_code
        if status_code is None:
            return True

        return (
            status_code
            in {
                HTTPStatus.UNAUTHORIZED,
                HTTPStatus.FORBIDDEN,
                HTTPStatus.NOT_FOUND,
                HTTPStatus.CONFLICT,
            }
            or status_code >= HTTPStatus.INTERNAL_SERVER_ERROR
        )

    async def _cancel_harvest_safely(self, rdi: str, harvest_id: str) -> None:
        """Try cancelling a harvest and suppress cancellation failures."""
        try:
            await self.cancel_harvest(harvest_id)
        except ApiClientError:
            logger.warning("[%s] Failed to cancel harvest %s", rdi, harvest_id)

    @classmethod
    async def _cancel_pending_arc_tasks(cls, pending_tasks: set[asyncio.Task[None]]) -> None:
        """Cancel and await remaining ARC submission tasks."""
        for pending_task in pending_tasks:
            pending_task.cancel()
        await asyncio.gather(*pending_tasks, return_exceptions=True)

    def _process_completed_arc_tasks(
        self,
        harvest_id: str,
        done_tasks: set[asyncio.Task[None]],
    ) -> tuple[int, Exception | None]:
        """Return (failed_count, catastrophic_error) for completed submission tasks."""
        failed_submissions = 0

        for done_task in done_tasks:
            try:
                done_task.result()
            except Exception as e:  # noqa: BLE001
                if self._is_catastrophic_harvest_error(e):
                    return failed_submissions, e
                failed_submissions += 1
                logger.warning("Skipping failed ARC submission in harvest %s: %s", harvest_id, e)

        return failed_submissions, None

    async def _submit_arcs_parallel(
        self,
        harvest_id: str,
        arcs: "AsyncGenerator[ARC | dict[str, Any] | str, None] | AsyncIterator[ARC | dict[str, Any] | str]",
    ) -> int:
        """Submit all ARCs in bounded parallelism and return number of skipped ARC submissions."""
        pending_tasks: set[asyncio.Task[None]] = set()
        failed_submissions = 0

        async def submit_one(arc_item: "ARC | dict[str, Any] | str") -> None:
            await self.submit_arc_in_harvest(harvest_id, arc_item)

        async for arc in arcs:
            task = asyncio.create_task(submit_one(arc))
            pending_tasks.add(task)

            if len(pending_tasks) >= self._config.max_concurrency:
                done, pending = await asyncio.wait(pending_tasks, return_when=asyncio.FIRST_COMPLETED)
                pending_tasks = pending
                failed_delta, catastrophic_error = self._process_completed_arc_tasks(harvest_id, done)
                failed_submissions += failed_delta
                if catastrophic_error is not None:
                    await self._cancel_pending_arc_tasks(pending_tasks)
                    raise catastrophic_error

        if pending_tasks:
            done, _ = await asyncio.wait(pending_tasks)
            failed_delta, catastrophic_error = self._process_completed_arc_tasks(harvest_id, done)
            failed_submissions += failed_delta
            if catastrophic_error is not None:
                raise catastrophic_error

        return failed_submissions

    def __init__(self, config: Config) -> None:
        """Initialize the ApiClient.

        Args:
            config: Configuration object containing API URL and certificate paths.

        Raises:
            ApiClientError: If certificate or key files don't exist.
        """
        self._config = config
        self._client: httpx.AsyncClient | None = None

        self._configure_global_request_limiter(config.max_concurrency)

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

        for attempt in range(self._config.max_retries + 1):
            if attempt > 0:
                delay = self._config.retry_backoff_factor * (2 ** (attempt - 1))
                logger.info(
                    "Retrying %s %s in %.1fs (attempt %d/%d)", method, path, delay, attempt, self._config.max_retries
                )
                await asyncio.sleep(delay)

            try:
                logger.debug("Sending %s request to %s (attempt %d)", method, path, attempt + 1)
                async with self._acquire_request_slot():
                    resp = await client.request(method, path, **kwargs)

                # Retry on transient server-side errors before raising
                should_retry = self._should_retry_failure(method, status_code=resp.status_code)
                if should_retry and attempt < self._config.max_retries:
                    logger.warning("Transient HTTP error %d from server, will retry", resp.status_code)
                    continue

                resp.raise_for_status()
                logger.debug("%s %s succeeded with status %d", method, path, resp.status_code)

                return self._parse_json_response(resp, method, path)

            except (httpx.HTTPStatusError, httpx.RequestError) as e:
                if self._should_retry_or_raise_failure(
                    e,
                    method=method,
                    attempt=attempt,
                    max_retries=self._config.max_retries,
                ):
                    continue

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

    async def _get(self, path: str, *, params: dict[str, str] | None = None) -> Any:
        """GET request."""
        return await self._request_with_retries("GET", path, params=params)

    async def _delete(self, path: str) -> None:
        """DELETE request, ignoring a 204 No Content response."""
        await self._request_with_retries("DELETE", path)

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    @classmethod
    def _serialize_arc(cls, arc: "ARC | dict[str, Any] | str") -> dict[str, Any]:
        """Serialize an ARC object, dict, or JSON string to a plain RO-Crate JSON dict."""
        if isinstance(arc, dict):
            return arc
        if isinstance(arc, str):
            try:
                data = json.loads(arc)
                if not isinstance(data, dict):
                    raise ApiClientError(f"JSON string must represent a dictionary, got {type(data).__name__}")
                return cast(dict[str, Any], data)
            except json.JSONDecodeError as e:
                raise ApiClientError(f"Invalid JSON string provided for ARC: {e}") from e
        return cast(dict[str, Any], json.loads(arc.ToROCrateJsonString()))

    @classmethod
    def _parse_arc_response(cls, data: Any) -> ArcResult:
        try:
            return ArcResult.model_validate(data)
        except ValidationError as e:
            raise ApiClientError(f"Invalid ARC response from API: {e}") from e

    @classmethod
    def _parse_harvest_response(cls, data: Any) -> HarvestResult:
        try:
            return HarvestResult.model_validate(data)
        except ValidationError as e:
            raise ApiClientError(f"Invalid harvest response from API: {e}") from e

    # ------------------------------------------------------------------
    # ARC endpoints (v3)
    # ------------------------------------------------------------------

    async def create_or_update_arc(
        self,
        rdi: str,
        arc: "ARC | dict[str, Any] | str",
    ) -> ArcResult:
        """Create or update an ARC.

        Uses ``POST /v3/arcs``.  The server stores the ARC synchronously and
        triggers the GitLab synchronisation in the background — no polling
        required.

        Args:
            rdi: RDI identifier.
            arc: ARC object, a pre-serialised RO-Crate JSON dict, or a JSON string.

        Returns:
            :class:`ArcResult` with the result of the operation.
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
    ) -> HarvestResult:
        """Start a new harvest run.

        Uses ``POST /v3/harvests``.

        Args:
            rdi: RDI identifier.
            expected_datasets: Optional hint about how many datasets will be submitted.

        Returns:
            :class:`HarvestResult` with the newly created harvest.
        """
        request = CreateHarvestRequest(rdi=rdi, expected_datasets=expected_datasets)
        data = await self._post("v3/harvests", request)
        return self._parse_harvest_response(data)

    async def list_harvests(self, rdi: str | None = None) -> list[HarvestResult]:
        """List harvest runs.

        Uses ``GET /v3/harvests``.

        Args:
            rdi: Optional RDI filter.

        Returns:
            List of :class:`HarvestResult` objects.
        """
        params: dict[str, str] | None = None
        if rdi:
            params = {"rdi": rdi}
        data = await self._get("v3/harvests", params=params)
        try:
            return [HarvestResult.model_validate(d) for d in data]
        except ValidationError as e:
            raise ApiClientError(f"Invalid harvest list response from API: {e}") from e

    async def get_harvest(self, harvest_id: str) -> HarvestResult:
        """Get a single harvest run by ID.

        Uses ``GET /v3/harvests/{harvest_id}``.

        Args:
            harvest_id: Harvest identifier.

        Returns:
            :class:`HarvestResult`.
        """
        data = await self._get(f"v3/harvests/{harvest_id}")
        return self._parse_harvest_response(data)

    async def complete_harvest(self, harvest_id: str) -> HarvestResult:
        """Mark a harvest run as completed.

        Uses ``POST /v3/harvests/{harvest_id}/complete``.

        Args:
            harvest_id: Harvest identifier.

        Returns:
            Updated :class:`HarvestResult`.
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
        arc: "ARC | dict[str, Any] | str",
    ) -> ArcResult:
        """Submit an ARC within an active harvest run.

        Uses ``POST /v3/harvests/{harvest_id}/arcs``.  The RDI is resolved
        automatically from the harvest run on the server side.

        Args:
            harvest_id: Harvest identifier.
            arc: ARC object, a pre-serialised RO-Crate JSON dict, or a JSON string.

        Returns:
            :class:`ArcResult` with the result of the operation.
        """
        serialized = self._serialize_arc(arc)
        request = SubmitHarvestArcRequest(arc=serialized)
        data = await self._post(f"v3/harvests/{harvest_id}/arcs", request)
        return self._parse_arc_response(data)

    async def harvest_arcs(
        self,
        rdi: str,
        arcs: "AsyncGenerator[ARC | dict[str, Any] | str, None] | AsyncIterator[ARC | dict[str, Any] | str]",
        expected_datasets: int | None = None,
    ) -> HarvestResult:
        """Create a harvest, upload all ARCs from an async generator, then complete it.

        The method:

        1. Creates a new harvest for *rdi*.
        2. Iterates *arcs*, submitting each one as part of that harvest.
        3. Calls :meth:`complete_harvest` when the generator is exhausted.

        ARC submission is best-effort: item-level errors are logged and skipped,
        and the harvest continues with remaining items. Catastrophic errors
        (for example auth or harvest-state failures) abort the harvest.

        Args:
            rdi: RDI identifier for the harvest.
            arcs: Async generator or async iterator yielding ARC objects,
                pre-serialised RO-Crate dicts, or JSON strings.
            expected_datasets: Optional hint about the total number of ARCs.

        Returns:
            :class:`HarvestResult` of the completed harvest.

        Raises:
            ApiClientError: On catastrophic HTTP or serialization errors. The
                harvest is cancelled before the exception propagates.

        Example::

            async def my_arcs() -> AsyncGenerator[dict | str, None]:
                for arc in source:
                    yield arc

            async with ApiClient(config) as client:
                result = await client.harvest_arcs("my-rdi", my_arcs())
        """
        harvest = await self.create_harvest(rdi, expected_datasets=expected_datasets)
        harvest_id = harvest.harvest_id
        logger.info("[%s] Started harvest %s for RDI %s", rdi, harvest_id, rdi)

        try:
            failed_submissions = await self._submit_arcs_parallel(harvest_id, arcs)
        except Exception:
            logger.warning("[%s] Catastrophic error during ARC submission, cancelling harvest %s", rdi, harvest_id)
            await self._cancel_harvest_safely(rdi, harvest_id)
            raise

        if failed_submissions > 0:
            logger.warning(
                "[%s] Harvest %s completed with %d skipped ARC submissions",
                rdi,
                harvest_id,
                failed_submissions,
            )

        result = await self.complete_harvest(harvest_id)
        logger.info("[%s] Completed harvest %s", rdi, harvest_id)
        return result

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
