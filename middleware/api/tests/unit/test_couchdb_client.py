"""Unit tests for CouchDB client."""

import warnings
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiocouch import CouchDB
from aiocouch.exception import NotFoundError, PreconditionFailedError
from aiocouch.remote import RemoteServer
from pydantic import SecretStr

from middleware.api.document_store.config import CouchDBConfig
from middleware.api.document_store.couchdb_client import (
    CouchDBClient,
    DatabaseMissingError,
    DocumentConflictError,
    _patch_aiocouch_aiohttp_auth,
)
from middleware.api.document_store.errors import DocumentStoreUnavailableError
from middleware.shared.json_types import JsonObject


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
    """Create a CouchDBClient; tests inject ``_handles`` before document ops."""
    return CouchDBClient.from_config(couchdb_config)


def _inject_handles(
    client: CouchDBClient,
    *,
    couch: MagicMock | None = None,
    db: MagicMock | None = None,
    session: MagicMock | None = None,
    connected: bool = True,
) -> tuple[MagicMock, MagicMock, MagicMock]:
    """Attach mock network handles so ``_client`` / ``_db`` / ``_session`` work."""
    mock_couch = couch if couch is not None else MagicMock()
    if not hasattr(mock_couch, "__getitem__") or not isinstance(mock_couch.__getitem__, AsyncMock):
        mock_couch.__getitem__ = AsyncMock(return_value=MagicMock())
    mock_couch.close = AsyncMock()
    mock_db = db if db is not None else MagicMock()
    mock_session = session if session is not None else MagicMock()
    mock_session.closed = getattr(mock_session, "closed", True)
    if not hasattr(mock_session, "close") or not isinstance(mock_session.close, AsyncMock):
        mock_session.close = AsyncMock()
    client._handles = (mock_couch, mock_db, mock_session)  # noqa: SLF001
    client._connected = connected  # noqa: SLF001
    return mock_couch, mock_db, mock_session


@pytest.mark.asyncio
async def test_aiocouch_remote_server_avoids_basicauth_deprecation() -> None:
    """Patched aiocouch must not trigger aiohttp BasicAuth / auth= deprecations."""
    _patch_aiocouch_aiohttp_auth()

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        server = RemoteServer("http://localhost:5984", user="admin", password="secret")
        await server.close()

    auth_warnings = [
        w
        for w in caught
        if issubclass(w.category, DeprecationWarning)
        and ("BasicAuth" in str(w.message) or "auth' parameter is deprecated" in str(w.message))
    ]
    assert auth_warnings == []


@pytest.mark.asyncio
async def test_aiocouch_remote_server_forwards_client_session_kwargs() -> None:
    """Patched aiocouch must pass through ClientSession kwargs from upstream callers."""
    _patch_aiocouch_aiohttp_auth()

    with patch("middleware.api.document_store.couchdb_client.aiohttp.ClientSession") as mock_session:
        RemoteServer("http://localhost:5984", user="admin", password="secret", timeout=42)
        mock_session.assert_called_once()
        _, kwargs = mock_session.call_args
        assert kwargs["timeout"] == 42  # noqa: PLR2004
        assert "auth" not in kwargs
        assert kwargs["headers"]["Authorization"].startswith("Basic ")


@pytest.mark.asyncio
async def test_aiocouch_remote_server_encodes_empty_string_credentials() -> None:
    """Empty-string user/password are set values and must still yield Basic auth."""
    _patch_aiocouch_aiohttp_auth()

    server = RemoteServer("http://localhost:5984", user="", password="")
    try:
        auth = server._http_session._default_headers.get("Authorization")  # noqa: SLF001
        assert auth is not None
        assert str(auth).startswith("Basic ")
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_couchdb_client_connect_success(couchdb_client: CouchDBClient) -> None:
    """Test successful connection to CouchDB."""
    mock_db = AsyncMock()
    mock_instance = MagicMock()
    mock_instance.__getitem__ = AsyncMock(return_value=mock_db)
    mock_instance.close = AsyncMock()
    mock_session = MagicMock()
    mock_session.closed = True
    mock_session.close = AsyncMock()

    with (
        patch("middleware.api.document_store.couchdb_client.CouchDB", return_value=mock_instance),
        patch("middleware.api.document_store.couchdb_client.Database", return_value=mock_db),
        patch("middleware.api.document_store.couchdb_client.aiohttp.ClientSession", return_value=mock_session),
    ):
        await couchdb_client.connect()

    assert couchdb_client._db == mock_db  # noqa: SLF001
    assert couchdb_client._connected is True  # noqa: SLF001
    assert mock_instance.__getitem__.call_count == 4  # noqa: PLR2004
    mock_instance.__getitem__.assert_any_call(couchdb_client._db_name)  # noqa: SLF001
    mock_instance.__getitem__.assert_any_call("_users")


