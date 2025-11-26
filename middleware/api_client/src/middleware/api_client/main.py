"""Client for the FAIRagro Middleware API."""

import logging
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel

from middleware.shared.api_models.models import (
    CreateOrUpdateArcsRequest,
    CreateOrUpdateArcsResponse,
)

from .config import Config

logger = logging.getLogger(__name__)


class MiddlewareClientError(Exception):
    """Base exception for MiddlewareClient errors."""


class MiddlewareClient:
    """Client for the FAIRagro Middleware API.
    
    This client provides access to the Middleware API with certificate-based
    authentication (mTLS). It supports creating and updating ARCs.
    
    Example:
        ```python
        from pathlib import Path
        from middleware.api_client import Config, MiddlewareClient
        
        # Load configuration from YAML file
        config = Config.from_yaml_file(Path("config.yaml"))
        
        # Create client instance
        async with MiddlewareClient(config) as client:
            # Create request
            request = CreateOrUpdateArcsRequest(
                rdi="my-rdi",
                arcs=[{"@context": "...", "@id": "...", ...}]
            )
            
            # Send request
            response = await client.create_or_update_arcs(request)
            print(f"Created/Updated {len(response.arcs)} ARCs")
        ```
    """

    def __init__(self, config: Config) -> None:
        """Initialize the MiddlewareClient.

        Args:
            config (Config): Configuration object containing API URL and certificate paths.
        
        Raises:
            MiddlewareClientError: If certificate or key files don't exist.
        """
        self._config = config
        self._client: httpx.AsyncClient | None = None
        
        # Validate certificate files exist
        cert_path = config.get_client_cert_path()
        key_path = config.get_client_key_path()
        
        if not cert_path.exists():
            raise MiddlewareClientError(f"Client certificate not found: {cert_path}")
        if not key_path.exists():
            raise MiddlewareClientError(f"Client key not found: {key_path}")
        
        # Validate CA cert if provided
        ca_path = config.get_ca_cert_path()
        if ca_path and not ca_path.exists():
            raise MiddlewareClientError(f"CA certificate not found: {ca_path}")
        
        logger.debug(
            "MiddlewareClient initialized with API URL: %s, cert: %s, key: %s",
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
            # Prepare certificate tuple for mTLS
            cert = (
                str(self._config.get_client_cert_path()),
                str(self._config.get_client_key_path()),
            )
            
            # Prepare verify parameter
            if not self._config.verify_ssl:
                verify: bool | str = False
            elif self._config.get_ca_cert_path():
                verify = str(self._config.get_ca_cert_path())
            else:
                verify = True
            
            self._client = httpx.AsyncClient(
                base_url=self._config.api_url,
                cert=cert,
                verify=verify,
                timeout=self._config.timeout,
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
            MiddlewareClientError: If the request fails.
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
            raise MiddlewareClientError(error_msg) from e
        except httpx.RequestError as e:
            error_msg = f"Request error: {str(e)}"
            logger.error(error_msg)
            raise MiddlewareClientError(error_msg) from e

    async def create_or_update_arcs(
        self,
        request: CreateOrUpdateArcsRequest,
    ) -> CreateOrUpdateArcsResponse:
        """Create or update ARCs in the FAIRagro Middleware API.

        Args:
            request (CreateOrUpdateArcsRequest): The request payload containing RDI and ARC data.

        Returns:
            CreateOrUpdateArcsResponse: The response containing the result of the operation.
        
        Raises:
            MiddlewareClientError: If the request fails.
        """
        logger.info("Creating/updating ARCs for RDI: %s", request.rdi)
        result = await self._post("/v1/arcs", request)
        response = CreateOrUpdateArcsResponse.model_validate(result)
        logger.info(
            "Successfully created/updated %d ARCs for RDI: %s",
            len(response.arcs),
            response.rdi,
        )
        return response

    async def aclose(self) -> None:
        """Close the underlying HTTP client connection.

        This should be called to properly clean up resources when the client
        is no longer needed.
        """
        if self._client is not None:
            logger.debug("Closing httpx.AsyncClient")
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "MiddlewareClient":
        """Async context manager entry.
        
        Returns:
            MiddlewareClient: This client instance.
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
