"""Unit tests for the whoami method in BusinessLogic."""

from unittest.mock import MagicMock
import pytest

from middleware_api.business_logic import (
    BusinessLogicResponse,
    BusinessLogic
)


@pytest.mark.asyncio
async def test_whoami_returns_middleware_response():
    """Test that whoami returns a BusinessLogicResponse."""
    service = BusinessLogic(store=MagicMock())
    client_id = "TestClient"

    result = await service.whoami(client_id)

    assert isinstance(result, BusinessLogicResponse) # nosec
    assert result.client_id == client_id # nosec
    assert result.message == "Client authenticated successfully" # nosec
