"""ARC management operations for creating, updating, and syncing ARCs."""

import json
import logging
from datetime import UTC, datetime
from typing import Any

from arctrl import ARC  # type: ignore[import-untyped]
from opentelemetry import trace

from middleware.api.arc_store import ArcStore, ArcStoreTransientError
from middleware.api.document_store import DocumentStore, DuplicateArcError
from middleware.api.document_store.arc_document import ArcEvent, ArcEventType
from middleware.api.rocrate import parse_rocrate
from middleware.api.utils import calculate_arc_id
from middleware.shared.api_models.common.models import ArcOperationResult, ArcResponse, ArcStatus
from middleware.shared.api_models.common.rocrate import RoCratePayload

from .exceptions import BusinessLogicError, DuplicateArcInHarvestError, InvalidJsonSemanticError, TransientError
from .ports import TaskDispatcher
from .task_payloads import ArcSyncTask

logger = logging.getLogger(__name__)


class ArcManager:
    """Handles ARC creation, update, and GitLab synchronization.

    Owns the two main domain operations:
    - ``create_or_update_arc``: fast CouchDB storage + enqueue GitLab sync (API mode)
    - ``sync_to_gitlab``: perform the slow GitLab sync (worker mode)
    """

    def __init__(
        self,
        store: ArcStore,
        doc_store: DocumentStore,
        task_dispatcher: TaskDispatcher | None = None,
    ) -> None:
        """Initialize the ArcManager.

        Args:
            store: ArcStore for GitLab persistence.
            doc_store: DocumentStore for CouchDB persistence.
            task_dispatcher: Optional dispatcher for enqueueing GitLab sync jobs (API mode only).
        """
        self._store = store
        self._doc_store = doc_store
        self._dispatcher = task_dispatcher
        self._tracer = trace.get_tracer(__name__)

    @property
    def store(self) -> ArcStore:
        """Return the underlying ArcStore (used by health checks and shutdown delegation)."""
        return self._store

    async def shutdown(self) -> None:
        """Release resources held by the underlying ArcStore (e.g. thread-pool)."""
        await self._store.shutdown()

    async def create_or_update_arc(
        self,
        rdi: str,
        arc: RoCratePayload | dict[str, Any],
        client_id: str | None,
        harvest_id: str | None = None,
    ) -> ArcOperationResult:
        """Create or update an ARC with fast CouchDB storage and async GitLab sync.

        This method performs fast CouchDB storage and enqueues GitLab sync.
        It must only be called by the API (requires configured task_dispatcher).

        Args:
            rdi: Research Data Infrastructure identifier.
            arc: Validated or raw RO-Crate payload.
            client_id: The client identifier.
            harvest_id: Optional harvest run identifier.

        Returns:
            ArcOperationResult: Response containing details of the processed ARC.

        Raises:
            InvalidJsonSemanticError: If the JSON is semantically incorrect.
            BusinessLogicError: If an error occurs during the operation or if not in API mode.
        """
        if not self._dispatcher:
            raise BusinessLogicError("create_or_update_arc can only be called in API mode")

        with self._tracer.start_as_current_span(
            "api.ArcManager.create_or_update_arc",
            attributes={"rdi": rdi, "client_id": client_id if client_id is not None else ""},
        ) as span:
            logger.info("[%s] Starting ARC creation/update: rdi=%s", client_id, rdi)
            try:
                rocrate = parse_rocrate(arc)
                arc_content = rocrate.model_dump(by_alias=True)
                doc_result = await self._doc_store.store_arc(
                    rdi,
                    arc_content,
                    rocrate.identifier,
                    harvest_id=harvest_id,
                )
                arc_id = doc_result.arc_id
                span.set_attribute("arc_id", arc_id)

                is_new = doc_result.is_new
                has_changes = doc_result.has_changes
                should_trigger_git = is_new or has_changes

                logger.info(
                    "[%s] Stored ARC %s in CouchDB: is_new=%s, has_changes=%s, trigger_git=%s",
                    client_id,
                    arc_id,
                    is_new,
                    has_changes,
                    should_trigger_git,
                )

                if should_trigger_git:
                    logger.info("[%s] Enqueueing GitLab sync task for ARC %s", client_id, arc_id)
                    self._dispatcher.dispatch_sync_arc(
                        ArcSyncTask(
                            rdi=rdi,
                            arc=arc_content,
                            client_id=client_id,
                        )
                    )
                else:
                    logger.info("[%s] Skipping GitLab sync for ARC %s (unchanged)", client_id, arc_id)

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
                logger.error("[%s] Unexpected error while processing ARC: %s", client_id, e, exc_info=True)
                span.record_exception(e)
                if isinstance(e, InvalidJsonSemanticError):
                    raise
                if isinstance(e, BusinessLogicError):
                    raise
                if isinstance(e, DuplicateArcError):
                    raise DuplicateArcInHarvestError(str(e)) from e
                raise BusinessLogicError(f"unexpected error encountered: {str(e)}") from e

    async def sync_to_gitlab(self, rdi: str, arc: RoCratePayload | dict[str, Any]) -> None:
        """Synchronize ARC to GitLab storage.

        This method performs the slow GitLab sync operation. It must only be
        called by background workers (requires NO task_dispatcher).

        Args:
            rdi: Research Data Infrastructure identifier.
            arc: Validated or raw RO-Crate payload.

        Raises:
            InvalidJsonSemanticError: If the JSON is semantically incorrect.
            BusinessLogicError: If an error occurs during the operation or if in API mode.
        """
        if self._dispatcher:
            raise BusinessLogicError("sync_to_gitlab must not be called in API mode")

        with self._tracer.start_as_current_span(
            "api.ArcManager.sync_to_gitlab",
            attributes={"rdi": rdi},
        ) as span:
            logger.info("Starting GitLab sync for RDI: %s", rdi)
            arc_id: str | None = None
            try:
                rocrate = parse_rocrate(arc)
                arc_id = calculate_arc_id(rocrate.identifier, rdi)
                arc_content = rocrate.model_dump(by_alias=True)
                span.set_attribute("arc_id", arc_id)

                arc_json = json.dumps(arc_content)
                arc_obj = ARC.from_rocrate_json_string(arc_json)

                logger.info("Triggering Git storage for ARC %s", arc_id)
                await self._store.create_or_update(
                    arc_id,
                    arc_obj,
                    rdi=rdi,
                )

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
                logger.info("Transient error during GitLab sync for ARC %s: %s", arc_id or "unknown", e)
                span.record_exception(e)
                raise TransientError(str(e)) from e

            except Exception as e:
                logger.error("Unexpected error while syncing ARC to GitLab: %s", e, exc_info=True)
                span.record_exception(e)

                if arc_id is not None:
                    try:
                        await self._doc_store.add_event(
                            arc_id,
                            ArcEvent(
                                timestamp=datetime.now(UTC),
                                type=ArcEventType.GIT_PUSH_FAILED,
                                message=f"GitLab sync failed: {str(e)}",
                            ),
                        )
                    except Exception as log_error:  # noqa: BLE001
                        logger.warning("Could not log sync failure to CouchDB: %s", log_error)

                if isinstance(e, InvalidJsonSemanticError):
                    raise
                if isinstance(e, BusinessLogicError):
                    raise
                raise BusinessLogicError(f"unexpected error encountered: {str(e)}") from e
