"""Mutable harvest-run report with counting methods and format-neutral snapshots."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


def _require_aware_utc(value: datetime, *, what: str) -> datetime:
    """Reject naive datetimes and normalize timezone-aware values to UTC."""
    if value.tzinfo is None:
        raise ValueError(f"{what} must be timezone-aware UTC")
    return value.astimezone(UTC)


class IssueKind(StrEnum):
    """Classification of a harvest issue for operator reports."""

    DATASET = "dataset"
    REPOSITORY = "repository"


@dataclass(frozen=True)
class HarvestIssue:
    """One harvest issue (dataset failure or repository-level problem)."""

    message: str
    kind: IssueKind = IssueKind.DATASET
    record_id: str | None = None
    url: str | None = None


@dataclass(frozen=True)
class RepositoryReport:  # pylint: disable=too-many-instance-attributes
    """Immutable snapshot of statistics for one repository scope."""

    rdi: str
    harvest_id: str | None
    duration_seconds: float
    expected_datasets: int | None = None
    harvested_datasets: int = 0
    failed_datasets: int = 0
    skipped_datasets: int = 0
    failures: tuple[HarvestIssue, ...] = ()
    total_studies: int | None = None
    total_assays: int | None = None


@dataclass
class _DatasetCounts:
    """Mutable dataset-level counters for one repository scope."""

    expected_datasets: int | None = None
    harvest_id: str | None = None
    harvested_datasets: int = 0
    failed_datasets: int = 0
    skipped_datasets: int = 0
    failures: list[HarvestIssue] = field(default_factory=list)


@dataclass
class _CompositionCounts:
    """Mutable study/assay totals for one repository scope."""

    total_studies: int = 0
    total_assays: int = 0


class RepositoryScope:
    """Mutable counting handle for one RDI within a harvest run."""

    def __init__(self, rdi: str, *, opened_at: datetime | None = None) -> None:
        """Open a repository scope for ``rdi``; timing starts immediately."""
        self._rdi = rdi
        if opened_at is None:
            self._opened_at = datetime.now(UTC)
        else:
            self._opened_at = _require_aware_utc(opened_at, what="RepositoryScope opened_at")
        self._closed_at: datetime | None = None
        self._lock = threading.Lock()
        self._datasets = _DatasetCounts()
        self._composition = _CompositionCounts()

    @property
    def rdi(self) -> str:
        """RDI identifier for this scope."""
        return self._rdi

    def close(self, *, closed_at: datetime | None = None) -> None:
        """Close the scope and record end time for duration."""
        if closed_at is not None:
            closed_at = _require_aware_utc(closed_at, what="RepositoryScope closed_at")
        with self._lock:
            if self._closed_at is None:
                self._closed_at = closed_at or datetime.now(UTC)

    def set_expected_datasets(self, count: int) -> None:
        """Set the optional expected dataset count for this repository."""
        if count < 0:
            raise ValueError("expected dataset count must be non-negative")
        with self._lock:
            self._datasets.expected_datasets = count

    def set_harvest_id(self, harvest_id: str | None) -> None:
        """Set or clear the harvest identifier for this repository."""
        with self._lock:
            self._datasets.harvest_id = harvest_id

    def record_harvested(self) -> None:
        """Record one successfully harvested dataset."""
        with self._lock:
            self._datasets.harvested_datasets += 1

    def record_failed(
        self,
        message: str,
        *,
        record_id: str | None = None,
        url: str | None = None,
    ) -> None:
        """Record one failed dataset and append a dataset-scoped issue."""
        with self._lock:
            self._datasets.failed_datasets += 1
            self._datasets.failures.append(
                HarvestIssue(
                    message=message,
                    kind=IssueKind.DATASET,
                    record_id=record_id,
                    url=url,
                )
            )

    def record_repository_issue(self, message: str, *, url: str | None = None) -> None:
        """Append a repository-level issue without incrementing failed datasets."""
        with self._lock:
            self._datasets.failures.append(
                HarvestIssue(
                    message=message,
                    kind=IssueKind.REPOSITORY,
                    url=url,
                )
            )

    def record_skipped(self) -> None:
        """Record one intentionally skipped dataset."""
        with self._lock:
            self._datasets.skipped_datasets += 1

    def add_studies(self, count: int = 1) -> None:
        """Add ``count`` studies to this repository's totals."""
        if count < 0:
            raise ValueError("study count must be non-negative")
        with self._lock:
            self._composition.total_studies += count

    def add_assays(self, count: int = 1) -> None:
        """Add ``count`` assays to this repository's totals."""
        if count < 0:
            raise ValueError("assay count must be non-negative")
        with self._lock:
            self._composition.total_assays += count

    def snapshot(self) -> RepositoryReport:
        """Return a format-neutral immutable view of current statistics."""
        with self._lock:
            datasets = self._datasets
            composition = self._composition
            closed_at = self._closed_at or datetime.now(UTC)
            duration = (closed_at - self._opened_at).total_seconds()
            if composition.total_studies == 0 and composition.total_assays == 0:
                total_studies: int | None = None
                total_assays: int | None = None
            else:
                total_studies = composition.total_studies
                total_assays = composition.total_assays
            return RepositoryReport(
                rdi=self._rdi,
                harvest_id=datasets.harvest_id,
                duration_seconds=duration,
                expected_datasets=datasets.expected_datasets,
                harvested_datasets=datasets.harvested_datasets,
                failed_datasets=datasets.failed_datasets,
                skipped_datasets=datasets.skipped_datasets,
                failures=tuple(datasets.failures),
                total_studies=total_studies,
                total_assays=total_assays,
            )