@pytest.mark.asyncio
async def test_couchdb_client_connect_create_db(couchdb_client: CouchDBClient) -> None:
    """Test connecting to CouchDB and creating a new database if it does not exist."""
    mock_instance = MagicMock()
    mock_instance.__getitem__ = AsyncMock(
        side_effect=[AsyncMock(), AsyncMock(), AsyncMock(), NotFoundError("Not Found")]
    )
    mock_db = AsyncMock()
    mock_instance.create = AsyncMock(return_value=mock_db)
    mock_instance.close = AsyncMock()
    mock_session = MagicMock()
    mock_session.closed = True
    mock_session.close = AsyncMock()

    with (
        patch("middleware.api.document_store.couchdb_client.CouchDB", return_value=mock_instance),
        patch("middleware.api.document_store.couchdb_client.Database", return_value=MagicMock()),
        patch("middleware.api.document_store.couchdb_client.aiohttp.ClientSession", return_value=mock_session),
    ):
        await couchdb_client.connect()

    assert couchdb_client._db == mock_db  # noqa: SLF001
    mock_instance.create.assert_called_with(couchdb_client._db_name)  # noqa: SLF001
    assert mock_instance.__getitem__.call_count == 4  # noqa: PLR2004


@pytest.mark.asyncio
async def test_couchdb_client_connect_failure(couchdb_client: CouchDBClient) -> None:
    """Test failure to connect to CouchDB."""
    mock_instance = MagicMock()
    mock_instance.__getitem__ = AsyncMock(side_effect=Exception("Connection Failed"))
    mock_instance.close = AsyncMock()
    mock_session = MagicMock()
    mock_session.closed = True
    mock_session.close = AsyncMock()

    with (
        patch("middleware.api.document_store.couchdb_client.CouchDB", return_value=mock_instance),
        patch("middleware.api.document_store.couchdb_client.Database", return_value=MagicMock()),
        patch("middleware.api.document_store.couchdb_client.aiohttp.ClientSession", return_value=mock_session),
        pytest.raises(Exception, match="Connection Failed"),
    ):
        await couchdb_client.connect()


@pytest.mark.asyncio
async def test_couchdb_client_health_check_success(couchdb_client: CouchDBClient) -> None:
    """Health check succeeds when connected and the application database exists."""
    mock_client = MagicMock(spec=CouchDB)
    mock_client.__getitem__ = AsyncMock(return_value=AsyncMock())
    _inject_handles(couchdb_client, couch=mock_client)

    result = await couchdb_client.health_check()
    assert result is True
    mock_client.__getitem__.assert_awaited_once_with(couchdb_client._db_name)  # noqa: SLF001


@pytest.mark.asyncio
async def test_couchdb_client_health_check_missing_app_db(couchdb_client: CouchDBClient) -> None:
    """Health check fails when the application database is missing."""
    mock_client = MagicMock(spec=CouchDB)
    mock_client.__getitem__ = AsyncMock(side_effect=NotFoundError("missing"))
    _inject_handles(couchdb_client, couch=mock_client)

    result = await couchdb_client.health_check()
    assert result is False


@pytest.mark.asyncio
async def test_couchdb_client_health_check_not_connected(couchdb_client: CouchDBClient) -> None:
    """Health check fails when connect() has not completed (noop re-init hook)."""
    result = await couchdb_client.health_check()
    assert result is False


