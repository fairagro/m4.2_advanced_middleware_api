"""Business logic module for handling ARC (Automated Research Compendium) operations.

This module provides:
- ARC status management and responses
- JSON validation and processing
- Business logic for creating, updating, and managing ARCs
"""

import json
import logging
from datetime import UTC, datetime
from typing import Any

from arctrl import ARC  # type: ignore[import-untyped]
from opentelemetry import trace

from middleware.shared.api_models.models import (
    ArcOperationResult,
    ArcResponse,
    ArcStatus,
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

    async def _create_arc_from_rocrate(self, rdi: str, arc_dict: dict) -> ArcResponse:
        """Create an ARC from RO-Crate JSON with tracing."""
        with self._tracer.start_as_current_span(
            "api.BusinessLogic._create_arc_from_rocrate",
            attributes={"rdi": rdi, "arc_index": len(getattr(arc_dict, "__dict__", {}))},
        ) as span:
            logger.debug("Processing RO-Crate JSON for RDI: %s", rdi)
            try:
                with self._tracer.start_as_current_span("api.BusinessLogic._create_arc_from_rocrate:json_serialize"):
                    arc_json = json.dumps(arc_dict)

                with self._tracer.start_as_current_span("api.BusinessLogic._create_arc_from_rocrate:arc_parse_rocrate"):
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
            exists = await self._store.exists(arc_id)
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

    async def create_or_update_arc(self, rdi: str, arc: Any, client_id: str | None) -> ArcOperationResult:
        """Create or update a single ARC based on the provided RO-Crate JSON data.

        Args:
            rdi: Research Data Infrastructure identifier.
            arc: ARC definition.
            client_id: The client identifier, or None if not authenticated.

        Raises:
            InvalidJsonSemanticError: If the JSON is semantically incorrect.
            BusinessLogicError: If an error occurs during the operation.

        Returns:
            ArcOperationResult: Response containing details of the processed ARC.

        """
        with self._tracer.start_as_current_span(
            "api.BusinessLogic.create_or_update_arc",
            attributes={"rdi": rdi, "client_id": client_id or "none"},
        ) as span:
            logger.info("Starting ARC creation/update: rdi=%s, client_id=%s", rdi, client_id or "none")
            try:
                result = await self._create_arc_from_rocrate(rdi, arc)

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
