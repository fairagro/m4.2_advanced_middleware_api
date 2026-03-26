"""CouchDB client wrapper for the FAIRagro Middleware.

Provides async access to CouchDB for ARC and Harvest document storage.
"""

import logging
from http import HTTPStatus
from typing import Any, Self

import aiohttp
from aiocouch import CouchDB, Database
from aiocouch.exception import NotFoundError, PreconditionFailedError

from middleware.api.document_store.config import CouchDBConfig

logger = logging.getLogger(__name__)


class CouchDBClient:
    """Async CouchDB client wrapper."""

    def __init__(
        self,
        url: str,
        db_name: str,
        user: str | None = None,
        password: str | None = None,
        *,
        default_query_limit: int,
    ):
        """Initialize CouchDB client.

        Args:
            url: CouchDB URL (e.g., http://localhost:5984)
            db_name: Database name to use
            user: CouchDB username (optional)
            password: CouchDB password (optional)
            default_query_limit: Default maximum number of documents returned by a Mango query.
        """
        self._url = url
        self._db_name = db_name
        self._user = user
        self._password = password
        self._default_query_limit = default_query_limit
        self._client: CouchDB | None = None
        self._db: Database | None = None
        # Shared HTTP session for raw CouchDB calls (e.g. index management).
        # Created lazily on first use; closed alongside the aiocouch client.
        self._session: aiohttp.ClientSession | None = None

    @classmethod
    def from_config(cls, config: CouchDBConfig) -> Self:
        """Create a CouchDBClient from a configuration object.

        Args:
            config: CouchDB configuration

        Returns:
            CouchDBClient: Initialized client
        """
        return cls(
            url=config.url,
            db_name=config.db_name,
            user=config.user,
            password=config.password.get_secret_value() if config.password else None,
            default_query_limit=config.default_query_limit,
        )

    async def connect(self) -> None:
        """Connect to CouchDB and ensure database exists."""
        if self._client is not None:
            return

        try:
            self._client = CouchDB(
                self._url,
                user=self._user,
                password=self._password,
            )

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

        except Exception as e:
            logger.error("Failed to connect to CouchDB: %s", e)
            raise

    async def ensure_system_databases(self) -> None:
        """Ensure CouchDB system databases exist.

        CouchDB 3.x requires _users, _replicator, and _global_changes to be present.
        """
        if not self._client:
            raise RuntimeError("Not connected to CouchDB server")

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
        if self._session:
            try:
                await self._session.close()
            finally:
                self._session = None
        if self._client:
            try:
                await self._client.close()
                logger.info("Closed CouchDB connection")
            finally:
                self._client = None
                self._db = None

    async def health_check(self) -> bool:
        """Check if CouchDB is accessible.

        Returns:
            True if CouchDB is healthy, False otherwise
        """
        try:
            if not self._client:
                return False
            # Check the server info as a health check
            # aiocouch's info() is async
            await self._client.info()
            return True
        except Exception as e:  # noqa: BLE001
            logger.error("CouchDB health check failed: %s", e)
            return False

    async def get_document(self, doc_id: str) -> dict[str, Any] | None:
        """Get a document by ID.

        Args:
            doc_id: Document ID

        Returns:
            Document data as dict, or None if not found
        """
        if not self._db:
            raise RuntimeError("Not connected to CouchDB")

        try:
            doc = await self._db[doc_id]
            return dict(doc)
        except NotFoundError:
            return None

    async def save_document(self, doc_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """Save or update a document.

        Args:
            doc_id: Document ID
            data: Document data (without _id)

        Returns:
            Saved document with _id and _rev
        """
        if not self._db:
            raise RuntimeError("Not connected to CouchDB")

        try:
            # Attempt to fetch the document
            doc = await self._db[doc_id]
            # If successful, it's an update
            doc.update(data)
            await doc.save()
        except NotFoundError:
            # If not found, it's a create
            doc = await self._db.create(doc_id, data=data)

        return dict(doc)

    async def delete_document(self, doc_id: str) -> bool:
        """Delete a document.

        Args:
            doc_id: Document ID

        Returns:
            True if deleted, False if not found
        """
        if not self._db:
            raise RuntimeError("Not connected to CouchDB")

        try:
            doc = await self._db[doc_id]
            await doc.delete()
            return True
        except NotFoundError:
            return False

    async def find(
        self,
        selector: dict[str, Any],
        limit: int | None = None,
        skip: int = 0,
        fields: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Find documents using a Mango query selector.

        Args:
            selector: Mango query selector
            limit: Maximum number of results to return per call.
                   Defaults to the instance's ``default_query_limit``.
            skip: Number of results to skip (for pagination)
            fields: Optional list of fields to include in results (projection).
                    When set, ``arc_content`` and other large fields can be
                    excluded to reduce memory and network usage.

        Returns:
            List of matching documents
        """
        if not self._db:
            raise RuntimeError("Not connected to CouchDB")

        effective_limit = limit if limit is not None else self._default_query_limit
        # aiocouch's find passes extra kwargs through to the _find body.
        kwargs: dict[str, Any] = {"limit": effective_limit, "skip": skip}
        if fields is not None:
            kwargs["fields"] = fields

        result = self._db.find(selector, **kwargs)
        docs = [dict(doc) async for doc in result]

        if len(docs) == effective_limit:
            logger.warning(
                "CouchDB find() returned exactly %d documents for selector %s — "
                "results may be silently truncated. Use skip/limit for pagination.",
                effective_limit,
                selector,
            )

        return docs

    def _get_session(self) -> aiohttp.ClientSession:
        """Return the shared aiohttp session, creating it on first call."""
        if self._session is None:
            auth = (
                aiohttp.BasicAuth(self._user, self._password)
                if self._user is not None and self._password is not None
                else None
            )
            self._session = aiohttp.ClientSession(
                auth=auth,
                headers={"Content-Type": "application/json"},
            )
        return self._session

    async def create_index(self, fields: list[str], name: str | None = None) -> None:
        """Create a Mango index if it doesn't exist.

        Args:
            fields: List of fields to index
            name: Optional name for the index
        """
        if not self._db:
            raise RuntimeError("Not connected to CouchDB")

        index_def: dict[str, Any] = {
            "index": {"fields": fields},
            "type": "json",
        }
        if name:
            index_def["name"] = name

        if not self._db_name:
            raise RuntimeError("Database name is not set")
        url = f"{self._url}/{self._db_name}/_index"

        session = self._get_session()
        async with session.post(url, json=index_def) as resp:
            if resp.status not in {HTTPStatus.OK, HTTPStatus.CREATED}:
                text = await resp.text()
                logger.error("Failed to create index on %s: %s", fields, text)
            else:
                logger.info("Ensured index on %s (name: %s)", fields, name)