class HarvestReport:
    """Mutable harvest-run accumulator; serializers read finished snapshots."""

    def __init__(
        self,
        *,
        name: str = "FAIRagro Harvest Run",
        start_time: datetime | None = None,
    ) -> None:
        """Create a run report and record the authoritative start time."""
        self.name = name
        if start_time is None:
            self._start_time = datetime.now(UTC)
        else:
            self._start_time = _require_aware_utc(start_time, what="HarvestReport start_time")
        self._end_time: datetime | None = None
        self._scopes: list[RepositoryScope] = []
        self._scopes_lock = threading.Lock()

    @property
    def start_time(self) -> datetime:
        """Run start timestamp."""
        return self._start_time

    @property
    def end_time(self) -> datetime:
        """Run end timestamp.

        Raises:
            ValueError: If :meth:`finish` has not been called yet.
        """
        if self._end_time is None:
            raise ValueError("HarvestReport.finish() must be called before reading end_time")
        return self._end_time

    @property
    def duration_seconds(self) -> float:
        """Total harvest run duration in seconds."""
        return (self.end_time - self.start_time).total_seconds()

    @property
    def repository_reports(self) -> tuple[RepositoryReport, ...]:
        """Immutable snapshots of all repository scopes in open order."""
        with self._scopes_lock:
            scopes = list(self._scopes)
        return tuple(scope.snapshot() for scope in scopes)

    def open_repository(self, rdi: str, *, opened_at: datetime | None = None) -> RepositoryScope:
        """Open a repository scope handle for ``rdi`` (multiple may be open)."""
        scope = RepositoryScope(rdi, opened_at=opened_at)
        with self._scopes_lock:
            self._scopes.append(scope)
        return scope

    def finish(self, *, end_time: datetime | None = None) -> None:
        """Finish the harvest run, close open scopes, and record the end timestamp.

        Raises:
            ValueError: If :meth:`finish` has already been called.
        """
        if self._end_time is not None:
            raise ValueError("HarvestReport.finish() has already been called")
        if end_time is None:
            finished_at = datetime.now(UTC)
        else:
            finished_at = _require_aware_utc(end_time, what="HarvestReport end_time")
        with self._scopes_lock:
            scopes = list(self._scopes)
        for scope in scopes:
            scope.close(closed_at=finished_at)
        self._end_time = finished_at
