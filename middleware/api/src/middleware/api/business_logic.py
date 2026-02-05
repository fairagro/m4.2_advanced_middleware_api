"""Business logic module for handling ARC (Automated Research Compendium) operations.

This module provides:
- ARC status management and responses
- JSON validation and processing
- Business logic for creating, updating, and managing ARCs
"""

import json
import logging
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable

from arctrl import ARC  # type: ignore[import-untyped]
from opentelemetry import trace

from middleware.shared.api_models.models import (
    ArcOperationResult,
    ArcResponse,
    ArcStatus,
    HealthResponse,
)

from .arc_store import ArcStore
from .document_store import DocumentStore

logger = logging.getLogger(__name__)


class BusinessLogicError(Exception):
    """Base exception class for all business logic errors."""


class InvalidJsonSemanticError(BusinessLogicError):
    """Arises when the ARC JSON syntax is valid but semantically incorrect.

    For example, missing required fields or invalid values.
    """


@runtime_checkable
class TaskSender(Protocol):
    """Protocol for Celery Task sender."""

    def delay(self, *args: Any, **kwargs: Any) -> Any:
        """Schedule the task."""
        ...


@runtime_checkable
class BusinessLogic(Protocol):
    """Protocol for Business Logic implementations."""

    async def create_or_update_arc(
        self, rdi: str, arc: dict[str, Any], client_id: str, doc_store: DocumentStore | None = None
    ) -> ArcOperationResult:
        """Create or update an ARC."""
        ...

    async def health_check(self) -> dict[str, bool]:
        """Check health of dependencies."""
        ...


class AsyncBusinessLogic:
    """Business Logic implementation that dispatches tasks to a background worker."""

    def __init__(self, task_sender: TaskSender) -> None:
        """Initialize with a task sender."""
        self._task_sender = task_sender
        self._tracer = trace.get_tracer(__name__)

    async def create_or_update_arc(
        self, rdi: str, arc: dict[str, Any], client_id: str, doc_store: DocumentStore | None = None
    ) -> ArcOperationResult:
        """Dispatch ARC for async processing."""
        # Note: doc_store is ignored here as it's not serializable/relevant for dispatch
        with self._tracer.start_as_current_span(
            "api.AsyncBusinessLogic.create_or_update_arc",
            attributes={"rdi": rdi, "client_id": client_id or "none"},
        ) as span:
            logger.info("Dispatching ARC task for RDI: %s", rdi)
            
            # Dispatch task
            task = self._task_sender.delay(rdi, arc, client_id)
            
            span.set_attribute("task_id", task.id)
            logger.info("Enqueued task %s", task.id)

            # Return a result indicating accepted status
            # CreateOrUpdateArcsResponse expects tasks, but internally we return ArcOperationResult?
            # actually internal logic uses ArcOperationResult.
            # However, for Async dispatch, we return a "Processing" status.
            # But the signature demands ArcOperationResult. 
            # We might need to adjust the return type or return a 'Pending' result.
            
            return ArcOperationResult(
                client_id=client_id,
                rdi=rdi,
                message="Task enqueued",
                arc=None,  # No ARC response yet
                task_id=task.id,
            )

    async def health_check(self) -> dict[str, bool]:
        """Check health of dispatch mechanism (e.g. RabbitMQ)."""
        # Ideally check broker connection
        # This implementation depends on how `task_sender` (Celery) exposes health
        # For now, we assume if we can instantiate, it's 'ok' or we delegate to Api health check logic
        # But strict layering means Api shouldn't know. 
        # We can implement a basic check here if possible, or pass.
        return {"dispatcher": True}


