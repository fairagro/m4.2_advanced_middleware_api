"""CouchDB implementation of DocumentStore."""

import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, cast

from middleware.api.document_store.config import CouchDBConfig
from middleware.api.document_store.content_hash import RoCrateContent, calculate_arc_content_hash
from middleware.api.document_store.couchdb_client import CouchDBClient
from middleware.api.utils import calculate_arc_id
from middleware.shared.api_models.common.models import ArcEventType, ArcLifecycleStatus, HarvestStatus

from . import ArcStoreResult, DocumentStore, DuplicateArcError
from .arc_document import (
    ArcDocument,
    ArcEvent,
    ArcMetadata,
)
from .harvest_document import (
    HarvestDocument,
    HarvestStatistics,
)
from .task_record import TaskRecord

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

    @staticmethod
    def _new_arc_metadata(content_hash: str, now: datetime, harvest_id: str | None) -> ArcMetadata:
        """Build metadata for a first-seen ARC document."""
        return ArcMetadata(
            arc_hash=content_hash,
            status=ArcLifecycleStatus.ACTIVE,
            first_seen=now,
            last_seen=now,
            last_changed=now,
            first_harvest_id=harvest_id,
            last_harvest_id=harvest_id,
            last_changed_harvest_id=harvest_id,
            events=[
                ArcEvent(timestamp=now, type=ArcEventType.ARC_CREATED, message="ARC first seen", harvest_id=harvest_id)
            ],
        )

    @staticmethod
    def _reject_conflicting_harvest_resubmit(
        *,
        identifier: str,
        harvest_id: str | None,
        last_harvest_id: str | None,
        has_changes: bool,
    ) -> None:
        """Raise when the same ARC id was already stored in this harvest with different content."""
        if harvest_id and last_harvest_id == harvest_id and has_changes:
            raise DuplicateArcError(
                f"ARC '{identifier}' was already submitted in harvest '{harvest_id}' with different content."
            )

    def _merge_existing_arc_metadata(
        self,
        existing_doc: ArcDocument,
        *,
        identifier: str,
        content_hash: str,
        now: datetime,
        harvest_id: str | None,
    ) -> tuple[ArcMetadata, bool]:
        """Update metadata for an existing ARC; enforce harvest-local identity."""
        # Compare normalized content, not the stored hash field, so documents
        # written before volatile-field stripping still compare correctly.
        has_changes = calculate_arc_content_hash(existing_doc.arc_content) != content_hash
        self._reject_conflicting_harvest_resubmit(
            identifier=identifier,
            harvest_id=harvest_id,
            last_harvest_id=existing_doc.metadata.last_harvest_id,
            has_changes=has_changes,
        )

        metadata = existing_doc.metadata
        metadata.last_seen = now
        metadata.last_harvest_id = harvest_id

        old_hash = metadata.arc_hash
        metadata.arc_hash = content_hash

        if has_changes:
            logger.info("ARC %s changed (old: %s, new: %s)", identifier, old_hash[:8], content_hash[:8])
            metadata.last_changed = now
            metadata.last_changed_harvest_id = harvest_id
            metadata.status = ArcLifecycleStatus.ACTIVE
            metadata.missing_since = None
            metadata.events.append(
                ArcEvent(
                    timestamp=now,
                    type=ArcEventType.ARC_UPDATED,
                    message="ARC content updated",
                    harvest_id=harvest_id,
                )
            )
            return metadata, True

        logger.debug("ARC content unchanged")
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
        return metadata, False

    @staticmethod
    def _harvest_identity_validator(
        *,
        harvest_id: str,
        identifier: str,
        content_hash: str,
    ) -> Callable[[dict[str, Any]], None]:
        """Return a save-time validator for harvest-local ARC identity (TOCTOU-safe)."""

        def _check_duplicate_on_retry(fresh_doc: dict[str, Any]) -> None:
            fresh_metadata = fresh_doc.get("metadata") or {}
            if fresh_metadata.get("last_harvest_id") != harvest_id:
                return
            fresh_content = fresh_doc.get("arc_content")
            if isinstance(fresh_content, dict):
                fresh_hash = calculate_arc_content_hash(cast(RoCrateContent, fresh_content))
                if fresh_hash == content_hash:
                    return
            raise DuplicateArcError(
                f"ARC '{identifier}' was already submitted in harvest '{harvest_id}' with different content."
            )

        return _check_duplicate_on_retry

    async def store_arc(
        self,
        rdi: str,
        arc_content: dict[str, Any],
        identifier: str,
        harvest_id: str | None = None,
    ) -> ArcStoreResult:
        """Store ARC with change detection."""
        if not identifier:
            raise ValueError("ARC content must contain a valid identifier")

        arc_id = calculate_arc_id(identifier, rdi)
        doc_id = f"arc_{arc_id}"
        content_hash = calculate_arc_content_hash(arc_content)
        now = datetime.now(UTC)

        existing_doc_dict = await self._client.get_document(doc_id)
        existing_doc = ArcDocument.model_validate(existing_doc_dict) if existing_doc_dict else None

        if existing_doc is None:
            is_new = True
            has_changes = True
            logger.info("ARC %s is new (hash: %s)", arc_id, content_hash[:8])
            metadata = self._new_arc_metadata(content_hash, now, harvest_id)
        else:
            is_new = False
            metadata, has_changes = self._merge_existing_arc_metadata(
                existing_doc,
                identifier=identifier,
                content_hash=content_hash,
                now=now,
                harvest_id=harvest_id,
            )

        if len(metadata.events) > self._config.max_event_log_size:
            metadata.events = metadata.events[-self._config.max_event_log_size :]

        doc = ArcDocument(
            doc_id=doc_id,
            doc_rev=existing_doc.doc_rev if existing_doc else None,
            rdi=rdi,
            arc_content=arc_content,
            metadata=metadata,
        )
        doc_data = doc.model_dump(mode="json", by_alias=True, exclude_none=True)

        pre_save_validator = (
            self._harvest_identity_validator(
                harvest_id=harvest_id,
                identifier=identifier,
                content_hash=content_hash,
            )
            if harvest_id
            else None
        )
        await self._client.save_document(doc_id, doc_data, pre_save_validator=pre_save_validator)

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

        doc_data = doc.model_dump(mode="json", by_alias=True, exclude_none=True)
        await self._client.save_document(doc_id, doc_data)

    async def health_check(self) -> bool:
        """Check if document store is reachable."""
        return await self._client.health_check()

    async def setup(self) -> None:
        """Initialize indices for the document store."""
        # We assume connect() has been called before setup()
        # Create indices for common queries
        await self._client.create_index(["type", "rdi"], name="idx_type_rdi")
        await self._client.create_index(["doc_type", "metadata.last_harvest_id"], name="idx_doc_type_harvest")
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
        client_id: str | None,
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

        doc_data = doc.model_dump(mode="json", by_alias=True, exclude_none=True)
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

        doc_data = doc.model_dump(mode="json", by_alias=True, exclude_none=True)
        await self._client.save_document(harvest_id, doc_data)
        return doc

    async def list_harvests(
        self,
        rdi: str | None = None,
        skip: int = 0,
        limit: int | None = None,
    ) -> list[HarvestDocument]:
        """List harvest records."""
        selector: dict[str, Any] = {"type": "harvest"}
        if rdi:
            selector["rdi"] = rdi

        docs = await self._client.find(selector, limit=limit, skip=skip)
        return [HarvestDocument.model_validate(d) for d in docs]

    async def get_harvest_statistics(self, harvest_id: str) -> HarvestStatistics:
        """Calculate and return statistics for a specific harvest run."""
        selector = {"doc_type": "arc", "metadata.last_harvest_id": harvest_id}
        docs = await self._client.find_projected(
            selector,
            fields=["metadata.first_harvest_id", "metadata.last_changed_harvest_id"],
        )

        stats = HarvestStatistics()
        stats.arcs_submitted = len(docs)

        for doc_dict in docs:
            meta = doc_dict.get("metadata", {})
            if meta.get("first_harvest_id") == harvest_id:
                stats.arcs_new += 1
            elif meta.get("last_changed_harvest_id") == harvest_id:
                stats.arcs_updated += 1
            else:
                stats.arcs_unchanged += 1

        return stats

    async def get_task_record(self, task_id: str) -> TaskRecord | None:
        """Get persisted task status record."""
        doc = await self._client.get_document(f"task_status_{task_id}")
        return TaskRecord.model_validate(doc) if doc else None

    async def save_task_record(self, task_record: TaskRecord) -> None:
        """Create or update a task status record in CouchDB."""
        doc_id = f"task_status_{task_record.task_id}"
        payload = task_record.model_dump(mode="json", exclude_none=True)
        await self._client.save_document(doc_id, payload)
