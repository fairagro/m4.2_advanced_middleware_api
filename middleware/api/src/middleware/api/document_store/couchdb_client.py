"""CouchDB client wrapper for the FAIRagro Middleware.

Provides async access to CouchDB for ARC and Harvest document storage.
"""

import logging
from collections.abc import Awaitable, Callable
from http import HTTPStatus
from typing import Any, Self, TypeVar, cast
from urllib.parse import quote

import aiohttp
from aiocouch import CouchDB, Database
from aiocouch.exception import ConflictError, NotFoundError, PreconditionFailedError
from aiocouch.remote import RemoteServer

from middleware.api.document_store.config import CouchDBConfig
from middleware.api.document_store.errors import DocumentStoreUnavailableError
from middleware.shared.json_types import CouchDbDocument, JsonObject, JsonValue

logger = logging.getLogger(__name__)

_PATCH_MARKER = "_fairagro_encode_basic_auth"

_T = TypeVar("_T")


class DatabaseMissingError(RuntimeError):
    """Configured application database does not exist on the CouchDB server."""


async def _async_noop() -> None:
    """Default re-init hook (no work)."""


def _patch_aiocouch_aiohttp_auth() -> None:
    """Make aiocouch use ``encode_basic_auth`` instead of deprecated ``BasicAuth``.

    aiocouch 4.0.1 still builds ``aiohttp.BasicAuth`` and passes ``auth=`` into
    ``ClientSession``. Both are deprecated in aiohttp 3.14+ (removed in 4.0) and
    spam pytest with DeprecationWarnings on every connect. Patch once per process
    until upstream adopts the new API.
    """
    if getattr(RemoteServer.__init__, _PATCH_MARKER, False):
        return

    def patched_init(  # noqa: PLR0913 — extends upstream RemoteServer.__init__ with explicit session headers
        self: RemoteServer,
        server: str,
        *,
        user: str | None = None,
        password: str | None = None,
        cookie: str | None = None,
        headers: dict[str, str] | None = None,
        **client_session_kwargs: Any,
    ) -> None:
        self._server = server
        session_headers: dict[str, str] = dict(headers or {})
        extra_headers = client_session_kwargs.pop("headers", None)
        if isinstance(extra_headers, dict):
            session_headers.update(extra_headers)
        if cookie:
            session_headers["Cookie"] = "AuthSession=" + cookie
        if user is not None and password is not None:
            session_headers["Authorization"] = aiohttp.encode_basic_auth(user, password)
        # Upstream aiocouch still passes deprecated auth=; never forward it.
        client_session_kwargs.pop("auth", None)
        self._http_session = aiohttp.ClientSession(
            headers=session_headers if session_headers else None,
            **client_session_kwargs,
        )

    setattr(patched_init, _PATCH_MARKER, True)
    RemoteServer.__init__ = patched_init  # type: ignore[method-assign, assignment]


class DocumentConflictError(RuntimeError):
    """Raised when a document update conflicts with a newer CouchDB revision."""