class DirectBusinessLogic:
    """Core business logic for handling ARC operations directly."""

    def __init__(self, store: ArcStore, doc_store: DocumentStore | None = None) -> None:
        """Initialize the BusinessLogic with the given ArcStore.

        Args:
            store (ArcStore): An instance of ArcStore for ARC persistence.
            doc_store (DocumentStore): Optional DocumentStore for CouchDB persistence.

        """
        self._store = store
        self._doc_store = doc_store
        self._tracer = trace.get_tracer(__name__)

    async def health_check(self) -> dict[str, bool]:
        """Check health of stores."""
        couchdb_ok = False
        if self._doc_store:
            couchdb_ok = await self._doc_store.health_check()
            
        # arc_store (Git) might not have health check yet, assume True or check if path exists
        return {
            "couchdb_reachable": couchdb_ok,
            # "git_reachable": True 
        }

    async def _create_arc_from_rocrate(self, rdi: str, arc_dict: dict[str, Any], doc_store: DocumentStore | None = None) -> ArcResponse:
        """Create an ARC from RO-Crate JSON with tracing."""
        with self._tracer.start_as_current_span(
            "api.DirectBusinessLogic._create_arc_from_rocrate",
            attributes={"rdi": rdi, "arc_index": len(getattr(arc_dict, "__dict__", {}))},
        ) as span:
            logger.debug("Processing RO-Crate JSON for RDI: %s", rdi)
            try:
                with self._tracer.start_as_current_span("api.DirectBusinessLogic._create_arc_from_rocrate:json_serialize"):
                    arc_json = json.dumps(arc_dict)

                with self._tracer.start_as_current_span("api.DirectBusinessLogic._create_arc_from_rocrate:arc_parse_rocrate"):
                    arc = ARC.from_rocrate_json_string(arc_json)

                logger.debug("Successfully parsed ARC from RO-Crate JSON")
            except Exception as e:
                logger.error("Failed to parse RO-Crate JSON: %s", e, exc_info=True)
                span.record_exception(e)
                raise InvalidJsonSemanticError(f"Error processing RO-Crate JSON: {e!r}") from e

            identifier = getattr(arc, "Identifier", None)
            if not identifier or identifier == "":
                logger.error("ARC missing identifier in RO-Crate JSON")
                raise InvalidJsonSemanticError("RO-Crate JSON must contain an 'Identifier' in the ISA object.")

            arc_id = self._store.arc_id(identifier, rdi)
            span.set_attribute("arc_id", arc_id)

            # 1. Store in DocumentStore (CouchDB) if configured
            # Use injected store or fall back to instance store
            active_doc_store = doc_store or self._doc_store
            
            is_new = True
            should_trigger_git = True
            
            if active_doc_store:
                try:
                    # Note: We rely on doc_store to calculate hash and detect changes
                    # We pass arc_dict (raw JSON)
                    doc_result = await active_doc_store.store_arc(rdi, arc_dict)
                    
                    # Log event
                    logger.info(
                        "Stored ARC %s in CouchDB: is_new=%s, has_changes=%s, trigger_git=%s",
                        arc_id, doc_result.is_new, doc_result.has_changes, doc_result.should_trigger_git
                    )
                    
                    is_new = doc_result.is_new
                    should_trigger_git = doc_result.should_trigger_git
                    # We could also use doc_result.arc_id but we trust _store.arc_id matches logic
                    
                except Exception as e:
                    logger.error("Failed to store ARC in DocumentStore: %s", e, exc_info=True)
                    # Proceed with Git store as fallback
                    pass
            else:
                # Legacy behavior: check if exists in Git store
                exists = await self._store.exists(arc_id)
                is_new = not exists
                logger.debug("ARC identifier=%s, arc_id=%s, exists=%s", identifier, arc_id, exists)
                span.set_attribute("arc_exists", exists)
            
            # 2. Store in Git (ArcStore)
            if should_trigger_git:
                logger.info("Triggering Git storage for ARC %s", arc_id)
                await self._store.create_or_update(arc_id, arc)
            else:
                logger.info("Skipping Git storage for ARC %s (unchanged)", arc_id)

            status = ArcStatus.CREATED if is_new else ArcStatus.UPDATED
            logger.info("ARC %s: %s (id=%s)", status.value, identifier, arc_id)

            return ArcResponse(
                id=arc_id,
                status=status,
                timestamp=datetime.now(UTC).isoformat() + "Z",
            )

    async def create_or_update_arc(
        self, rdi: str, arc: dict[str, Any], client_id: str, doc_store: DocumentStore | None = None
    ) -> ArcOperationResult:
        """Create or update a single ARC based on the provided RO-Crate JSON data.

        Args:
            rdi: Research Data Infrastructure identifier.
            arc: ARC definition.
            client_id: The client identifier, or None if not authenticated.
            doc_store: Optional DocumentStore to use for this operation.

        Raises:
            InvalidJsonSemanticError: If the JSON is semantically incorrect.
            BusinessLogicError: If an error occurs during the operation.

        Returns:
            ArcOperationResult: Response containing details of the processed ARC.

        """
        with self._tracer.start_as_current_span(
            "api.DirectBusinessLogic.create_or_update_arc",
            attributes={"rdi": rdi, "client_id": client_id or "none"},
        ) as span:
            logger.info("Starting ARC creation/update: rdi=%s, client_id=%s", rdi, client_id or "none")
            try:
                result = await self._create_arc_from_rocrate(rdi, arc, doc_store=doc_store)

                span.set_attribute("success", True)

                logger.info("Successfully processed ARC for RDI: %s", rdi)

                return ArcOperationResult(
                    client_id=client_id,
                    rdi=rdi,
                    message="Processed ARC successfully",
                    arc=result,
                )
            except Exception as e:
                logger.error("Unexpected error while processing ARC: %s", e, exc_info=True)
                span.record_exception(e)
                if isinstance(e, InvalidJsonSemanticError):
                    raise e
                raise BusinessLogicError(f"unexpected error encountered: {str(e)}") from e
