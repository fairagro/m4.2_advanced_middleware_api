"""Ports for infrastructure integrations used by BusinessLogic."""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from middleware.api.business_logic.task_payloads import ArcSyncTask, CatalogFinalizeTask


@runtime_checkable
class TaskDispatcher(Protocol):
    """Protocol for dispatching background tasks."""

    def dispatch_sync_arc(self, task: ArcSyncTask) -> None:
        """Dispatch a task to sync an ARC to GitLab."""
        raise NotImplementedError

    def dispatch_finalize_catalog(self, task: CatalogFinalizeTask) -> None:
        """Dispatch a task to finalize the consolidated RDI catalog."""
        raise NotImplementedError


@runtime_checkable
class BrokerHealthChecker(Protocol):
    """Port for checking message broker health."""

    def is_healthy(self) -> bool:
        """Return whether the configured broker is reachable."""
        raise NotImplementedError


@dataclass(slots=True)
class BusinessLogicPorts:
    """Optional infrastructure adapters used by BusinessLogic in API mode."""

    task_dispatcher: TaskDispatcher | None = None
    broker_health_checker: BrokerHealthChecker | None = None