@pytest.mark.asyncio
async def test_couchdb_client_health_check_runs_reinit_hook(couchdb_client: CouchDBClient) -> None:
    """Health check invokes the re-init hook then probes the application DB."""
    mock_client = MagicMock(spec=CouchDB)
    mock_client.__getitem__ = AsyncMock(return_value=AsyncMock())

    async def _reinit() -> None:
        _inject_handles(couchdb_client, couch=mock_client)

    couchdb_client.set_reinit_hook(_reinit)

    assert await couchdb_client.health_check() is True


@pytest.mark.asyncio
async def test_save_document_recovers_after_database_wipe(couchdb_client: CouchDBClient) -> None:
    """Missing application DB triggers re-init hook and retries the write once."""
    reinit_calls = 0
    db_exists = False

    async def _reinit() -> None:
        nonlocal reinit_calls, db_exists
        reinit_calls += 1
        db_exists = True
        _inject_handles(couchdb_client, db=mock_db)

    mock_db = MagicMock()
    mock_db.__getitem__ = AsyncMock(side_effect=NotFoundError("db or doc missing"))
    created = MagicMock()
    created.save = AsyncMock()
    created.__iter__ = MagicMock(return_value=iter({"_id": "doc1", "_rev": "1-b", "k": "v"}.items()))
    mock_db.create = AsyncMock(return_value=created)

    mock_server = MagicMock(spec=CouchDB)

    async def _getitem(name: str) -> MagicMock:
        if name == couchdb_client._db_name:  # noqa: SLF001
            if not db_exists:
                raise NotFoundError("no db")
            return mock_db
        return MagicMock()

    mock_server.__getitem__ = AsyncMock(side_effect=_getitem)

    _inject_handles(couchdb_client, couch=mock_server, db=mock_db)
    couchdb_client.set_reinit_hook(_reinit)

    await couchdb_client.save_document("doc1", {"k": "v"})
    assert reinit_calls == 1
    mock_db.create.assert_awaited_once()
    created.save.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_document_missing_doc_does_not_reinit(couchdb_client: CouchDBClient) -> None:
    """Document 404 with an existing application DB must not trigger re-init."""
    reinit = AsyncMock()
    couchdb_client.set_reinit_hook(reinit)

    mock_db = MagicMock()
    mock_db.__getitem__ = AsyncMock(side_effect=NotFoundError("no doc"))
    mock_server = MagicMock(spec=CouchDB)
    mock_server.__getitem__ = AsyncMock(return_value=mock_db)

    _inject_handles(couchdb_client, couch=mock_server, db=mock_db)

    assert await couchdb_client.get_document("missing") is None
    reinit.assert_not_awaited()


@pytest.mark.asyncio
async def test_with_db_recovery_raises_unavailable_when_reinit_fails(
    couchdb_client: CouchDBClient,
) -> None:
    """Failed re-init becomes DocumentStoreUnavailableError (HTTP 503 at the API)."""

    async def _boom() -> None:
        raise RuntimeError("cannot create")

    couchdb_client.set_reinit_hook(_boom)

    async def _op() -> None:
        raise DatabaseMissingError("gone")

    with pytest.raises(DocumentStoreUnavailableError, match="re-initialization failed"):
        await couchdb_client._with_db_recovery(_op)  # noqa: SLF001


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
    _inject_handles(couchdb_client, db=mock_db)

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
    _inject_handles(couchdb_client, db=mock_db)

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
    _inject_handles(couchdb_client, db=mock_db)

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
    _inject_handles(couchdb_client, db=mock_db)

    await couchdb_client.save_document("doc1", {"val": 2})

    mock_doc.update.assert_called_with({"val": 2})
    mock_doc.save.assert_called_once()


