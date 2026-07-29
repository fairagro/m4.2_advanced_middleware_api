"""Format-neutral harvest run report domain model."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class FailedRecord:
    """A single dataset that failed during harvesting."""

    message: str
    record_id: str | None = None
    url: str | None = None


@dataclass(frozen=True)
class RepositoryReport:  # pylint: disable=too-many-instance-attributes
    """Execution statistics for a single harvested repository."""

    rdi: str
    harvest_id: str | None
    duration_seconds: float
    expected_datasets: int | None = None
    harvested_datasets: int | None = None
    failed_datasets: int | None = None
    skipped_datasets: int = 0
    failed_records: tuple[FailedRecord, ...] = ()
    total_studies: int | None = None
    total_assays: int | None = None


@dataclass(frozen=True)
class HarvestReport:
    """Summary statistics for an entire harvest run."""

    start_time: datetime
    end_time: datetime
    repository_reports: list[RepositoryReport] = field(default_factory=list)
    name: str = "FAIRagro Harvest Run"

    @property
    def duration_seconds(self) -> float:
        """Return the total harvest run duration in seconds."""
        return (self.end_time - self.start_time).total_seconds()
