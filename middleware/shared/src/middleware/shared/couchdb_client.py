"""CouchDB client wrapper for the FAIRagro Middleware.

Provides async access to CouchDB for ARC and Harvest document storage.
"""

import logging
from typing import Any

from aiocouch import CouchDB, Database, Document
from aiocouch.exception import NotFoundError

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

    async def connect(self, db_name: str = "fairagro_middleware") -> None:
        """Connect to CouchDB and ensure database exists.

        Args:
            db_name: Database name to use
        """
        try:
            self._client = CouchDB(
                self.url,
                user=self.user,
                password=self.password,
            )
            
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

    async def close(self) -> None:
        """Close CouchDB connection."""
        if self._client:
            await self._client.close()
            self._client = None
            self._db = None
            logger.info("Closed CouchDB connection")

    async def health_check(self) -> bool:
        """Check if CouchDB is accessible.

        Returns:
            True if CouchDB is healthy, False otherwise
        """
        try:
            if not self._client:
                return False
            # Try to access the root endpoint
            await self._client.get()
            return True
        except Exception as e:
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

        # Check if document exists
        existing_doc = await self.get_document(doc_id)
        
        if existing_doc:
            # Update existing document
            doc = await self._db[doc_id]
            doc.update(data)
            await doc.save()
        else:
            # Create new document
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
        result = await self._db.find(selector, limit=limit)
        return [dict(doc) async for doc in result]

    async def __aenter__(self) -> "CouchDBClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()
