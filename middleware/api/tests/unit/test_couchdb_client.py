"""Unit tests for CouchDB client."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiocouch.exception import NotFoundError
from pydantic import SecretStr

from middleware.api.config import CouchDBConfig
from middleware.api.couchdb_client import CouchDBClient


@pytest.fixture
def couchdb_config() -> CouchDBConfig:
    """Fixture to provide a CouchDBConfig instance for testing.

    Returns
    -------
    CouchDBConfig
        Configuration object for CouchDB connection.
    """
    return CouchDBConfig(url="http://localhost:5984", user="admin", password=SecretStr("password"))


@pytest.fixture
def couchdb_client(couchdb_config: CouchDBConfig) -> CouchDBClient:
    """Create a CouchDBClient instance from the provided configuration.

    Parameters
    ----------
    couchdb_config : CouchDBConfig
        Configuration object for CouchDB connection.

    Returns
    -------
    CouchDBClient
        An instance of CouchDBClient initialized with the provided configuration.
    """
    return CouchDBClient.from_config(couchdb_config)


@pytest.mark.asyncio
async def test_couchdb_client_connect_success(couchdb_client: CouchDBClient) -> None:
    """Test successful connection to CouchDB.

    Parameters
    ----------
    couchdb_client : CouchDBClient
        An instance of CouchDBClient initialized with the provided configuration.
    """
    with patch("middleware.api.couchdb_client.CouchDB") as mock_couchdb:
        mock_instance = mock_couchdb.return_value
        mock_db = AsyncMock()

        # In aiocouch, db = await couchdb['db_name']
        # So couchdb.__getitem__ must be an AsyncMock or similar
        mock_instance.__getitem__ = AsyncMock(return_value=mock_db)

        await couchdb_client.connect("test_db")

        assert couchdb_client._client == mock_instance  # pylint: disable=protected-access
        assert couchdb_client._db == mock_db  # pylint: disable=protected-access
        mock_instance.__getitem__.assert_called_with("test_db")


@pytest.mark.asyncio
async def test_couchdb_client_connect_create_db(couchdb_client: CouchDBClient) -> None:
    """Test connecting to CouchDB and creating a new database if it does not exist.

    Parameters
    ----------
    couchdb_client : CouchDBClient
        An instance of CouchDBClient initialized with the provided configuration.
    """
    with patch("middleware.api.couchdb_client.CouchDB") as mock_couchdb:
        mock_instance = mock_couchdb.return_value
        mock_instance.__getitem__ = AsyncMock(side_effect=NotFoundError("Not Found"))
        mock_db = AsyncMock()
        mock_instance.create = AsyncMock(return_value=mock_db)

        await couchdb_client.connect("new_db")

        assert couchdb_client._db == mock_db  # pylint: disable=protected-access
        mock_instance.create.assert_called_with("new_db")


@pytest.mark.asyncio
async def test_couchdb_client_connect_failure(couchdb_client: CouchDBClient) -> None:
    """Test failure to connect to CouchDB.

    Parameters
    ----------
    couchdb_client : CouchDBClient
        An instance of CouchDBClient initialized with the provided configuration.
    """
    with (
        patch("middleware.api.couchdb_client.CouchDB", side_effect=Exception("Connection Failed")),
        pytest.raises(Exception, match="Connection Failed"),
    ):
        await couchdb_client.connect()


@pytest.mark.asyncio
async def test_couchdb_client_health_check_success(couchdb_client: CouchDBClient) -> None:
    """Test successful health check.

    Parameters
    ----------
    couchdb_client : CouchDBClient
        An instance of CouchDBClient initialized with the provided configuration.
    """
    mock_client = MagicMock()
    mock_resp = AsyncMock()
    mock_resp.json.return_value = {"couchdb": "Welcome"}
    mock_resp.__aenter__.return_value = mock_resp
    mock_client.request.return_value = mock_resp

    couchdb_client._client = mock_client  # pylint: disable=protected-access

    result = await couchdb_client.health_check()
    assert result is True
    mock_client.request.assert_called_with("GET", "/")


@pytest.mark.asyncio
async def test_couchdb_client_health_check_failure(couchdb_client: CouchDBClient) -> None:
    """Test failed health check.

    Parameters
    ----------
    couchdb_client : CouchDBClient
        An instance of CouchDBClient initialized with the provided configuration.
    """
    mock_client = MagicMock()
    mock_client.request.side_effect = Exception("error")
    couchdb_client._client = mock_client  # pylint: disable=protected-access

    result = await couchdb_client.health_check()
    assert result is False


@pytest.mark.asyncio
async def test_couchdb_client_health_check_no_client(couchdb_client: CouchDBClient) -> None:
    """Test health check when not connected.

    Parameters
    ----------
    couchdb_client : CouchDBClient
        An instance of CouchDBClient initialized with the provided configuration.
    """
    result = await couchdb_client.health_check()
    assert result is False


@pytest.mark.asyncio
async def test_couchdb_client_get_document_success(couchdb_client: CouchDBClient) -> None:
    """Test retrieving a document successfully.

    Parameters
    ----------
    couchdb_client : CouchDBClient
        An instance of CouchDBClient initialized with the provided configuration.
    """
    mock_db = MagicMock()
    mock_doc = {"_id": "doc1", "data": "value"}
    mock_db.__getitem__ = AsyncMock(return_value=mock_doc)
    couchdb_client._db = mock_db  # pylint: disable=protected-access

    result = await couchdb_client.get_document("doc1")
    assert result == mock_doc


@pytest.mark.asyncio
async def test_couchdb_client_get_document_not_found(couchdb_client: CouchDBClient) -> None:
    """Test retrieving a non-existent document.

    Parameters
    ----------
    couchdb_client : CouchDBClient
        An instance of CouchDBClient initialized with the provided configuration.
    """
    mock_db = MagicMock()
    mock_db.__getitem__ = AsyncMock(side_effect=NotFoundError("Not Found"))
    couchdb_client._db = mock_db  # pylint: disable=protected-access

    result = await couchdb_client.get_document("nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_couchdb_client_get_document_no_db(couchdb_client: CouchDBClient) -> None:
    """Test retrieving a document when not connected to a database.

    Parameters
    ----------
    couchdb_client : CouchDBClient
        An instance of CouchDBClient initialized with the provided configuration.
    """
    with pytest.raises(RuntimeError, match="Not connected to CouchDB"):
        await couchdb_client.get_document("doc1")


@pytest.mark.asyncio
async def test_couchdb_client_save_document_new(couchdb_client: CouchDBClient) -> None:
    """Test saving a new document.

    Parameters
    ----------
    couchdb_client : CouchDBClient
        An instance of CouchDBClient initialized with the provided configuration.
    """
    mock_db = MagicMock()
    mock_db.__getitem__ = AsyncMock(side_effect=NotFoundError)
    mock_doc = {"_id": "new_doc", "val": 1}
    mock_db.create = AsyncMock(return_value=mock_doc)
    couchdb_client._db = mock_db  # pylint: disable=protected-access

    result = await couchdb_client.save_document("new_doc", {"val": 1})
    assert result == mock_doc
    mock_db.create.assert_called_with("new_doc", data={"val": 1})


@pytest.mark.asyncio
async def test_couchdb_client_save_document_update(couchdb_client: CouchDBClient) -> None:
    """Test updating an existing document.

    Parameters
    ----------
    couchdb_client : CouchDBClient
        An instance of CouchDBClient initialized with the provided configuration.
    """
    mock_db = MagicMock()
    existing_doc_data = {"_id": "doc1", "val": 1}

    mock_doc = MagicMock()
    mock_doc.update = MagicMock()
    mock_doc.save = AsyncMock()
    # Mocking dict(mock_doc) is tricky, let's make mock_doc behave like a dict or return one
    mock_doc.__iter__.return_value = iter(existing_doc_data.keys())
    mock_doc.__getitem__.side_effect = existing_doc_data.__getitem__

    mock_db.__getitem__ = AsyncMock(return_value=mock_doc)
    couchdb_client._db = mock_db  # pylint: disable=protected-access

    await couchdb_client.save_document("doc1", {"val": 2})

    mock_doc.update.assert_called_with({"val": 2})
    mock_doc.save.assert_called_once()


@pytest.mark.asyncio
async def test_couchdb_client_delete_document_success(couchdb_client: CouchDBClient) -> None:
    """Test deleting a document successfully.

    Parameters
    ----------
    couchdb_client : CouchDBClient
        An instance of CouchDBClient initialized with the provided configuration.
    """
    mock_db = MagicMock()
    mock_doc = AsyncMock()
    mock_db.__getitem__ = AsyncMock(return_value=mock_doc)
    couchdb_client._db = mock_db  # pylint: disable=protected-access

    result = await couchdb_client.delete_document("doc1")
    assert result is True
    mock_doc.delete.assert_called_once()


@pytest.mark.asyncio
async def test_couchdb_client_delete_document_not_found(couchdb_client: CouchDBClient) -> None:
    """Test deleting a non-existent document.

    Parameters
    ----------
    couchdb_client : CouchDBClient
        An instance of CouchDBClient initialized with the provided configuration.
    """
    mock_db = MagicMock()
    mock_db.__getitem__ = AsyncMock(side_effect=NotFoundError("Not Found"))
    couchdb_client._db = mock_db  # pylint: disable=protected-access

    result = await couchdb_client.delete_document("doc1")
    assert result is False


@pytest.mark.asyncio
async def test_couchdb_client_find(couchdb_client: CouchDBClient) -> None:
    """Test finding documents with a selector.

    Parameters
    ----------
    couchdb_client : CouchDBClient
        An instance of CouchDBClient initialized with the provided configuration.
    """
    mock_db = MagicMock()
    mock_result = AsyncMock()

    # Mocking async for
    docs = [{"_id": "1"}, {"_id": "2"}]
    mock_result.__aiter__.return_value = iter(docs)

    mock_db.find.return_value = mock_result
    couchdb_client._db = mock_db  # pylint: disable=protected-access

    selector = {"type": "arc"}
    result = await couchdb_client.find(selector, limit=10)

    assert result == docs
    mock_db.find.assert_called_with(selector, limit=10)


@pytest.mark.asyncio
async def test_couchdb_client_context_manager(couchdb_config: CouchDBConfig) -> None:
    """Test the async context manager.

    Parameters
    ----------
    couchdb_config : CouchDBConfig
        Configuration object for CouchDB connection.
    """
    with patch("middleware.api.couchdb_client.CouchDB") as mock_couchdb:
        mock_instance = mock_couchdb.return_value
        mock_instance.close = AsyncMock()

        async with CouchDBClient.from_config(couchdb_config) as client:
            client._client = mock_instance  # pylint: disable=protected-access
            assert isinstance(client, CouchDBClient)

        mock_instance.close.assert_called_once()


@pytest.mark.asyncio
async def test_couchdb_client_get_db(couchdb_client: CouchDBClient) -> None:
    """Test retrieving the database instance.

    Parameters
    ----------
    couchdb_client : CouchDBClient
        An instance of CouchDBClient initialized with the provided configuration.
    """
    mock_db = MagicMock()
    couchdb_client._db = mock_db  # pylint: disable=protected-access
    assert couchdb_client.get_db() == mock_db


@pytest.mark.asyncio
async def test_couchdb_client_ensure_system_databases(couchdb_client: CouchDBClient) -> None:
    """Test ensuring system databases exist."""
    with patch("middleware.api.couchdb_client.CouchDB") as mock_couchdb:
        mock_instance = mock_couchdb.return_value
        # One exists, one missing, one fails
        mock_instance.__getitem__ = AsyncMock(
            side_effect=[
                AsyncMock(),  # _users exists
                NotFoundError("Not Found"),  # _replicator missing
                Exception("Error"),  # _global_changes fails
            ]
        )
        mock_instance.create = AsyncMock()

        # Manually set the client since connect() wasn't called
        couchdb_client._client = mock_instance  # pylint: disable=protected-access

        await couchdb_client.ensure_system_databases()

        assert mock_instance.__getitem__.call_count == 3  # noqa: PLR2004
        mock_instance.create.assert_called_once_with("_replicator")


@pytest.mark.asyncio
async def test_couchdb_client_ensure_system_databases_not_connected(couchdb_client: CouchDBClient) -> None:
    """Test ensuring system databases when not connected."""
    with pytest.raises(RuntimeError, match="Not connected to CouchDB server"):
        await couchdb_client.ensure_system_databases()
