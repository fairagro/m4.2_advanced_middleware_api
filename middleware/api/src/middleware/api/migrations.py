"""Migration manager for CouchDB.

Handles schema-like changes (Views, Indexes, Design Documents) in CouchDB.
"""

import logging
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any

from aiocouch.exception import NotFoundError

from .couchdb_client import CouchDBClient

logger = logging.getLogger(__name__)


class BaseMigration(ABC):
    """Base class for all migrations."""

    @property
    @abstractmethod
    def migration_id(self) -> str:
        """Unique identifier for this migration (e.g., '20240205_create_arc_views')."""
        pass

    @abstractmethod
    async def apply(self, client: CouchDBClient) -> None:
        """Apply the migration."""
        pass


class MigrationManager:
    """Manager for CouchDB migrations."""

    _MIGRATIONS_DB = "_migrations"

    def __init__(self, client: CouchDBClient):
        """Initialize migration manager.

        Args:
            client: Connected CouchDBClient instance
        """
        self._client = client

    async def _ensure_migrations_db(self) -> None:
        """Ensure the migrations database exists."""
        # Note: CouchDBClient.connect handles its own primary DB, 
        # but here we might need to access the server-level client.
        server_client = self._client.client
        if not server_client:
            raise RuntimeError("CouchDB client not connected")
        
        try:
            await server_client[self._MIGRATIONS_DB]
        except NotFoundError:
            logger.info("Creating migrations database: %s", self._MIGRATIONS_DB)
            await server_client.create(self._MIGRATIONS_DB)

    async def is_applied(self, migration_id: str) -> bool:
        """Check if a migration has already been applied."""
        server_client = self._client.client
        if not server_client:
            raise RuntimeError("CouchDB client not connected")
        
        try:
            db = await server_client[self._MIGRATIONS_DB]
            await db[migration_id]
            return True
        except NotFoundError:
            return False

    async def mark_applied(self, migration_id: str) -> None:
        """Mark a migration as applied."""
        server_client = self._client.client
        if not server_client:
            raise RuntimeError("CouchDB client not connected")
        
        db = await server_client[self._MIGRATIONS_DB]
        await db.create(migration_id, data={
            "applied_at": datetime.now(UTC).isoformat() + "Z",
            "migration_id": migration_id
        })

    async def run_migrations(self, migrations: list[BaseMigration]) -> None:
        """Run a list of migrations if they haven't been applied yet."""
        await self._ensure_migrations_db()
        
        for migration in migrations:
            if await self.is_applied(migration.migration_id):
                logger.debug("Migration already applied: %s", migration.migration_id)
                continue
            
            logger.info("Applying migration: %s", migration.migration_id)
            try:
                await migration.apply(self._client)
                await self.mark_applied(migration.migration_id)
                logger.info("Successfully applied migration: %s", migration.migration_id)
            except Exception as e:
                logger.error("Failed to apply migration %s: %s", migration.migration_id, e)
                raise
