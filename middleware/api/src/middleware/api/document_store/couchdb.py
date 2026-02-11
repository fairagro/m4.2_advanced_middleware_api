"""CouchDB implementation of DocumentStore."""

import hashlib
import json
import logging
from datetime import UTC, datetime
from typing import Any

from middleware.api.config import CouchDBConfig
from middleware.api.couchdb_client import CouchDBClient
from middleware.api.schemas import ArcEventType
from middleware.api.schemas.arc_document import (
    ArcDocument,
    ArcEvent,
    ArcLifecycleStatus,
    ArcMetadata,
)
from middleware.api.utils import calculate_arc_id, extract_identifier

from . import ArcStoreResult, DocumentStore

logger = logging.getLogger(__name__)


class CouchDB(DocumentStore):
    """CouchDB implementation of DocumentStore."""

    def __init__(self, config: CouchDBConfig) -> None:
        """Initialize CouchDB document store.

        Args:
            config: CouchDB configuration
        """
        self._config = config
        self._db_name = config.db_name
        self._client = CouchDBClient.from_config(config)

    def _calculate_content_hash(self, arc_content: dict[str, Any]) -> str:
        """Calculate SHA256 hash of ARC content."""
        # Use sort_keys=True for canonical JSON representation
        json_str = json.dumps(arc_content, sort_keys=True)
        return hashlib.sha256(json_str.encode("utf-8")).hexdigest()

    async def store_arc(
        self,
        rdi: str,
        arc_content: dict[str, Any],
        harvest_id: str | None = None,
    ) -> ArcStoreResult:
        """Store ARC with change detection."""
        # Use the shared utility to calculate ARC ID
        identifier = extract_identifier(arc_content)
        arc_id = calculate_arc_id(identifier, rdi)
        doc_id = f"arc_{arc_id}"

        content_hash = self._calculate_content_hash(arc_content)
        now = datetime.now(UTC)

        # Check existing document
        existing_doc_dict = await self._client.get_document(doc_id)
        existing_doc = ArcDocument(**existing_doc_dict) if existing_doc_dict else None

        is_new = existing_doc is None
        has_changes = True  # Default to true for new

        if is_new:
            logger.info("ARC %s is new (hash: %s)", arc_id, content_hash[:8])
            metadata = ArcMetadata(
                arc_hash=content_hash,
                status=ArcLifecycleStatus.ACTIVE,
                first_seen=now,
                last_seen=now,
                last_harvest_id=harvest_id,
                events=[
                    ArcEvent(
                        timestamp=now, type=ArcEventType.ARC_CREATED, message="ARC first seen", harvest_id=harvest_id
                    )
                ],
            )
        else:
            # Check for changes
            assert existing_doc is not None
            has_changes = existing_doc.metadata.arc_hash != content_hash

            # Start with existing metadata
            metadata = existing_doc.metadata
            metadata.last_seen = now
            metadata.last_harvest_id = harvest_id

            if has_changes:
                logger.info("ARC %s changed (old: %s, new: %s)", arc_id, metadata.arc_hash[:8], content_hash[:8])
                metadata.arc_hash = content_hash
                metadata.status = ArcLifecycleStatus.ACTIVE  # Reset to active if it was missing/deleted
                metadata.missing_since = None

                # Append update event
                metadata.events.append(
                    ArcEvent(
                        timestamp=now,
                        type=ArcEventType.ARC_UPDATED,
                        message="ARC content updated",
                        harvest_id=harvest_id,
                    )
                )
            else:
                logger.debug("ARC %s unchanged", arc_id)
                # Optionally log "not changed" event, or just update timestamps?
                # For now, we don't log every "seen but unchanged" to avoid spam,
                # but we DO update last_seen (already done above).

                # If it was marked MISSING/DELETED but is now back (restored), we should note that
                if metadata.status in (ArcLifecycleStatus.MISSING, ArcLifecycleStatus.DELETED):
                    metadata.status = ArcLifecycleStatus.ACTIVE
                    metadata.missing_since = None
                    metadata.events.append(
                        ArcEvent(
                            timestamp=now,
                            type=ArcEventType.ARC_RESTORED,
                            message="ARC reappeared after being missing/deleted",
                            harvest_id=harvest_id,
                        )
                    )

        # Trim events (keep last max_event_log_size)
        if len(metadata.events) > self._config.max_event_log_size:
            metadata.events = metadata.events[-self._config.max_event_log_size :]

        # Create/Update document
        doc = ArcDocument(
            doc_id=doc_id,
            doc_rev=existing_doc.doc_rev if existing_doc else None,
            rdi=rdi,
            arc_content=arc_content,
            metadata=metadata,
        )
        # Hack to handle _rev which is aliased in Pydantic but needs to be passed to client logic
        # if we were using it manually.
        # But our client.save_document wraps simple dict PUT.
        # We need to pass the dict. Pydantic's model_dump(by_alias=True) will include _id and _rev.
        doc_data = doc.model_dump(by_alias=True, exclude_none=True)
        # _rev should not be in data if it's None (new doc)

        await self._client.save_document(doc_id, doc_data)

        return ArcStoreResult(arc_id=arc_id, is_new=is_new, has_changes=has_changes)

    async def get_arc_content(self, arc_id: str) -> dict[str, Any] | None:
        """Get raw ARC RO-Crate JSON."""
        doc_id = f"arc_{arc_id}"
        doc = await self._client.get_document(doc_id)
        return doc.get("arc_content") if doc else None

    async def get_metadata(self, arc_id: str) -> ArcMetadata | None:
        """Get ARC metadata without full content."""
        doc_id = f"arc_{arc_id}"
        doc = await self._client.get_document(doc_id)
        if doc and "metadata" in doc:
            return ArcMetadata(**doc["metadata"])
        return None

    async def add_event(self, arc_id: str, event: ArcEvent) -> None:
        """Append event to ARC event log."""
        doc_id = f"arc_{arc_id}"
        doc_dict = await self._client.get_document(doc_id)

        if not doc_dict:
            logger.warning("Attempted to add event to non-existent ARC %s", arc_id)
            return

        doc = ArcDocument(**doc_dict)
        doc.metadata.events.append(event)

        # Trim events
        if len(doc.metadata.events) > self._config.max_event_log_size:
            doc.metadata.events = doc.metadata.events[-self._config.max_event_log_size :]

        doc_data = doc.model_dump(by_alias=True, exclude_none=True)
        await self._client.save_document(doc_id, doc_data)

    async def health_check(self) -> bool:
        """Check if document store is reachable."""
        return await self._client.health_check()

    async def setup(self, setup_system: bool = False) -> None:
        """Initialize CouchDB and ensure databases exist.

        Args:
            setup_system: Whether to ensure system databases exist.
        """
        await self._client.connect(db_name=self._db_name, setup_system=setup_system)
        logger.info("CouchDB document store initialized (setup_system=%s)", setup_system)

    async def connect(self) -> None:
        """Connect to CouchDB."""
        await self._client.connect(db_name=self._db_name)
        logger.info("CouchDB document store connected")

    async def close(self) -> None:
        """Close CouchDB connection."""
        await self._client.close()
        logger.info("CouchDB document store disconnected")
