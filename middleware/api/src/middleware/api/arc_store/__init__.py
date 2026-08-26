"""Contains the ArcStore interface and its implementations."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import NoReturn

from arctrl import ARC  # type: ignore[import-untyped]
from opentelemetry import trace

from middleware.api.arc_store.arctrl_compat import patch_fable_int32_for_openpyxl
from middleware.api.utils import calculate_arc_id
from middleware.shared.security.url_redact import redact_url_userinfo

patch_fable_int32_for_openpyxl()

logger = logging.getLogger(__name__)


class ArcStoreError(Exception):
    """Exception base class for all ArcStore errors."""

    def __str__(self) -> str:
        """Hide URL userinfo (e.g. oauth2 tokens) in messages and events."""
        return redact_url_userinfo(super().__str__())


class ArcStoreTransientError(ArcStoreError):
    """Exception raised when a transient error occurs in the ArcStore.

    This indicates that a retry might be successful.
    """


def _record_and_raise_arc_store_error(span: trace.Span, exc: BaseException, message: str) -> NoReturn:
    """Record a redacted ArcStoreError on the span, then raise it.

    Never call ``span.record_exception`` with a raw ``GitCommandError``: tracing
    backends would export oauth2 userinfo embedded in HTTPS remotes.
    """
    wrapped = ArcStoreError(redact_url_userinfo(f"{message}: {exc}"))
    span.record_exception(wrapped)
    raise wrapped from exc


# ----------- Interface -----------


class ArcStore(ABC):
    """Abstract base class for ARC storage backends."""

    def __init__(self) -> None:
        """Initialize ArcStore with tracer."""
        self._tracer = trace.get_tracer(__name__)

    @staticmethod
    def arc_id(identifier: str, rdi: str) -> str:
        """Generate ARC ID."""
        return calculate_arc_id(identifier, rdi)

    @abstractmethod
    async def _create_or_update(
        self,
        arc_id: str,
        arc: ARC,
        *,
        rdi: str,
    ) -> None:
        """Create or updates an ARC."""
        raise NotImplementedError("`ArcStore._create_or_update` is not implemented")

    @abstractmethod
    async def _get(self, arc_id: str) -> ARC | None:
        """Return an ARC of a given id."""
        raise NotImplementedError("`ArcStore._get` is not implemented")

    @abstractmethod
    async def _delete(self, arc_id: str) -> None:
        """Delete an ARC of a given id."""
        raise NotImplementedError("`ArcStore._delete` is not implemented")

    @abstractmethod
    async def _exists(self, arc_id: str) -> bool:
        """Check if an ARC of a given id already exists."""
        raise NotImplementedError("`ArcStore._exists` is not implemented")

    @abstractmethod
    def _check_health(self) -> bool:
        """Check connection to the storage backend."""
        raise NotImplementedError("`ArcStore._check_health` is not implemented")

    @property
    def publishes_per_arc_git(self) -> bool:
        """Whether ``create_or_update`` pushes one Git project per ARC.

        Consolidated catalog backends return False so callers skip per-ARC
        ``GIT_PUSH_*`` events.
        """
        return True

    @property
    def supports_standalone_upload(self) -> bool:
        """Whether standalone ARC create (``/v1/arcs``, ``/v2/arcs``, ``/v3/arcs``) is allowed."""
        return True

    async def _finalize(self, *, rdi: str) -> bool:  # noqa: PLR6301, ARG002
        """Publish pending catalog state for an RDI.

        Default is a successful no-op returning False (nothing pushed) so
        orchestrators can call finalize for every backend without branching.
        """
        return False

    async def shutdown(self) -> None:  # noqa: PLR6301
        """Release resources held by the store (e.g. thread-pool executors).

        Subclasses should override this if they own background resources.
        The default implementation is a no-op.
        """
        return  # no-op default; subclasses (e.g. GitRepo) override

    async def create_or_update(
        self,
        arc_id: str,
        arc: ARC,
        *,
        rdi: str,
    ) -> None:
        """_Create or update an ARC.

        Args:
            arc_id (str): ID of the ARC to create or update.
            arc (ARC): ARC object to create or update.
            rdi: Originating Research Data Infrastructure identifier.

        Raises:
            ArcStoreError: If an error occurs during the operation.

        Returns:
            _type_: None

        """
        with self._tracer.start_as_current_span(
            "api.ArcStore.create_or_update",
            attributes={"arc_id": arc_id, "rdi": rdi},
        ) as span:
            try:
                return await self._create_or_update(arc_id, arc, rdi=rdi)
            except ArcStoreError as e:
                span.record_exception(e)
                raise
            except Exception as e:
                logger.exception(
                    "Caught exception when trying to create or update ARC '%s': %s",
                    arc_id,
                    redact_url_userinfo(str(e)),
                )
                _record_and_raise_arc_store_error(
                    span,
                    e,
                    "General exception caught in `ArcStore.create_or_update`",
                )

    async def finalize(self, *, rdi: str) -> bool:
        """Publish pending catalog state for an RDI.

        Raises:
            ArcStoreError: If an error occurs during the operation.
        """
        with self._tracer.start_as_current_span(
            "api.ArcStore.finalize",
            attributes={"rdi": rdi},
        ) as span:
            try:
                pushed = await self._finalize(rdi=rdi)
                span.set_attribute("pushed", pushed)
                return pushed
            except ArcStoreError as e:
                span.record_exception(e)
                raise
            except Exception as e:
                logger.exception(
                    "Caught exception when finalizing catalog for RDI '%s': %s",
                    rdi,
                    redact_url_userinfo(str(e)),
                )
                _record_and_raise_arc_store_error(
                    span,
                    e,
                    "General exception caught in `ArcStore.finalize`",
                )

    async def get(self, arc_id: str) -> ARC | None:
        """_Get an ARC by its ID.

        Args:
            arc_id (str): ID of the ARC to retrieve.

        Returns:
            Optional[ARC]: The ARC object if found, otherwise None.

        """
        with self._tracer.start_as_current_span(
            "api.ArcStore.get",
            attributes={"arc_id": arc_id},
        ) as span:
            try:
                arc = await self._get(arc_id)
                span.set_attribute("found", arc is not None)
                return arc
            except ArcStoreError as e:
                span.record_exception(e)
                raise
            except Exception as e:
                logger.exception(
                    "Caught exception when trying to retrieve ARC '%s': %s",
                    arc_id,
                    redact_url_userinfo(str(e)),
                )
                _record_and_raise_arc_store_error(
                    span,
                    e,
                    "General exception caught in `ArcStore.get`",
                )

    async def delete(self, arc_id: str) -> None:
        """_Delete an ARC by its ID.

        Args:
            arc_id (str): ID of the ARC to delete.

        Raises:
            ArcStoreError: If an error occurs during the operation.

        Returns:
            _type_: None

        """
        with self._tracer.start_as_current_span(
            "api.ArcStore.delete",
            attributes={"arc_id": arc_id},
        ) as span:
            try:
                return await self._delete(arc_id)
            except ArcStoreError as e:
                span.record_exception(e)
                raise
            except Exception as e:
                logger.exception(
                    "Caught exception when trying to delete ARC '%s': %s",
                    arc_id,
                    redact_url_userinfo(str(e)),
                )
                _record_and_raise_arc_store_error(
                    span,
                    e,
                    "General exception caught in `ArcStore.delete`",
                )

    async def exists(self, arc_id: str) -> bool:
        """_Check if an ARC exists by its ID.

        Args:
            arc_id (str): ID of the ARC to check.

        Raises:
            ArcStoreError: If an error occurs during the operation.

        Returns:
            bool: True if the ARC exists, False otherwise.

        """
        with self._tracer.start_as_current_span(
            "api.ArcStore.exists",
            attributes={"arc_id": arc_id},
        ) as span:
            try:
                exists = await self._exists(arc_id)
                span.set_attribute("exists", exists)
                return exists
            except ArcStoreError as e:
                span.record_exception(e)
                raise
            except Exception as e:
                logger.exception(
                    "Caught exception when trying to check if ARC '%s' exists: %s",
                    arc_id,
                    redact_url_userinfo(str(e)),
                )
                _record_and_raise_arc_store_error(
                    span,
                    e,
                    f"Caught exception when trying to check if ARC '{arc_id}' exists",
                )

    def check_health(self) -> bool:
        """Check connection to the storage backend.

        Returns:
            bool: True if backend is reachable, False otherwise.
        """
        try:
            return self._check_health()
        except (RuntimeError, OSError, ValueError, ConnectionError, TimeoutError) as e:
            logger.exception("Caught exception during health check: %s", str(e))
            return False
