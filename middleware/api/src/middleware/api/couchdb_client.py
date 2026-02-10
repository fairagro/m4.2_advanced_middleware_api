"""CouchDB client wrapper for the FAIRagro Middleware.

Provides async access to CouchDB for ARC and Harvest document storage.
"""

import logging
from typing import Any

from aiocouch import CouchDB, Database
from aiocouch.exception import NotFoundError

from .config import CouchDBConfig

logger = logging.getLogger(__name__)


class CouchDBClient:
    """Async CouchDB client wrapper."""

    def __init__(self, url: str, user: str | None = None, password: str | None = None):
        """Initialize CouchDB client.

        Args:
            url: CouchDB URL (e.g., http://localhost:5984)
            user: CouchDB username (optional)
            password: CouchDB password (optional)
        """
        self.url = url
        self.user = user
        self.password = password
        self._client: CouchDB | None = None
        self._db: Database | None = None

    @property
    def client(self) -> CouchDB | None:
        """Get the underlying CouchDB client.

        Returns:
            CouchDB: The aiocouch client instance, or None if not connected.
        """
        return self._client

    @classmethod
    def from_config(cls, config: CouchDBConfig) -> "CouchDBClient":
        """Create a CouchDBClient from a configuration object.

        Args:
            config: CouchDB configuration

        Returns:
            CouchDBClient: Initialized client
        """
        return cls(
            url=config.url,
            user=config.user,
            password=config.password.get_secret_value() if config.password else None,
        )

    async def connect(self, db_name: str = "fairagro_middleware", setup_system: bool = False) -> None:
        """Connect to CouchDB and ensure database exists.

        Args:
            db_name: Database name to use
            setup_system: Whether to ensure system databases exist (default: False)
        """
        if self._client is not None:
            return

        try:
            self._client = CouchDB(
                self.url,
                user=self.user,
                password=self.password,
            )

            if setup_system:
                await self.ensure_system_databases()

            # Check if database exists, create if not
            try:
                self._db = await self._client[db_name]
                logger.info("Connected to CouchDB database: %s", db_name)
            except NotFoundError:
                self._db = await self._client.create(db_name)
                logger.info("Created CouchDB database: %s", db_name)

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
                logger.info("Creating missing system database: %s", db)
                await self._client.create(db)
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.warning("Failed to check/create system database %s: %s", db, e)

    async def close(self) -> None:
        """Close CouchDB connection."""
        if self._client:
            try:
                await self._client.close()
                logger.info("Closed CouchDB connection")
            finally:
                self._client = None
                self._db = None

    def get_db(self) -> Database | None:
        """Get the connected database instance.

        Returns:
            Database: The connected database instance, or None if not connected.
        """
        return self._db

    async def health_check(self) -> bool:
        """Check if CouchDB is accessible.

        Returns:
            True if CouchDB is healthy, False otherwise
        """
        try:
            if not self._client:
                return False
            # Check the server info as a health check
            await self._client.info()
            return True
        except Exception as e:  # pylint: disable=broad-exception-caught
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

    async def find(self, selector: dict[str, Any], limit: int = 100) -> list[dict[str, Any]]:
        """Find documents using a Mango query selector.

        Args:
            selector: Mango query selector
            limit: Maximum number of results

        Returns:
            List of matching documents
        """
        if not self._db:
            raise RuntimeError("Not connected to CouchDB")

        # Use the find method of the database
        result = self._db.find(selector, limit=limit)
        return [dict(doc) async for doc in result]

    async def __aenter__(self) -> "CouchDBClient":
        """Async context manager entry."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any | None,
    ) -> None:
        """Async context manager exit."""
        await self.close()
