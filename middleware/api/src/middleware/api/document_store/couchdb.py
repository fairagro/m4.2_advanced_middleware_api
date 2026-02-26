"""CouchDB implementation of DocumentStore."""

import hashlib
import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from middleware.api.config import CouchDBConfig
from middleware.api.couchdb_client import CouchDBClient
from middleware.api.utils import calculate_arc_id, extract_identifier
from middleware.shared.api_models.common.models import ArcEventType, ArcLifecycleStatus, HarvestStatus

from . import ArcStoreResult, DocumentStore
from .arc_document import (
    ArcDocument,
    ArcEvent,
    ArcMetadata,
)
from .harvest_document import (
    HarvestDocument,
    HarvestStatistics,
)

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

    @classmethod
    def _calculate_content_hash(cls, arc_content: dict[str, Any]) -> str:
        """Calculate SHA256 hash of ARC content.

        Note: We use sort_keys=True to ensure consistent hashing even if
        the JSON dictionary order or whitespace changes.
        """
        # orjson is faster if available, but standard json is fine for relatively small dicts
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
        if not identifier:
            raise ValueError("ARC content must contain a valid identifier")

        arc_id = calculate_arc_id(identifier, rdi)
        doc_id = f"arc_{arc_id}"

        content_hash = self._calculate_content_hash(arc_content)
        now = datetime.now(UTC)

        # Check existing document
        existing_doc_dict = await self._client.get_document(doc_id)
        existing_doc = ArcDocument.model_validate(existing_doc_dict) if existing_doc_dict else None

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
                if metadata.status in {ArcLifecycleStatus.MISSING, ArcLifecycleStatus.DELETED}:
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

        doc = ArcDocument.model_validate(doc_dict)
        doc.metadata.events.append(event)

        # Trim events
        if len(doc.metadata.events) > self._config.max_event_log_size:
            doc.metadata.events = doc.metadata.events[-self._config.max_event_log_size :]

        doc_data = doc.model_dump(by_alias=True, exclude_none=True)
        await self._client.save_document(doc_id, doc_data)

    async def health_check(self) -> bool:
        """Check if document store is reachable."""
        return await self._client.health_check()

    async def setup(self) -> None:
        """Initialize indices for the document store."""
        # We assume connect() has been called before setup()
        # Create indices for common queries
        await self._client.create_index(["type", "rdi"], name="idx_type_rdi")
        await self._client.create_index(["type", "metadata.last_harvest_id"], name="idx_type_harvest")
        logger.info("CouchDB document store indices initialized")

    async def connect(self) -> None:
        """Connect to CouchDB."""
        await self._client.connect()
        logger.info("CouchDB document store connected")

    async def close(self) -> None:
        """Close CouchDB connection."""
        await self._client.close()
        logger.info("CouchDB document store disconnected")

    async def create_harvest(
        self,
        rdi: str,
        client_id: str,
        expected_datasets: int | None = None,
    ) -> str:
        """Create a new harvest record."""
        harvest_uuid = str(uuid.uuid4())
        doc_id = f"harvest-{harvest_uuid}"

        doc = HarvestDocument(
            doc_id=doc_id,
            rdi=rdi,
            client_id=client_id,
            started_at=datetime.now(UTC),
            status=HarvestStatus.RUNNING,
            statistics=HarvestStatistics(expected_datasets=expected_datasets),
        )

        doc_data = doc.model_dump(by_alias=True, exclude_none=True)
        await self._client.save_document(doc_id, doc_data)
        return doc_id

    async def get_harvest(self, harvest_id: str) -> HarvestDocument | None:
        """Get harvest document."""
        doc = await self._client.get_document(harvest_id)
        return HarvestDocument.model_validate(doc) if doc else None

    async def update_harvest(self, harvest_id: str, updates: dict[str, Any]) -> HarvestDocument:
        """Update a harvest record and return the updated document."""
        doc_dict = await self._client.get_document(harvest_id)
        if not doc_dict:
            raise ValueError(f"Harvest {harvest_id} not found")

        doc = HarvestDocument.model_validate(doc_dict)

        # Apply updates to the model
        if "status" in updates:
            doc.status = updates["status"]
        if "statistics" in updates:
            doc.statistics = HarvestStatistics.model_validate(updates["statistics"])
        if "completed_at" in updates:
            doc.completed_at = updates["completed_at"]

        # If completing, set completed_at if not provided
        if doc.status == HarvestStatus.COMPLETED and not doc.completed_at:
            doc.completed_at = datetime.now(UTC)

        doc_data = doc.model_dump(by_alias=True, exclude_none=True)
        await self._client.save_document(harvest_id, doc_data)
        return doc

    async def list_harvests(self, rdi: str | None = None) -> list[HarvestDocument]:
        """List harvest records."""
        selector: dict[str, Any] = {"type": "harvest"}
        if rdi:
            selector["rdi"] = rdi

        docs = await self._client.find(selector)
        return [HarvestDocument.model_validate(d) for d in docs]

    async def get_harvest_statistics(self, harvest_id: str) -> HarvestStatistics:
        """Calculate and return statistics for a specific harvest run."""
        # Find all ARCs that were touched by this harvest run
        # We search for documents where last_harvest_id in metadata matches
        selector = {"type": "arc", "metadata.last_harvest_id": harvest_id}
        docs = await self._client.find(selector)

        stats = HarvestStatistics()
        stats.arcs_submitted = len(docs)

        for doc_dict in docs:
            # We need to look at the event log to see what happened to this ARC during THIS harvest
            events = doc_dict.get("metadata", {}).get("events", [])
            harvest_events = [e for e in events if e.get("harvest_id") == harvest_id]

            if not harvest_events:
                # Should not happen based on selector, but let's be safe
                stats.arcs_unchanged += 1
                continue

            # Check if it was created or updated
            event_types = {e.get("type") for e in harvest_events}
            if ArcEventType.ARC_CREATED in event_types:
                stats.arcs_new += 1
            elif ArcEventType.ARC_UPDATED in event_types:
                stats.arcs_updated += 1
            else:
                # If no CREATED/UPDATED event, it was just "seen" but unchanged
                stats.arcs_unchanged += 1

        return stats
