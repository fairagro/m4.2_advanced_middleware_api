"""Business logic exceptions and protocol definitions."""

from typing import Protocol, runtime_checkable

from middleware.api.schemas.celery_tasks import ArcSyncTask


@runtime_checkable
class TaskDispatcher(Protocol):
    """Protocol for dispatching background tasks."""

    def dispatch_sync_arc(self, task: ArcSyncTask) -> None:
        """Dispatch a task to sync an ARC to GitLab."""


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
