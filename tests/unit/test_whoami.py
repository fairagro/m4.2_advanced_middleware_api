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


@pytest.mark.asyncio
async def test_whoami_with_empty_accessible_rdis() -> None:
    """Test that whoami handles empty accessible_rdis list."""
    service = BusinessLogic(store=MagicMock())
    client_id = "TestClient"
    accessible_rdis: list[str] = []

    result = await service.whoami(client_id, accessible_rdis=accessible_rdis)

    assert isinstance(result, WhoamiResponse)  # nosec
    assert result.client_id == client_id  # nosec
    assert result.accessible_rdis == []  # nosec


@pytest.mark.asyncio
async def test_whoami_with_multiple_accessible_rdis() -> None:
    """Test that whoami correctly returns multiple accessible RDIs."""
    service = BusinessLogic(store=MagicMock())
    client_id = "TestClient"
    accessible_rdis = ["bonares", "edal", "edaphobase", "publisso"]

    result = await service.whoami(client_id, accessible_rdis=accessible_rdis)

    assert isinstance(result, WhoamiResponse)  # nosec
    assert result.client_id == client_id  # nosec
    assert set(result.accessible_rdis) == {"bonares", "edal", "edaphobase", "publisso"}  # nosec
    assert len(result.accessible_rdis) == 4  # nosec


@pytest.mark.asyncio
async def test_whoami_preserves_accessible_rdis_order() -> None:
    """Test that whoami preserves the order of accessible_rdis."""
    service = BusinessLogic(store=MagicMock())
    client_id = "TestClient"
    accessible_rdis = ["zeta", "alpha", "beta"]

    result: WhoamiResponse = await service.whoami(client_id, accessible_rdis=accessible_rdis)

    assert result.accessible_rdis == ["zeta", "alpha", "beta"]  # nosec
