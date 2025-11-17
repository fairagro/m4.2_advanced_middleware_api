"""Unit tests for the whoami method in BusinessLogic."""

from unittest.mock import MagicMock

import pytest

from middleware_api.business_logic import BusinessLogic, WhoamiResponse


@pytest.mark.asyncio
async def test_whoami_returns_middleware_response() -> None:
    """Test that whoami returns a BusinessLogicResponse."""
    service = BusinessLogic(store=MagicMock())
    client_id = "TestClient"
    accessible_rdis = ["rdi1", "rdi2"]

    result = await service.whoami(client_id, accessible_rdis=accessible_rdis)

    assert isinstance(result, WhoamiResponse)  # nosec
    assert result.client_id == client_id  # nosec
    assert result.message == "Client authenticated successfully"  # nosec
    assert result.accessible_rdis == accessible_rdis  # nosec
