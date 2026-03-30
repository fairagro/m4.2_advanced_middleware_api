"""Unit tests for CouchDB client."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiocouch import CouchDB
from aiocouch.exception import NotFoundError, PreconditionFailedError
from pydantic import SecretStr

from middleware.api.document_store.config import CouchDBConfig
from middleware.api.document_store.couchdb_client import CouchDBClient


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
    with patch("middleware.api.document_store.couchdb_client.CouchDB") as mock_couchdb:
        mock_instance = mock_couchdb.return_value
        mock_db = AsyncMock()

        # In aiocouch, db = await couchdb['db_name']
        # So couchdb.__getitem__ must be an AsyncMock or similar
        # It's called for _users, _replicator, _global_changes, then test_db
        mock_instance.__getitem__ = AsyncMock(return_value=mock_db)

        await couchdb_client.connect()

        assert couchdb_client._client == mock_instance  # noqa: SLF001
        assert couchdb_client._db == mock_db  # noqa: SLF001
        assert mock_instance.__getitem__.call_count == 4  # noqa: PLR2004
        mock_instance.__getitem__.assert_any_call(couchdb_client._db_name)  # noqa: SLF001
        mock_instance.__getitem__.assert_any_call("_users")


@pytest.mark.asyncio
async def test_couchdb_client_connect_create_db(couchdb_client: CouchDBClient) -> None:
    """Test connecting to CouchDB and creating a new database if it does not exist.

    Parameters
    ----------
    couchdb_client : CouchDBClient
        An instance of CouchDBClient initialized with the provided configuration.
    """
    with patch("middleware.api.document_store.couchdb_client.CouchDB") as mock_couchdb:
        mock_instance = mock_couchdb.return_value
        # Succeed for system dbs, fail for test_db
        mock_instance.__getitem__ = AsyncMock(
            side_effect=[AsyncMock(), AsyncMock(), AsyncMock(), NotFoundError("Not Found")]
        )
        mock_db = AsyncMock()
        mock_instance.create = AsyncMock(return_value=mock_db)

        await couchdb_client.connect()

        assert couchdb_client._db == mock_db  # noqa: SLF001
        mock_instance.create.assert_called_with(couchdb_client._db_name)  # noqa: SLF001
        assert mock_instance.__getitem__.call_count == 4  # noqa: PLR2004


@pytest.mark.asyncio
async def test_couchdb_client_connect_failure(couchdb_client: CouchDBClient) -> None:
    """Test failure to connect to CouchDB.

    Parameters
    ----------
    couchdb_client : CouchDBClient
        An instance of CouchDBClient initialized with the provided configuration.
    """
    with (
        patch("middleware.api.document_store.couchdb_client.CouchDB", side_effect=Exception("Connection Failed")),
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
    mock_client = MagicMock(spec=CouchDB)
    mock_client.info = AsyncMock(return_value={"couchdb": "Welcome"})

    couchdb_client._client = mock_client  # noqa: SLF001

    result = await couchdb_client.health_check()
    assert result is True
    mock_client.info.assert_called_once()


@pytest.mark.asyncio
async def test_couchdb_client_health_check_failure(couchdb_client: CouchDBClient) -> None:
    """Test failed health check.

    Parameters
    ----------
    couchdb_client : CouchDBClient
        An instance of CouchDBClient initialized with the provided configuration.
    """
    mock_client = MagicMock(spec=CouchDB)
    mock_client.info = AsyncMock(side_effect=Exception("error"))
    couchdb_client._client = mock_client  # noqa: SLF001

    result = await couchdb_client.health_check()
    assert result is False
    mock_client.info.assert_called_once()


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
    couchdb_client._db = mock_db  # noqa: SLF001

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
    couchdb_client._db = mock_db  # noqa: SLF001

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
    """Test saving a new document calls create() then save() on the returned Document.

    Parameters
    ----------
    couchdb_client : CouchDBClient
        An instance of CouchDBClient initialized with the provided configuration.
    """
    mock_db = MagicMock()
    mock_db.__getitem__ = AsyncMock(side_effect=NotFoundError)
    # Simulate an aiocouch Document: create() returns an object with a save() coroutine.
    mock_doc = MagicMock()
    mock_doc.save = AsyncMock()
    mock_doc.__iter__ = MagicMock(return_value=iter({"_id": "new_doc", "val": 1}.items()))
    mock_db.create = AsyncMock(return_value=mock_doc)
    couchdb_client._db = mock_db  # noqa: SLF001

    await couchdb_client.save_document("new_doc", {"val": 1})

    mock_db.create.assert_called_with("new_doc", data={"val": 1})
    mock_doc.save.assert_awaited_once()


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
    couchdb_client._db = mock_db  # noqa: SLF001

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
    couchdb_client._db = mock_db  # noqa: SLF001

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
    couchdb_client._db = mock_db  # noqa: SLF001

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
    couchdb_client._db = mock_db  # noqa: SLF001

    selector = {"type": "arc"}
    result = await couchdb_client.find(selector, limit=10)

    assert result == docs
    mock_db.find.assert_called_with(selector, limit=10, skip=0)


@pytest.mark.asyncio
async def test_couchdb_client_find_projected(couchdb_client: CouchDBClient) -> None:
    """Test finding projected documents with a selector."""
    couchdb_client._db = MagicMock()  # noqa: SLF001
    couchdb_client._db_name = "test_db"  # noqa: SLF001

    selector = {"type": "arc"}
    fields = ["metadata.events"]
    expected_docs = [{"metadata": {"events": [{"type": "arc_created"}]}}]

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={"docs": expected_docs})

    mock_session = MagicMock()
    mock_session.post.return_value.__aenter__.return_value = mock_response
    mock_session.post.return_value.__aexit__.return_value = None

    couchdb_client._session = mock_session  # noqa: SLF001

    result = await couchdb_client.find_projected(selector, fields, limit=10, skip=2)

    assert result == expected_docs
    mock_session.post.assert_called_once_with(
        "http://localhost:5984/test_db/_find",
        json={
            "selector": selector,
            "fields": fields,
            "limit": 10,
            "skip": 2,
        },
    )


@pytest.mark.asyncio
async def test_couchdb_client_find_projected_raises_on_http_error(couchdb_client: CouchDBClient) -> None:
    """Test projected find raises when CouchDB returns an error status."""
    couchdb_client._db = MagicMock()  # noqa: SLF001
    couchdb_client._db_name = "test_db"  # noqa: SLF001

    mock_response = AsyncMock()
    mock_response.status = 400
    mock_response.text = AsyncMock(return_value='{"error":"bad_request"}')

    mock_session = MagicMock()
    mock_session.post.return_value.__aenter__.return_value = mock_response
    mock_session.post.return_value.__aexit__.return_value = None

    couchdb_client._session = mock_session  # noqa: SLF001

    with pytest.raises(RuntimeError, match="CouchDB _find failed with status 400"):
        await couchdb_client.find_projected({"type": "arc"}, ["metadata.events"])


@pytest.mark.asyncio
async def test_couchdb_client_ensure_system_databases(couchdb_client: CouchDBClient) -> None:
    """Test ensuring system databases exist."""
    with patch("middleware.api.document_store.couchdb_client.CouchDB") as mock_couchdb:
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
        couchdb_client._client = mock_instance  # noqa: SLF001

        await couchdb_client.ensure_system_databases()

        assert mock_instance.__getitem__.call_count == 3  # noqa: PLR2004
        mock_instance.create.assert_called_once_with("_replicator")


@pytest.mark.asyncio
async def test_couchdb_client_ensure_system_databases_race(couchdb_client: CouchDBClient) -> None:
    """Test ensuring system databases where create fails because it already exists."""
    with patch("middleware.api.document_store.couchdb_client.CouchDB") as mock_couchdb:
        mock_instance = mock_couchdb.return_value
        # All missing
        mock_instance.__getitem__ = AsyncMock(side_effect=NotFoundError("Not Found"))
        # Create fails with conflict
        mock_instance.create = AsyncMock(side_effect=PreconditionFailedError("Already exists"))

        # Manually set the client
        couchdb_client._client = mock_instance  # noqa: SLF001

        # Should not raise
        await couchdb_client.ensure_system_databases()

        assert mock_instance.create.call_count == 3  # noqa: PLR2004


@pytest.mark.asyncio
async def test_couchdb_client_ensure_system_databases_not_connected(couchdb_client: CouchDBClient) -> None:
    """Test ensuring system databases when not connected."""
    with pytest.raises(RuntimeError, match="Not connected to CouchDB server"):
        await couchdb_client.ensure_system_databases()


@pytest.mark.asyncio
async def test_couchdb_client_connect_race_condition(couchdb_client: CouchDBClient) -> None:
    """Test connection with race condition where DB is created between check and create."""
    with patch("middleware.api.document_store.couchdb_client.CouchDB") as mock_couchdb:
        mock_instance = mock_couchdb.return_value
        mock_db = AsyncMock()

        # side_effect for __getitem__:
        # 1-3. system dbs exist
        # 4. test_db not found
        # 5. test_db exists (after race)
        mock_instance.__getitem__ = AsyncMock(
            side_effect=[
                AsyncMock(),
                AsyncMock(),
                AsyncMock(),
                NotFoundError("Not Found"),
                mock_db,
            ]
        )
        # create fails with conflict/already exists (412)
        mock_instance.create = AsyncMock(side_effect=PreconditionFailedError("Already exists"))

        await couchdb_client.connect()

        assert couchdb_client._db == mock_db  # noqa: SLF001
        assert mock_instance.__getitem__.call_count == 5  # noqa: PLR2004
        mock_instance.create.assert_called_once_with(couchdb_client._db_name)  # noqa: SLF001
