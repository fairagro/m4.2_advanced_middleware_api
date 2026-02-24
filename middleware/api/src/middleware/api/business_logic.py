"""Business logic module for handling ARC (Automated Research Compendium) operations.

This module provides unified business logic for ARC processing with two-phase operation:
1. Fast CouchDB storage (used by API for immediate response)
2. Slow GitLab sync (executed by background worker)
"""

import json
import logging
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable

import redis
from arctrl import ARC  # type: ignore[import-untyped]
from opentelemetry import trace

from middleware.api.utils import calculate_arc_id, extract_identifier
from middleware.shared.api_models.common.models import (
    ArcOperationResult,
    ArcResponse,
    ArcStatus,
    ArcSyncTask,
)

from .schemas import ArcEvent, ArcEventType

from .arc_store import ArcStore, ArcStoreTransientError
from .celery_app import celery_app
from .config import Config
from .document_store import DocumentStore
from .services.harvest_manager import HarvestManager

logger = logging.getLogger(__name__)


@runtime_checkable
class TaskDispatcher(Protocol):
    """Protocol for dispatching background tasks."""

    def dispatch_sync_arc(self, task: ArcSyncTask) -> None:
        """Dispatch a task to sync an ARC to GitLab."""
        ...


class BusinessLogicError(Exception):
    """Base exception class for all business logic errors."""


class InvalidJsonSemanticError(BusinessLogicError):
    """Arises when the ARC JSON syntax is valid but semantically incorrect.

    For example, missing required fields or invalid values.
    """


class SetupError(BusinessLogicError):
    """Arises when the business logic setup fails."""


class TransientError(BusinessLogicError):
    """Arises when a transient error occurs that may be resolved by retrying.

    Examples: Server unreachable, maintenance mode, temporary network issues.
    """

