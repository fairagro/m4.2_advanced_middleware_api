from unittest.mock import MagicMock
import pytest

from app.middleware_service import (
    MiddlewareResponse,
    MiddlewareService
)


@pytest.mark.asyncio
async def test_whoami_returns_middleware_response():
    service = MiddlewareService(store=MagicMock())  # store kannst du mocken oder None setzen
    client_id = "TestClient"

    result = await service.whoami(client_id)

    assert isinstance(result, MiddlewareResponse) # nosec
    assert result.client_id == client_id # nosec
    assert result.message == "Client authenticated successfully" # nosec