@pytest.mark.asyncio
async def test_couchdb_client_save_document_validator_called_with_fresh_doc(
    couchdb_client: CouchDBClient,
) -> None:
    """pre_save_validator receives the freshly fetched document dict."""
    fresh_doc_data = {"_id": "doc1", "val": 99}
    mock_doc = MagicMock()
    mock_doc.update = MagicMock()
    mock_doc.save = AsyncMock()
    # dict(mock_doc) uses mock_doc.keys() + mock_doc[k] — configure both
    mock_doc.keys.return_value = list(fresh_doc_data.keys())
    mock_doc.__getitem__.side_effect = fresh_doc_data.__getitem__

    mock_db = MagicMock()
    mock_db.__getitem__ = AsyncMock(return_value=mock_doc)
    _inject_handles(couchdb_client, db=mock_db)

    validator = MagicMock()
    await couchdb_client.save_document("doc1", {"val": 100}, pre_save_validator=validator)

    validator.assert_called_once_with(dict(fresh_doc_data))


@pytest.mark.asyncio
async def test_couchdb_client_save_document_validator_exception_propagates(
    couchdb_client: CouchDBClient,
) -> None:
    """An exception raised by pre_save_validator propagates immediately without retry."""

    class SentinelError(Exception):
        pass

    fresh_doc_data = {"_id": "doc1", "state": "taken"}
    mock_doc = MagicMock()
    mock_doc.keys.return_value = fresh_doc_data.keys()
    mock_doc.__getitem__.side_effect = fresh_doc_data.__getitem__

    mock_db = MagicMock()
    mock_db.__getitem__ = AsyncMock(return_value=mock_doc)
    _inject_handles(couchdb_client, db=mock_db)

    def raising_validator(doc: dict) -> None:  # noqa: ARG001
        raise SentinelError("invariant violated")

    with pytest.raises(SentinelError, match="invariant violated"):
        await couchdb_client.save_document("doc1", {"state": "new"}, pre_save_validator=raising_validator)

    # save() must NOT have been called — write was aborted before it happened
    mock_doc.save.assert_not_called()


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
    _inject_handles(couchdb_client, db=mock_db)

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
    _inject_handles(couchdb_client, db=mock_db)

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
    _inject_handles(couchdb_client, db=mock_db)

    selector: JsonObject = {"type": "arc"}
    result = await couchdb_client.find(selector, limit=10)

    assert result == docs
    mock_db.find.assert_called_with(selector, limit=10, skip=0)


@pytest.mark.asyncio
async def test_couchdb_client_find_projected(couchdb_client: CouchDBClient) -> None:
    """Test finding projected documents with a selector."""
    couchdb_client._db_name = "test_db"  # noqa: SLF001

    selector: JsonObject = {"type": "arc"}
    fields = ["metadata.events"]
    expected_docs = [{"metadata": {"events": [{"type": "arc_created"}]}}]

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={"docs": expected_docs})

    mock_session = MagicMock()
    mock_session.post.return_value.__aenter__.return_value = mock_response
    mock_session.post.return_value.__aexit__.return_value = None
    _inject_handles(couchdb_client, session=mock_session)

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
async def test_couchdb_client_find_page_uses_bookmark_and_sort(couchdb_client: CouchDBClient) -> None:
    """find_page posts bookmark/sort and returns the next bookmark."""
    couchdb_client._db_name = "test_db"  # noqa: SLF001

    expected_docs = [{"_id": "arc_1"}, {"_id": "arc_2"}]
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={"docs": expected_docs, "bookmark": "next-bm"})

    mock_session = MagicMock()
    mock_session.post.return_value.__aenter__.return_value = mock_response
    mock_session.post.return_value.__aexit__.return_value = None
    _inject_handles(couchdb_client, session=mock_session)

    selector: JsonObject = {"doc_type": "arc", "rdi": "edal"}
    sort: list[JsonObject] = [{"doc_type": "asc"}, {"rdi": "asc"}, {"_id": "asc"}]
    docs, bookmark = await couchdb_client.find_page(
        selector,
        limit=2,
        bookmark="prev-bm",
        sort=sort,
    )

    assert docs == expected_docs
    assert bookmark == "next-bm"
    mock_session.post.assert_called_once_with(
        "http://localhost:5984/test_db/_find",
        json={
            "selector": selector,
            "limit": 2,
            "bookmark": "prev-bm",
            "sort": sort,
        },
    )


