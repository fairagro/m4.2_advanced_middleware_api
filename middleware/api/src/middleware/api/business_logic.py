"""Business logic module for handling ARC (Automated Research Compendium) operations.

This module provides:
- ARC status management and responses
- JSON validation and processing
- Business logic for creating, updating, and managing ARCs
"""

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any

from arctrl import ARC  # type: ignore[import-untyped]
from opentelemetry import trace

from middleware.shared.api_models.models import (
    ArcResponse,
    ArcStatus,
    CreateOrUpdateArcsResponse,
)

from .arc_store import ArcStore

logger = logging.getLogger(__name__)


class BusinessLogicError(Exception):
    """Base exception class for all business logic errors."""


class InvalidJsonSemanticError(BusinessLogicError):
    """Arises when the ARC JSON syntax is valid but semantically incorrect.

    For example, missing required fields or invalid values.
    """


class BusinessLogic:
    """Core business logic for handling ARC operations."""

    def __init__(self, store: ArcStore) -> None:
        """Initialize the BusinessLogic with the given ArcStore.

        Args:
            store (ArcStore): An instance of ArcStore for ARC persistence.

        """
        self._store = store
        self._tracer = trace.get_tracer(__name__)

    def check_health(self) -> bool:
        """Check if the backend systems are healthy.

        Returns:
            bool: True if healthy, False otherwise.
        """
        with self._tracer.start_as_current_span("check_health") as span:
            is_healthy = self._store.check_health()
            span.set_attribute("is_healthy", is_healthy)
            if is_healthy:
                logger.debug("Health check passed.")
            else:
                logger.error("Health check failed.")
            return is_healthy

    async def _create_arc_from_rocrate(self, rdi: str, arc_dict: dict) -> ArcResponse:
        """Create an ARC from RO-Crate JSON with tracing."""
        with self._tracer.start_as_current_span(
            "create_arc_from_rocrate",
            attributes={"rdi": rdi, "arc_index": len(getattr(arc_dict, "__dict__", {}))},
        ) as span:
            logger.debug("Processing RO-Crate JSON for RDI: %s", rdi)
            try:
                arc_json = json.dumps(arc_dict)
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
            exists = self._store.exists(arc_id)
            logger.debug("ARC identifier=%s, arc_id=%s, exists=%s", identifier, arc_id, exists)

            span.set_attribute("arc_id", arc_id)
            span.set_attribute("arc_exists", exists)

            await self._store.create_or_update(arc_id, arc)
            status = ArcStatus.UPDATED if exists else ArcStatus.CREATED
            logger.info("ARC %s: %s (id=%s)", status.value, identifier, arc_id)

            return ArcResponse(
                id=arc_id,
                status=status,
                timestamp=datetime.now(UTC).isoformat() + "Z",
            )

    async def _process_arcs(self, rdi: str, arcs: list[Any]) -> list[ArcResponse]:
        """Process a batch of ARCs with span for batch timing."""
        logger.debug("Processing batch of %d ARCs for RDI: %s", len(arcs), rdi)
        with self._tracer.start_as_current_span(
            "process_arcs_batch",
            attributes={"rdi": rdi, "batch_size": len(arcs)},
        ):
            tasks = [self._create_arc_from_rocrate(rdi, arc) for arc in arcs]
            # Use return_exceptions=True to ensure one failure doesn't stop the whole batch
            results = await asyncio.gather(*tasks, return_exceptions=True)

            processed_arcs: list[ArcResponse] = []
            for i, res in enumerate(results):
                if isinstance(res, Exception):
                    logger.error(
                        "Failed to process ARC at index %d in batch for RDI %s: %s", i, rdi, res, exc_info=True
                    )
                else:
                    processed_arcs.append(res)  # type: ignore[arg-type]

            logger.debug("Batch processing complete: %d/%d ARCs processed successfully", len(processed_arcs), len(arcs))
            return processed_arcs

    # -------------------------- Create or Update ARCs --------------------------
    # TODO: in the first implementation, we accepted string data for ARC JSON,
    # now we accept list[Any] that is already validated using Pydantic in the API layer.
    # The question is: do we need validation on the BusinessLogic layer as well?
    # Depending on the answer, we need to refactor the current validation approach.
    async def create_or_update_arcs(
        self, rdi: str, arcs: list[Any], client_id: str | None
    ) -> CreateOrUpdateArcsResponse:
        """Create or update ARCs based on the provided RO-Crate JSON data.

        Args:
            rdi: Research Data Infrastructure identifier.
            arcs: List of ARC definitions.
            client_id: The client identifier, or None if not authenticated.

        Raises:
            InvalidJsonSemanticError: If the JSON is semantically incorrect.
            BusinessLogicError: If an error occurs during the operation.

        Returns:
            CreateOrUpdateArcsResponse: Response containing details of the processed
            ARCs.

        """
        with self._tracer.start_as_current_span(
            "create_or_update_arcs",
            attributes={"rdi": rdi, "num_arcs": len(arcs), "client_id": client_id or "none"},
        ) as span:
            logger.info(
                "Starting ARC creation/update: rdi=%s, num_arcs=%d, client_id=%s", rdi, len(arcs), client_id or "none"
            )
            try:
                # We do not catch InvalidJsonSemanticError or BusinessLogicError here anymore explicitly
                # because individual ARC failures are handled inside _process_arcs now.
                # Only if _process_arcs itself crashes (unexpectedly) will we land here.
                result = await self._process_arcs(rdi, arcs)

                span.set_attribute("success", True)
                span.set_attribute("processed_count", len(result))

                logger.info("Successfully processed %d/%d ARCs for RDI: %s", len(result), len(arcs), rdi)

                return CreateOrUpdateArcsResponse(
                    client_id=client_id,
                    rdi=rdi,
                    message=f"Processed {len(result)}/{len(arcs)} ARCs successfully",
                    arcs=result,
                )
            except Exception as e:
                logger.error("Unexpected error while processing ARCs batch: %s", e, exc_info=True)
                span.record_exception(e)
                raise BusinessLogicError(f"unexpected error encountered: {str(e)}") from e

    # # -------------------------
    # # READ ARCs
    # # -------------------------
    # @app.get("/arcs", response_model=List[ARC])
    # async def get_arcs():
    #     return list(ARC_DB.values())

    # @app.get("/arcs/{arc_id}")
    # async def get_arc(arc_id: str, request: Request):
    #     arc = ARC_DB.get(arc_id)
    #     if not arc:
    #         raise HTTPException(status_code=404, detail="ARC not found")
    #     accept = request.headers.get("accept", "application/json")
    #     return JSONResponse(content=serialize_arc(arc, accept))

    # # -------------------------
    # # UPDATE ARC
    # # -------------------------
    # @app.put("/arcs/{arc_id}")
    # async def update_arc(arc_id: str, updated: ARC):
    #     if arc_id not in ARC_DB:
    #         raise HTTPException(status_code=404, detail="ARC not found")
    #     updated.id = arc_id
    #     updated.created_at = ARC_DB[arc_id]["created_at"]
    #     updated.updated_at = datetime.now(UTC).isoformat() + "Z"
    #     ARC_DB[arc_id] = updated.dict()
    #     return updated

    # @app.patch("/arcs/{arc_id}")
    # async def patch_arc(arc_id: str, patch_data: dict):
    #     if arc_id not in ARC_DB:
    #         raise HTTPException(status_code=404, detail="ARC not found")
    #     arc = ARC_DB[arc_id]
    #     arc.update(patch_data)
    #     arc["updated_at"] = datetime.now(UTC).isoformat() + "Z"
    #     ARC_DB[arc_id] = arc
    #     return arc

    # # -------------------------
    # # DELETE ARC
    # # -------------------------
    # @app.delete("/arcs/{arc_id}", status_code=204)
    # async def delete_arc(arc_id: str):
    #     if arc_id not in ARC_DB:
    #         raise HTTPException(status_code=404, detail="ARC not found")
    #     del ARC_DB[arc_id]
    #     return Response(status_code=204)