class CouchDBClient:
    """Async CouchDB client wrapper."""

    def __init__(self, config: CouchDBConfig) -> None:
        """Initialize CouchDB client.

        Network handles (``_client``, ``_db``, ``_session``) are opened in
        :meth:`connect` — ``aiohttp.ClientSession`` / aiocouch require a running
        event loop, so they cannot be created in sync ``__init__``.

        Args:
            config: CouchDB configuration.
        """
        self._url = config.url
        self._db_name = config.db_name
        self._user = config.user
        self._password = config.password.get_secret_value() if config.password else None
        self._default_query_limit = config.default_query_limit
        self._max_save_retries = config.max_save_retries
        self._reinit_hook: Callable[[], Awaitable[None]] = _async_noop
        self._inside_reinit = False
        self._connected = False
        self._handles: tuple[CouchDB, Database, aiohttp.ClientSession] | None = None

    @property
    def _client(self) -> CouchDB:
        """CouchDB server client via aiocouch (non-optional once connected)."""
        return self._require_handles()[0]

    @_client.setter
    def _client(self, value: CouchDB) -> None:
        handles = self._require_handles()
        self._handles = (value, handles[1], handles[2])

    @property
    def _db(self) -> Database:
        """Application database handle (non-optional once connected)."""
        return self._require_handles()[1]

    @_db.setter
    def _db(self, value: Database) -> None:
        handles = self._require_handles()
        self._handles = (handles[0], value, handles[2])

    @property
    def _session(self) -> aiohttp.ClientSession:
        """Shared HTTP session for raw CouchDB calls (non-optional once connected)."""
        return self._require_handles()[2]

    @_session.setter
    def _session(self, value: aiohttp.ClientSession) -> None:
        handles = self._require_handles()
        self._handles = (handles[0], handles[1], value)

    def _require_handles(self) -> tuple[CouchDB, Database, aiohttp.ClientSession]:
        if self._handles is None:
            raise RuntimeError("Not connected to CouchDB")
        return self._handles

    def _require_connected(self) -> None:
        """Raise if ``connect()`` has not completed successfully."""
        if not self._connected or self._handles is None:
            raise RuntimeError("Not connected to CouchDB")

    def _new_handles(self) -> tuple[CouchDB, Database, aiohttp.ClientSession]:
        """Build a fresh aiocouch client, DB handle, and HTTP session.

        Must run on a running event loop (``connect`` / ``close``).
        """
        _patch_aiocouch_aiohttp_auth()
        client = CouchDB(
            self._url,
            user=self._user,
            password=self._password,
        )
        db = Database(client, self._db_name)
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._user is not None and self._password is not None:
            headers["Authorization"] = aiohttp.encode_basic_auth(self._user, self._password)
        session = aiohttp.ClientSession(headers=headers)
        return client, db, session

    def set_reinit_hook(self, hook: Callable[[], Awaitable[None]] | None) -> None:
        """Register async callback that recreates DB + indices after a wipe.

        Passing ``None`` restores the no-op default hook.
        """
        self._reinit_hook = hook if hook is not None else _async_noop

    @classmethod
    def from_config(cls, config: CouchDBConfig) -> Self:
        """Create a CouchDBClient from a configuration object.

        Args:
            config: CouchDB configuration

        Returns:
            CouchDBClient: Initialized client
        """
        return cls(config)

    async def connect(self) -> None:
        """Connect to CouchDB and ensure database exists."""
        if self._connected:
            return

        try:
            self._handles = self._new_handles()

            # Ensure system databases exist (required for CouchDB 3.x)
            await self.ensure_system_databases()

            # Check if database exists, create if not
            try:
                self._db = await self._client[self._db_name]
                logger.info("Connected to CouchDB database: %s", self._db_name)
            except NotFoundError:
                try:
                    self._db = await self._client.create(self._db_name)
                    logger.info("Created CouchDB database: %s", self._db_name)
                except PreconditionFailedError:
                    # Race condition: another process created it in the meantime
                    self._db = await self._client[self._db_name]
                    logger.info("Connected to CouchDB database (created by other process): %s", self._db_name)
            self._connected = True

        except Exception as e:
            logger.error("Failed to connect to CouchDB: %s", e)
            await self._discard_handles()
            raise

    async def _discard_handles(self) -> None:
        """Close and drop network handles without requiring a successful connect."""
        handles = self._handles
        self._handles = None
        self._connected = False
        if handles is None:
            return
        client, _db, session = handles
        try:
            if not session.closed:
                await session.close()
        except Exception as e:  # noqa: BLE001
            logger.warning("Error closing CouchDB HTTP session: %s", e)
        try:
            await client.close()
        except Exception as e:  # noqa: BLE001
            logger.warning("Error closing CouchDB client: %s", e)

    async def ensure_system_databases(self) -> None:
        """Ensure CouchDB system databases exist.

        CouchDB 3.x requires _users, _replicator, and _global_changes to be present.
        """
        self._require_handles()
        system_dbs = ["_users", "_replicator", "_global_changes"]
        for db in system_dbs:
            try:
                await self._client[db]
                logger.debug("System database exists: %s", db)
            except NotFoundError:
                try:
                    logger.info("Creating missing system database: %s", db)
                    await self._client.create(db)
                except PreconditionFailedError:
                    logger.debug("System database %s was created by another process", db)
            except Exception as e:  # noqa: BLE001
                logger.warning("Failed to check/create system database %s: %s", db, e)

    async def close(self) -> None:
        """Close CouchDB connection."""
        if self._handles is None:
            return
        await self._discard_handles()
        logger.info("Closed CouchDB connection")

    async def application_database_exists(self) -> bool:
        """Return whether the configured application database exists on the server."""
        if self._handles is None:
            return False
        try:
            await self._client[self._db_name]
            return True
        except NotFoundError:
            return False
        except Exception as e:  # noqa: BLE001
            logger.error("Failed to probe application database %s: %s", self._db_name, e)
            return False

    async def _raise_if_database_missing(self, cause: BaseException | None = None) -> None:
        """Raise :class:`DatabaseMissingError` when the application DB is gone."""
        if await self.application_database_exists():
            return
        message = f"CouchDB application database {self._db_name!r} does not exist"
        if cause is not None:
            raise DatabaseMissingError(message) from cause
        raise DatabaseMissingError(message)

    async def _with_db_recovery(self, operation: Callable[[], Awaitable[_T]]) -> _T:
        """Run *operation*; on missing app DB, re-init once (via hook) and retry."""
        try:
            return await operation()
        except DatabaseMissingError:
            if self._inside_reinit:
                raise DocumentStoreUnavailableError(
                    "CouchDB application database is missing and cannot be re-initialized"
                ) from None
            logger.warning(
                "CouchDB application database %s missing; running guarded re-initialization",
                self._db_name,
            )
            try:
                await self._reinit_hook()
            except Exception as e:
                raise DocumentStoreUnavailableError(
                    "CouchDB re-initialization failed after application database disappeared"
                ) from e
            try:
                return await operation()
            except DatabaseMissingError as e:
                raise DocumentStoreUnavailableError(
                    "CouchDB application database still missing after re-initialization"
                ) from e

    async def health_check(self) -> bool:
        """Check whether the configured application database exists.

        Runs the re-init hook first (no-op by default; store registers ensure) so
        readiness can recover after a wipe without a write request.

        Returns:
            True if connected and the application database exists.
        """
        try:
            if not self._inside_reinit:
                try:
                    await self._reinit_hook()
                except Exception as e:  # noqa: BLE001
                    logger.error("CouchDB re-initialization during health check failed: %s", e)
                    return False
            if not self._connected:
                return False
            return await self.application_database_exists()
        except Exception as e:  # noqa: BLE001
            logger.error("CouchDB health check failed: %s", e)
            return False

    async def get_document(self, doc_id: str) -> CouchDbDocument | None:
        """Get a document by ID.

        Args:
            doc_id: Document ID

        Returns:
            Document data as dict, or None if not found
        """

        async def _op() -> CouchDbDocument | None:
            self._require_connected()
            try:
                doc = await self._db[doc_id]
                return dict(doc)
            except NotFoundError as err:
                await self._raise_if_database_missing(err)
                return None

        return await self._with_db_recovery(_op)

    async def create_document_exclusive(self, doc_id: str, data: CouchDbDocument) -> CouchDbDocument:
        """Create a document only if it does not already exist.

        Unlike :meth:`save_document`, a conflict does not fall through to an update
        of the existing document.

        Raises:
            DocumentConflictError: If the document already exists or create races.
        """

        async def _op() -> CouchDbDocument:
            self._require_connected()
            content = {k: v for k, v in data.items() if k not in {"_id", "_rev"}}
            try:
                doc = await self._db.create(doc_id, data=content)
                await doc.save()
            except ConflictError as err:
                raise DocumentConflictError(f"Document {doc_id} already exists") from err
            except NotFoundError as err:
                await self._raise_if_database_missing(err)
                raise
            return dict(doc)

        return await self._with_db_recovery(_op)

    async def save_document(
        self,
        doc_id: str,
        data: CouchDbDocument,
        pre_save_validator: Callable[[CouchDbDocument], None] | None = None,
    ) -> CouchDbDocument:
        """Save or update a document with optimistic-concurrency retry.

        ``_id`` and ``_rev`` are stripped from *data* before writing: the
        revision is always sourced from a fresh CouchDB fetch so that a stale
        ``_rev`` carried in *data* cannot trigger a spurious 409 Conflict.

        On a genuine concurrent-write conflict the operation is retried up to
        ``max_save_retries`` times (re-fetching the document on each attempt)
        before raising :class:`DocumentConflictError`.

        *pre_save_validator* is called with the **freshly fetched** document dict
        on every attempt (including retries).  Raising from the validator aborts
        the write immediately without retrying — use this to enforce invariants
        that must be checked against the current CouchDB state (e.g. detecting a
        conflicting re-submission of the same ARC in one harvest after a
        concurrent write has landed).

        Args:
            doc_id: Document ID
            data: Document data (``_id`` / ``_rev`` are ignored if present)
            pre_save_validator: Optional callable that receives the current
                document dict and may raise to abort the write.

        Returns:
            Saved document with ``_id`` and ``_rev``

        Raises:
            DocumentConflictError: If the conflict persists after all retries.
        """

        async def _op() -> CouchDbDocument:
            self._require_connected()

            # Strip CouchDB internal fields: we always re-fetch to get the current
            # _rev, so any _rev/_id carried in `data` would be stale and would
            # cause a spurious 409 on concurrent writes.
            content = {k: v for k, v in data.items() if k not in {"_id", "_rev"}}

            for attempt in range(1, self._max_save_retries + 1):
                try:
                    try:
                        # Attempt to fetch the document (update path)
                        doc = await self._db[doc_id]
                        if pre_save_validator is not None:
                            pre_save_validator(dict(doc))
                        doc.update(content)
                        await doc.save()
                    except NotFoundError as err:
                        await self._raise_if_database_missing(err)
                        # Document does not exist yet (create path)
                        # NOTE: aiocouch.Database.create() only creates a local object;
                        # doc.save() is required to actually PUT the document to CouchDB.
                        doc = await self._db.create(doc_id, data=content)
                        await doc.save()
                    return dict(doc)
                except ConflictError as err:
                    if attempt >= self._max_save_retries:
                        raise DocumentConflictError(
                            f"Concurrent modification conflict for document {doc_id} "
                            f"after {self._max_save_retries} retries"
                        ) from err
                    logger.debug(
                        "CouchDB write conflict on %s (attempt %d/%d), retrying",
                        doc_id,
                        attempt,
                        self._max_save_retries,
                    )

            raise DocumentConflictError(f"Failed to save document {doc_id}")  # pragma: no cover

        return await self._with_db_recovery(_op)

    async def delete_document(self, doc_id: str) -> bool:
        """Delete a document.

        Args:
            doc_id: Document ID

        Returns:
            True if deleted, False if not found
        """

        async def _op() -> bool:
            self._require_connected()
            try:
                doc = await self._db[doc_id]
                await doc.delete()
                return True
            except NotFoundError as err:
                await self._raise_if_database_missing(err)
                return False

        return await self._with_db_recovery(_op)

    async def find(
        self,
        selector: JsonObject,
        limit: int | None = None,
        skip: int = 0,
    ) -> list[CouchDbDocument]:
        """Find documents using a Mango query selector.

        Args:
            selector: Mango query selector
            limit: Maximum number of results to return per call.
                   Defaults to the instance's ``default_query_limit``.
            skip: Number of results to skip (for pagination)

        Returns:
            List of matching documents
        """

        async def _op() -> list[CouchDbDocument]:
            self._require_connected()
            try:
                effective_limit = limit if limit is not None else self._default_query_limit
                result = self._db.find(selector, limit=effective_limit, skip=skip)
                docs = [dict(doc) async for doc in result]
            except NotFoundError as err:
                await self._raise_if_database_missing(err)
                raise

            if limit is None and len(docs) == effective_limit:
                logger.warning(
                    "CouchDB find() returned exactly %d documents for selector %s — "
                    "results may be silently truncated. Use skip/limit for pagination.",
                    effective_limit,
                    selector,
                )

            return docs

        return await self._with_db_recovery(_op)

    async def find_page(
        self,
        selector: JsonObject,
        *,
        limit: int,
        bookmark: str | None = None,
        sort: list[JsonObject] | None = None,
    ) -> tuple[list[CouchDbDocument], str | None]:
        """Fetch one Mango page using bookmark pagination (not ``skip``).

        Offset (``skip``) paging over unordered or mutating result sets can omit
        or repeat documents. CouchDB bookmarks are the stable cursor for
        multi-page catalog scans.

        Args:
            selector: Mango query selector.
            limit: Maximum documents for this page.
            bookmark: Opaque cursor from a previous ``find_page`` call.
            sort: Optional Mango ``sort`` clause (must match an index).

        Returns:
            ``(docs, next_bookmark)``. ``next_bookmark`` is ``None`` when the
            response omits a bookmark; callers should stop when ``docs`` is
            empty or shorter than ``limit``.
        """
        if limit < 1:
            msg = "limit must be >= 1"
            raise ValueError(msg)

        async def _op() -> tuple[list[CouchDbDocument], str | None]:
            self._require_connected()
            if not self._db_name:
                raise RuntimeError("Database name is not set")

            payload: JsonObject = {
                "selector": selector,
                "limit": limit,
            }
            if bookmark is not None:
                payload["bookmark"] = bookmark
            if sort is not None:
                payload["sort"] = cast(JsonValue, sort)

            url = f"{self._url}/{self._db_name}/_find"
            session = self._get_session()
            async with session.post(url, json=payload) as resp:
                if resp.status == HTTPStatus.NOT_FOUND:
                    await self._raise_if_database_missing()
                if resp.status != HTTPStatus.OK:
                    text = await resp.text()
                    logger.error("CouchDB _find page failed: %s", text)
                    raise RuntimeError(f"CouchDB _find failed with status {resp.status}: {text}")
                response_data = await resp.json()

            docs_raw = response_data.get("docs", [])
            docs: list[CouchDbDocument] = [dict(doc) for doc in docs_raw]
            next_bookmark = response_data.get("bookmark")
            return docs, next_bookmark if isinstance(next_bookmark, str) else None

        return await self._with_db_recovery(_op)

    async def find_projected(
        self,
        selector: JsonObject,
        fields: list[str],
        limit: int | None = None,
        skip: int = 0,
    ) -> list[CouchDbDocument]:
        """Find documents using CouchDB _find with explicit field projection.

        This method uses the raw HTTP endpoint because aiocouch's ``Database.find``
        returns full ``Document`` objects and therefore does not support the
        ``fields`` parameter.

        Args:
            selector: Mango query selector.
            fields: List of fields to return (CouchDB ``fields`` projection).
            limit: Maximum number of results to return per call.
                   Defaults to the instance's ``default_query_limit``.
            skip: Number of results to skip (for pagination).

        Returns:
            List of projected documents.
        """

        async def _op() -> list[CouchDbDocument]:
            self._require_connected()
            if not self._db_name:
                raise RuntimeError("Database name is not set")

            effective_limit = limit if limit is not None else self._default_query_limit

            payload: JsonObject = {
                "selector": selector,
                "fields": cast(JsonValue, fields),
                "limit": effective_limit,
                "skip": skip,
            }

            url = f"{self._url}/{self._db_name}/_find"
            session = self._get_session()
            async with session.post(url, json=payload) as resp:
                if resp.status == HTTPStatus.NOT_FOUND:
                    await self._raise_if_database_missing()
                if resp.status != HTTPStatus.OK:
                    text = await resp.text()
                    logger.error("CouchDB _find with projection failed: %s", text)
                    raise RuntimeError(f"CouchDB _find failed with status {resp.status}: {text}")

                response_data = await resp.json()

            docs_raw = response_data.get("docs", [])
            docs: list[CouchDbDocument] = [dict(doc) for doc in docs_raw]

            if limit is None and len(docs) == effective_limit:
                logger.warning(
                    "CouchDB find_projected() returned exactly %d documents for selector %s — "
                    "results may be silently truncated. Use skip/limit for pagination.",
                    effective_limit,
                    selector,
                )

            return docs

        return await self._with_db_recovery(_op)

    async def save_document_if_revision_matches(
        self,
        doc_id: str,
        data: CouchDbDocument,
        *,
        expected_rev: str,
    ) -> CouchDbDocument:
        """Save a document only if the expected revision still matches.

        Uses raw ``PUT /{db}/{docid}`` to allow optimistic-concurrency handling
        in higher layers (retry on 409 Conflict).

        Args:
            doc_id: Document ID.
            data: Complete document payload to save.
            expected_rev: Revision expected by the caller.

        Returns:
            Saved document payload including updated ``_rev``.

        Raises:
            DocumentConflictError: If CouchDB returns 409 conflict.
            RuntimeError: For non-success HTTP errors.
        """

        async def _op() -> CouchDbDocument:
            self._require_connected()
            if not self._db_name:
                raise RuntimeError("Database name is not set")

            payload = dict(data)
            payload["_id"] = doc_id
            payload["_rev"] = expected_rev

            encoded_doc_id = quote(doc_id, safe="")
            url = f"{self._url}/{self._db_name}/{encoded_doc_id}"
            session = self._get_session()

            async with session.put(url, json=payload) as resp:
                if resp.status in {HTTPStatus.CREATED, HTTPStatus.ACCEPTED, HTTPStatus.OK}:
                    response_data = await resp.json()
                    new_rev = response_data.get("rev")
                    if isinstance(new_rev, str):
                        payload["_rev"] = new_rev
                    return payload

                if resp.status == HTTPStatus.CONFLICT:
                    raise DocumentConflictError(f"Conflict updating document {doc_id}")

                if resp.status == HTTPStatus.NOT_FOUND:
                    await self._raise_if_database_missing()

                text = await resp.text()
                raise RuntimeError(f"Failed to update document {doc_id}: {resp.status} {text}")

        return await self._with_db_recovery(_op)

    def _get_session(self) -> aiohttp.ClientSession:
        """Return the shared aiohttp session used for raw CouchDB HTTP calls."""
        return self._session

    async def create_index(self, fields: list[str], name: str | None = None) -> None:
        """Create a Mango index if it doesn't exist.

        Args:
            fields: List of fields to index
            name: Optional name for the index
        """

        async def _op() -> None:
            self._require_connected()

            index_def: JsonObject = {
                "index": cast(JsonValue, {"fields": fields}),
                "type": "json",
            }
            if name:
                index_def["name"] = name

            if not self._db_name:
                raise RuntimeError("Database name is not set")
            url = f"{self._url}/{self._db_name}/_index"

            session = self._get_session()
            async with session.post(url, json=index_def) as resp:
                if resp.status == HTTPStatus.NOT_FOUND:
                    await self._raise_if_database_missing()
                if resp.status not in {HTTPStatus.OK, HTTPStatus.CREATED}:
                    text = await resp.text()
                    logger.error("Failed to create index on %s: %s", fields, text)
                else:
                    logger.info("Ensured index on %s (name: %s)", fields, name)

        await self._with_db_recovery(_op)