@pytest.mark.asyncio
async def test_couchdb_client_find_projected_raises_on_http_error(couchdb_client: CouchDBClient) -> None:
    """Test projected find raises when CouchDB returns an error status."""
    couchdb_client._db_name = "test_db"  # noqa: SLF001

    mock_response = AsyncMock()
    mock_response.status = 400
    mock_response.text = AsyncMock(return_value='{"error":"bad_request"}')

    mock_session = MagicMock()
    mock_session.post.return_value.__aenter__.return_value = mock_response
    mock_session.post.return_value.__aexit__.return_value = None
    _inject_handles(couchdb_client, session=mock_session)

    with pytest.raises(RuntimeError, match="CouchDB _find failed with status 400"):
        await couchdb_client.find_projected({"type": "arc"}, ["metadata.events"])


@pytest.mark.asyncio
async def test_save_document_if_revision_matches_success(couchdb_client: CouchDBClient) -> None:
    """Test revision-checked save succeeds and returns updated _rev."""
    couchdb_client._db_name = "test_db"  # noqa: SLF001

    mock_response = AsyncMock()
    mock_response.status = 201
    mock_response.json = AsyncMock(return_value={"ok": True, "id": "doc1", "rev": "2-new"})

    mock_session = MagicMock()
    mock_session.put.return_value.__aenter__.return_value = mock_response
    mock_session.put.return_value.__aexit__.return_value = None
    _inject_handles(couchdb_client, session=mock_session)

    result = await couchdb_client.save_document_if_revision_matches(
        "doc1",
        {"type": "harvest", "statistics": {"arcs_submitted": 1}},
        expected_rev="1-old",
    )

    assert result["_id"] == "doc1"
    assert result["_rev"] == "2-new"


@pytest.mark.asyncio
async def test_save_document_if_revision_matches_conflict(couchdb_client: CouchDBClient) -> None:
    """Test revision-checked save raises DocumentConflictError on 409."""
    couchdb_client._db_name = "test_db"  # noqa: SLF001

    mock_response = AsyncMock()
    mock_response.status = 409

    mock_session = MagicMock()
    mock_session.put.return_value.__aenter__.return_value = mock_response
    mock_session.put.return_value.__aexit__.return_value = None
    _inject_handles(couchdb_client, session=mock_session)

    with pytest.raises(DocumentConflictError, match="Conflict updating document doc1"):
        await couchdb_client.save_document_if_revision_matches(
            "doc1",
            {"type": "harvest", "statistics": {"arcs_submitted": 1}},
            expected_rev="1-old",
        )


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
        _inject_handles(couchdb_client, couch=mock_instance)

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
        _inject_handles(couchdb_client, couch=mock_instance)

        # Should not raise
        await couchdb_client.ensure_system_databases()

        assert mock_instance.create.call_count == 3  # noqa: PLR2004


@pytest.mark.asyncio
async def test_couchdb_client_connect_race_condition(couchdb_client: CouchDBClient) -> None:
    """Test connection with race condition where DB is created between check and create."""
    mock_instance = MagicMock()
    mock_db = AsyncMock()
    mock_instance.__getitem__ = AsyncMock(
        side_effect=[
            AsyncMock(),
            AsyncMock(),
            AsyncMock(),
            NotFoundError("Not Found"),
            mock_db,
        ]
    )
    mock_instance.create = AsyncMock(side_effect=PreconditionFailedError("Already exists"))
    mock_instance.close = AsyncMock()
    mock_session = MagicMock()
    mock_session.closed = True
    mock_session.close = AsyncMock()

    with (
        patch("middleware.api.document_store.couchdb_client.CouchDB", return_value=mock_instance),
        patch("middleware.api.document_store.couchdb_client.Database", return_value=MagicMock()),
        patch("middleware.api.document_store.couchdb_client.aiohttp.ClientSession", return_value=mock_session),
    ):
        await couchdb_client.connect()

    assert couchdb_client._db == mock_db  # noqa: SLF001
    assert mock_instance.__getitem__.call_count == 5  # noqa: PLR2004
    mock_instance.create.assert_called_once_with(couchdb_client._db_name)  # noqa: SLF001
