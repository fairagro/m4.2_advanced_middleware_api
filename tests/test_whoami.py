import pytest

from app.middleware_service import (
    ClientCertMissingError,
    ClientCertParsingError,
    InvalidAcceptTypeError,
    MiddlewareResponse,
    MiddlewareService
)


@pytest.mark.asyncio
async def test_authenticated(service: MiddlewareService, cert: str):
    result = await service.whoami(
        client_cert=cert,
        accept_type="application/json")
    
    assert isinstance(result, MiddlewareResponse) # nosec
    assert result.client_id == "TestClient" # nosec


@pytest.mark.asyncio
async def test_no_cert(service: MiddlewareService, cert: str):
    with pytest.raises(ClientCertMissingError):
        await service.whoami(
            client_cert=None,
            accept_type="application/json")


@pytest.mark.asyncio
async def test_whoami_invalid_cert(service: MiddlewareService, cert: str):
    with pytest.raises(ClientCertParsingError):
        await service.whoami(
            client_cert="invalid_cert",
            accept_type="application/json")


@pytest.mark.asyncio
async def test_invalid_accept_header(service: MiddlewareService, cert: str):
    with pytest.raises(InvalidAcceptTypeError):
        await service.whoami(
            client_cert=cert,
            accept_type="application/xml")