class BusinessLogic:
    """Unified business logic for ARC processing.

    This class handles both fast CouchDB storage (for immediate API responses)
    and slow GitLab synchronization (for background workers).

    Architecture:
    - API calls create_or_update_arc() which stores in CouchDB and enqueues GitLab sync
    - Worker calls sync_to_gitlab() to perform the slow GitLab synchronization
    """

    def __init__(
        self,
        config: Config,
        store: ArcStore,
        doc_store: DocumentStore,
        task_dispatcher: TaskDispatcher | None = None,
    ) -> None:
        """Initialize the BusinessLogic.

        Args:
            config: Middleware API configuration.
            store: ArcStore for GitLab persistence.
            doc_store: DocumentStore for CouchDB persistence.
            task_dispatcher: Optional task dispatcher for enqueueing GitLab sync jobs.
        """
        self._config = config
        self._store = store
        self._doc_store = doc_store
        self._dispatcher = task_dispatcher
        self._harvest_manager = HarvestManager(doc_store)
        self._tracer = trace.get_tracer(__name__)

    @property
    def harvest_manager(self) -> HarvestManager:
        """Get the harvest manager service."""
        return self._harvest_manager

    async def health_check(self) -> dict[str, bool]:
        """Check health of stores and message broker."""
        couchdb_ok = await self._doc_store.health_check()

        # Check RabbitMQ (broker) via celery_app
        rabbitmq_ok = False
        try:
            with celery_app.connection_or_acquire() as conn:
                conn.ensure_connection(max_retries=1)
                rabbitmq_ok = True
        except (ConnectionError, redis.ConnectionError) as e:
            logger.error("RabbitMQ health check failed: %s", e)

        # Check Redis (result backend) via celery_app
        redis_ok = False
        try:
            backend_url = self._config.celery.result_backend.get_secret_value()
            if "redis" in backend_url:
                # Use redis library to ping
                r = redis.from_url(backend_url)
                r.ping()
                redis_ok = True
            else:
                # If it's not redis (e.g. memory in tests), consider it ok
                redis_ok = True
        except (redis.ConnectionError, redis.TimeoutError) as e:
            logger.error("Redis health check failed: %s", e)

        return {
            "couchdb_reachable": couchdb_ok,
            "rabbitmq": rabbitmq_ok,
            "redis": redis_ok,
        }

    def get_task_status(self, task_id: str) -> Any:
        """Get the status and result of a Celery task.

        Args:
            task_id: The ID of the task to check.

        Returns:
            The Celery AsyncResult for the task.
        """
        return celery_app.AsyncResult(task_id)

    def store_task_result(self, task_id: str, result: ArcOperationResult) -> None:
        """Store an operation result in the task backend.

        Args:
            task_id: The ID to store the result under.
            result: The ArcOperationResult to store.
        """
        celery_app.backend.store_result(
            task_id,
            result=result.model_dump(),
            state="SUCCESS",
        )

    async def setup(self) -> None:
        """Set up stores and apply migrations."""
        try:
            # We enforce system database creation during setup
            await self._doc_store.setup(setup_system=True)
            # Future: await apply_migrations(self._doc_store)
        except Exception as e:
            logger.error("Failed to setup CouchDB store: %s", e, exc_info=True)
            raise SetupError(f"Failed to setup CouchDB store: {e}") from e

    async def connect(self) -> None:
        """Connect to stores."""
        await self._doc_store.connect()

    async def close(self) -> None:
        """Close store connections."""
        await self._doc_store.close()

    async def __aenter__(self) -> "BusinessLogic":
        """Enter async context."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit async context."""
        await self.close()

    async def create_or_update_arc(self, rdi: str, arc: dict[str, Any], client_id: str, harvest_id: str | None = None) -> ArcOperationResult:
        """Create or update an ARC with fast CouchDB storage and async GitLab sync.

        This method performs fast CouchDB storage and enqueues GitLab sync.
        It must only be called by the API (requires configured task_dispatcher).

        Args:
            rdi: Research Data Infrastructure identifier.
            arc: ARC definition.
            client_id: The client identifier.
            harvest_id: Optional harvest run identifier.

        Returns:
            ArcOperationResult: Response containing details of the processed ARC.

        Raises:
            InvalidJsonSemanticError: If the JSON is semantically incorrect.
            BusinessLogicError: If an error occurs during the operation or if not in API mode.
        """
        # Ensure we are in API mode (dispatcher configured)
        if not self._dispatcher:
            raise BusinessLogicError("create_or_update_arc can only be called in API mode")

        with self._tracer.start_as_current_span(
            "api.BusinessLogic.create_or_update_arc",
            attributes={"rdi": rdi, "client_id": client_id},
        ) as span:
            logger.info("Starting ARC creation/update: rdi=%s, client_id=%s", rdi, client_id)
            try:
                # Fast validation: Ensure identifier is present
                identifier = extract_identifier(arc)
                if identifier is None:
                    raise InvalidJsonSemanticError("RO-Crate JSON must contain an 'identifier' (e.g. in ISA object).")

                # identifier is None:
                #     raise InvalidJsonSemanticError("RO-Crate JSON must contain an 'identifier' (e.g. in ISA object).")

                # Store in CouchDB (fast) - identifiers and hashing are handled inside doc_store
                doc_result = await self._doc_store.store_arc(rdi, arc, harvest_id=harvest_id)
                arc_id = doc_result.arc_id
                span.set_attribute("arc_id", arc_id)

                is_new = doc_result.is_new
                has_changes = doc_result.has_changes
                should_trigger_git = is_new or has_changes

                logger.info(
                    "Stored ARC %s in CouchDB: is_new=%s, has_changes=%s, trigger_git=%s",
                    arc_id,
                    is_new,
                    has_changes,
                    should_trigger_git,
                )

                # Enqueue GitLab sync if needed
                if should_trigger_git:
                    logger.info("Enqueueing GitLab sync task for ARC %s", arc_id)
                    self._dispatcher.dispatch_sync_arc(ArcSyncTask(rdi=rdi, arc=arc))
                else:
                    logger.info("Skipping GitLab sync for ARC %s (unchanged)", arc_id)

                status = ArcStatus.CREATED if is_new else ArcStatus.UPDATED
                result = ArcResponse(
                    id=arc_id,
                    status=status,
                    timestamp=datetime.now(UTC).isoformat() + "Z",
                )

                span.set_attribute("success", True)

                return ArcOperationResult(
                    client_id=client_id,
                    rdi=rdi,
                    message="Stored in CouchDB successfully",
                    arc=result,
                )

            except Exception as e:
                logger.error("Unexpected error while processing ARC: %s", e, exc_info=True)
                span.record_exception(e)
                if isinstance(e, InvalidJsonSemanticError):
                    raise e
                if isinstance(e, BusinessLogicError):
                    raise e
                raise BusinessLogicError(f"unexpected error encountered: {str(e)}") from e

    async def sync_to_gitlab(self, rdi: str, arc: dict[str, Any]) -> None:
        """Synchronize ARC to GitLab storage.

        This method performs the slow GitLab sync operation. It must only be
        called by background workers (requires NO task_dispatcher).

        Args:
            rdi: Research Data Infrastructure identifier.
            arc: ARC definition.

        Raises:
            InvalidJsonSemanticError: If the JSON is semantically incorrect.
            BusinessLogicError: If an error occurs during the operation or if in API mode.
        """
        # Ensure we are in Worker mode (task_dispatcher NOT configured)
        if self._dispatcher:
            raise BusinessLogicError("sync_to_gitlab must not be called in API mode")

        with self._tracer.start_as_current_span(
            "api.BusinessLogic.sync_to_gitlab",
            attributes={"rdi": rdi},
        ) as span:
            logger.info("Starting GitLab sync for RDI: %s", rdi)
            try:
                # Calculate ARC ID using shared utility - fast and doesn't require full arctrl parse yet
                identifier = extract_identifier(arc)
                if identifier is None:
                    raise InvalidJsonSemanticError("RO-Crate JSON must contain an 'identifier' (e.g. in ISA object).")

                arc_id = calculate_arc_id(identifier, rdi)
                span.set_attribute("arc_id", arc_id)

                # Parse ARC for storage (slow, but fine in worker)
                arc_json = json.dumps(arc)
                arc_obj = ARC.from_rocrate_json_string(arc_json)

                # Store in Git
                logger.info("Triggering Git storage for ARC %s", arc_id)
                await self._store.create_or_update(arc_id, arc_obj)

                # Record success in CouchDB
                await self._doc_store.add_event(
                    arc_id,
                    ArcEvent(
                        timestamp=datetime.now(UTC),
                        type=ArcEventType.GIT_PUSH_SUCCESS,
                        message="Successfully synchronized to GitLab",
                    ),
                )

                span.set_attribute("success", True)
                logger.info("Successfully synced ARC %s to GitLab", arc_id)

            except ArcStoreTransientError as e:
                logger.info("Transient error during GitLab sync for ARC %s: %s", arc_id, e)
                span.record_exception(e)
                # Note: We don't always want to write an event for every retry-able transient error
                # to avoid log spam, but for critical failures we do.
                raise TransientError(str(e)) from e

            except Exception as e:
                logger.error("Unexpected error while syncing ARC to GitLab: %s", e, exc_info=True)
                span.record_exception(e)

                # Try to record failure in CouchDB if we have an arc_id
                try:
                    identifier = identifier or extract_identifier(arc)
                    if identifier:
                        arc_id = arc_id or calculate_arc_id(identifier, rdi)
                        await self._doc_store.add_event(
                            arc_id,
                            ArcEvent(
                                timestamp=datetime.now(UTC),
                                type=ArcEventType.GIT_PUSH_FAILED,
                                message=f"GitLab sync failed: {str(e)}",
                            ),
                        )
                except Exception as log_error:
                    logger.warning("Could not log sync failure to CouchDB: %s", log_error)

                if isinstance(e, InvalidJsonSemanticError):
                    raise e
                if isinstance(e, BusinessLogicError):
                    raise e
                raise BusinessLogicError(f"unexpected error encountered: {str(e)}") from e
