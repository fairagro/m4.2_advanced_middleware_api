"""Unit tests for the shared harvest report counting API and JSON-LD serializer."""

from __future__ import annotations

import asyncio
import json
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from middleware.shared.report import (
    FAIRAGRO_HARVEST_REPORT_NS,
    HarvestIssue,
    HarvestReport,
    IssueKind,
    JsonLdReportSerializer,
    RepositoryScope,
)

_START = datetime(2026, 5, 6, 14, 0, 0, tzinfo=UTC)
_END = datetime(2026, 5, 6, 14, 3, 45, tzinfo=UTC)
_SCOPE_CLOSE = datetime(2026, 5, 6, 14, 0, 17, tzinfo=UTC)

_SCOPE_DURATION_SECONDS = 12.5
_SAMPLE_EXPECTED = 100
_SAMPLE_HARVESTED = 95
_SAMPLE_FAILED = 5
_SAMPLE_SKIPPED = 2
_EXPECTED_COUNT = 10
_HARVESTED_TWICE = 2
_STUDIES = 3
_ASSAYS = 7
_REPO_COUNT = 2
_ASYNC_HARVESTED = 100
_ASYNC_FAILED = 40
_PARALLEL_HARVESTED = 80
_THREAD_HARVESTED = 200
_THREAD_FAILED = 50


def _finished_report(
    *,
    populate: Callable[[HarvestReport], None] | None = None,
    start_time: datetime = _START,
    end_time: datetime = _END,
) -> HarvestReport:
    """Build a finished report; optional ``populate(report)`` opens scopes."""
    report = HarvestReport(start_time=start_time)
    if populate is not None:
        populate(report)
    report.finish(end_time=end_time)
    return report


def _open_sample_scope(report: HarvestReport) -> None:
    """Open one sample repository scope with typical counts."""
    scope = report.open_repository("bonares")
    scope.set_expected_datasets(_SAMPLE_EXPECTED)
    scope.set_harvest_id("harvest-1")
    for _ in range(_SAMPLE_HARVESTED):
        scope.record_harvested()
    for i in range(_SAMPLE_FAILED):
        scope.record_failed(
            "map failed" if i == 0 else f"fail-{i}",
            record_id="frl:123" if i == 0 else None,
            url="https://example.test/frl:123" if i == 0 else None,
        )
    for _ in range(_SAMPLE_SKIPPED):
        scope.record_skipped()
    scope.close(closed_at=_SCOPE_CLOSE)


def test_harvest_issue_with_optional_identifiers() -> None:
    """Harvest issues expose message, kind, record id, and URL when provided."""
    issue = HarvestIssue(
        message="boom",
        kind=IssueKind.DATASET,
        record_id="id-1",
        url="https://x.test",
    )
    assert issue.message == "boom"
    assert issue.kind is IssueKind.DATASET
    assert issue.record_id == "id-1"
    assert issue.url == "https://x.test"


def test_harvest_issue_message_only() -> None:
    """Optional identifiers default to unset; kind defaults to dataset."""
    issue = HarvestIssue(message="boom")
    assert issue.kind is IssueKind.DATASET
    assert issue.record_id is None
    assert issue.url is None


def test_harvest_issue_coerces_kind_string() -> None:
    """String kind values are normalized to IssueKind."""
    issue = HarvestIssue(message="boom", kind="repository")  # type: ignore[arg-type]
    assert issue.kind is IssueKind.REPOSITORY


def test_harvest_issue_rejects_invalid_kind() -> None:
    """Unknown kind values raise ValueError."""
    with pytest.raises(ValueError, match="invalid issue kind"):
        HarvestIssue(message="boom", kind="nope")  # type: ignore[arg-type]


def test_harvest_issue_rejects_record_id_for_repository() -> None:
    """Repository issues must not carry a dataset record id."""
    with pytest.raises(ValueError, match="record_id"):
        HarvestIssue(
            message="sitemap failed",
            kind=IssueKind.REPOSITORY,
            record_id="should-not-exist",
        )


def test_mutable_run_records_start_time() -> None:
    """Creating a report records an authoritative start timestamp."""
    report = HarvestReport(start_time=_START)
    assert report.start_time == _START


def test_finish_records_end_time_and_duration() -> None:
    """Finishing the run records end time used for duration."""
    report = HarvestReport(start_time=_START)
    report.finish(end_time=_END)
    assert report.end_time == _END
    assert report.duration_seconds == (_END - _START).total_seconds()


def test_end_time_requires_finish() -> None:
    """Reading end time before finish raises."""
    report = HarvestReport(start_time=_START)
    with pytest.raises(ValueError, match="finish"):
        _ = report.end_time


def test_open_and_close_repository_scope() -> None:
    """Open/close records RDI and per-scope duration."""
    report = HarvestReport(start_time=_START)
    opened = datetime(2026, 5, 6, 14, 1, 0, tzinfo=UTC)
    closed = opened + timedelta(seconds=_SCOPE_DURATION_SECONDS)
    scope = report.open_repository("bonares", opened_at=opened)
    scope.close(closed_at=closed)
    report.finish(end_time=_END)
    repos = report.repository_reports
    assert len(repos) == 1
    assert repos[0].rdi == "bonares"
    assert repos[0].duration_seconds == _SCOPE_DURATION_SECONDS


def test_concurrent_scopes_are_isolated() -> None:
    """Counting on one handle does not change another handle's totals."""
    report = HarvestReport(start_time=_START)
    a = report.open_repository("rdi-a")
    b = report.open_repository("rdi-b")
    a.record_harvested()
    a.record_harvested()
    b.record_failed("oops")
    snap_a = a.snapshot()
    snap_b = b.snapshot()
    assert snap_a.harvested_datasets == _HARVESTED_TWICE
    assert snap_a.failed_datasets == 0
    assert snap_b.harvested_datasets == 0
    assert snap_b.failed_datasets == 1


def test_counting_increments() -> None:
    """Counting methods increment harvested, failed, and skipped."""
    report = HarvestReport(start_time=_START)
    scope = report.open_repository("bonares")
    scope.set_expected_datasets(_EXPECTED_COUNT)
    scope.set_harvest_id("h-1")
    scope.record_harvested()
    scope.record_harvested()
    scope.record_failed("bad", record_id="r1", url="https://x.test/r1")
    scope.record_skipped()
    scope.add_studies(_STUDIES)
    scope.add_assays(_ASSAYS)
    snap = scope.snapshot()
    assert snap.expected_datasets == _EXPECTED_COUNT
    assert snap.harvest_id == "h-1"
    assert snap.harvested_datasets == _HARVESTED_TWICE
    assert snap.failed_datasets == 1
    assert snap.skipped_datasets == 1
    assert snap.total_studies == _STUDIES
    assert snap.total_assays == _ASSAYS
    assert snap.failures == (
        HarvestIssue(
            message="bad",
            kind=IssueKind.DATASET,
            record_id="r1",
            url="https://x.test/r1",
        ),
    )


def test_repository_issue_does_not_increment_failed_datasets() -> None:
    """Repository-level issues append to failures without counting datasets."""
    report = HarvestReport(start_time=_START)
    scope = report.open_repository("publisso")
    scope.record_repository_issue(
        "Sitemap discovery failed for https://frl.publisso.de/find",
        url="https://frl.publisso.de/find",
    )
    snap = scope.snapshot()
    assert snap.failed_datasets == 0
    assert snap.failures == (
        HarvestIssue(
            message="Sitemap discovery failed for https://frl.publisso.de/find",
            kind=IssueKind.REPOSITORY,
            url="https://frl.publisso.de/find",
        ),
    )


def test_study_assay_omit_when_both_zero() -> None:
    """Unset study/assay totals are None when never incremented."""
    report = HarvestReport(start_time=_START)
    scope = report.open_repository("bonares")
    snap = scope.snapshot()
    assert snap.total_studies is None
    assert snap.total_assays is None


def test_render_requires_finish() -> None:
    """JSON-LD render requires finish()."""
    report = HarvestReport(start_time=_START)
    with pytest.raises(ValueError, match="finish"):
        JsonLdReportSerializer().render(report)


def test_naive_start_time_rejected() -> None:
    """Naive start times must not be silently treated as local time."""
    with pytest.raises(ValueError, match="timezone-aware"):
        HarvestReport(start_time=datetime(2026, 5, 6, 14, 0, 0))


def test_naive_opened_at_rejected() -> None:
    """Naive opened_at on a repository scope is rejected."""
    with pytest.raises(ValueError, match="timezone-aware"):
        RepositoryScope("bonares", opened_at=datetime(2026, 5, 6, 14, 0, 0))


def test_naive_closed_at_rejected() -> None:
    """Naive closed_at on a repository scope is rejected."""
    scope = RepositoryScope("bonares", opened_at=_START)
    with pytest.raises(ValueError, match="timezone-aware"):
        scope.close(closed_at=datetime(2026, 5, 6, 14, 1, 0))


def test_finish_closes_open_scopes_deterministically() -> None:
    """finish() closes still-open scopes at the run end time."""
    opened = datetime(2026, 5, 6, 14, 0, 0, tzinfo=UTC)
    report = HarvestReport(start_time=opened)
    scope = report.open_repository("bonares", opened_at=opened)
    report.finish(end_time=_END)
    assert scope.snapshot().duration_seconds == (_END - opened).total_seconds()
    assert report.end_time == _END


def test_finish_is_single_shot() -> None:
    """Calling finish() twice raises so run and scope durations stay aligned."""
    report = HarvestReport(start_time=_START)
    report.open_repository("bonares", opened_at=_START)
    report.finish(end_time=_END)
    with pytest.raises(ValueError, match="already been called"):
        report.finish(end_time=_END + timedelta(seconds=30))
    assert report.end_time == _END


def test_require_aware_utc_normalizes_non_utc() -> None:
    """Timezone-aware non-UTC timestamps are stored as UTC equivalents."""
    berlin = ZoneInfo("Europe/Berlin")
    local_start = datetime(2026, 5, 6, 16, 0, 0, tzinfo=berlin)  # UTC+2 in May
    report = HarvestReport(start_time=local_start)
    assert report.start_time == datetime(2026, 5, 6, 14, 0, 0, tzinfo=UTC)
    assert report.start_time.tzinfo == UTC


def test_jsonld_context_and_types() -> None:
    """JSON-LD uses schema.org Action with EntryPoint results."""
    report = _finished_report(populate=_open_sample_scope)
    document = json.loads(JsonLdReportSerializer().render(report))
    assert document["@context"]["@vocab"] == "https://schema.org/"
    assert document["@context"]["schema"] == "https://schema.org/"
    assert document["@context"]["fairagro"] == FAIRAGRO_HARVEST_REPORT_NS
    assert document["@context"]["fairagro"].endswith("/ns/harvest-report/v2/#")
    assert document["@type"] == "schema:Action"
    assert document["schema:result"][0]["@type"] == "schema:EntryPoint"


def test_jsonld_timestamps_and_durations() -> None:
    """Timestamps end with Z; run duration is seconds; scope duration is ISO."""
    report = _finished_report(populate=_open_sample_scope)
    document = json.loads(JsonLdReportSerializer().render(report))
    assert document["schema:startTime"].endswith("Z")
    assert document["schema:endTime"].endswith("Z")
    assert document["fairagro:harvestDurationSeconds"] == report.duration_seconds
    assert document["schema:result"][0]["schema:duration"].startswith("PT")


def test_jsonld_metrics_and_failures() -> None:
    """Fairagro metrics and nested failure issues are emitted."""
    report = _finished_report(populate=_open_sample_scope)
    entry = json.loads(JsonLdReportSerializer().render(report))["schema:result"][0]
    assert entry["@id"] == "bonares"
    assert entry["fairagro:harvestId"] == "harvest-1"
    assert entry["fairagro:expectedDatasets"] == _SAMPLE_EXPECTED
    assert entry["fairagro:harvestedDatasets"] == _SAMPLE_HARVESTED
    assert entry["fairagro:failedDatasets"] == _SAMPLE_FAILED
    assert entry["fairagro:skippedDatasets"] == _SAMPLE_SKIPPED
    assert entry["fairagro:failures"][0] == {
        "fairagro:message": "map failed",
        "fairagro:kind": "dataset",
        "fairagro:recordId": "frl:123",
        "fairagro:url": "https://example.test/frl:123",
    }


def test_jsonld_repository_issue_without_failed_datasets() -> None:
    """Repository issues appear under failures while failedDatasets stays 0."""

    def populate(report: HarvestReport) -> None:
        scope = report.open_repository("publisso")
        scope.record_repository_issue(
            "Sitemap discovery failed",
            url="https://frl.publisso.de/find",
        )
        scope.close(closed_at=_SCOPE_CLOSE)

    report = _finished_report(populate=populate)
    entry = json.loads(JsonLdReportSerializer().render(report))["schema:result"][0]
    assert entry["fairagro:failedDatasets"] == 0
    assert entry["fairagro:failures"] == [
        {
            "fairagro:message": "Sitemap discovery failed",
            "fairagro:kind": "repository",
            "fairagro:url": "https://frl.publisso.de/find",
        }
    ]


def test_jsonld_optional_study_and_assay_totals() -> None:
    """Optional study and assay totals appear as fairagro properties."""

    def populate(report: HarvestReport) -> None:
        scope = report.open_repository("sql")
        scope.add_studies(_STUDIES)
        scope.add_assays(_ASSAYS)
        scope.close(closed_at=_SCOPE_CLOSE)

    report = _finished_report(populate=populate)
    entry = json.loads(JsonLdReportSerializer().render(report))["schema:result"][0]
    assert entry["fairagro:totalStudies"] == _STUDIES
    assert entry["fairagro:totalAssays"] == _ASSAYS


def test_jsonld_omits_unset_expected_and_study_assay() -> None:
    """Unset expected and zero study/assay totals are omitted."""

    def populate(report: HarvestReport) -> None:
        scope = report.open_repository("bonares")
        scope.set_harvest_id("harvest-1")
        scope.record_harvested()
        scope.close(closed_at=_SCOPE_CLOSE)

    report = _finished_report(populate=populate)
    entry = json.loads(JsonLdReportSerializer().render(report))["schema:result"][0]
    assert "fairagro:expectedDatasets" not in entry
    assert "fairagro:totalStudies" not in entry
    assert "fairagro:totalAssays" not in entry
    assert entry["fairagro:harvestedDatasets"] == 1
    assert entry["fairagro:failedDatasets"] == 0
    assert entry["fairagro:skippedDatasets"] == 0
    assert entry["fairagro:harvestId"] == "harvest-1"


def test_jsonld_harvest_id_null_when_unset() -> None:
    """Unset harvest id is emitted as JSON null."""

    def populate(report: HarvestReport) -> None:
        scope = report.open_repository("bonares")
        scope.close(closed_at=_SCOPE_CLOSE)

    report = _finished_report(populate=populate)
    entry = json.loads(JsonLdReportSerializer().render(report))["schema:result"][0]
    assert entry["fairagro:harvestId"] is None


def test_jsonld_omits_empty_failures() -> None:
    """Empty failure lists are omitted from JSON-LD."""

    def populate(report: HarvestReport) -> None:
        scope = report.open_repository("bonares")
        scope.close(closed_at=_SCOPE_CLOSE)

    report = _finished_report(populate=populate)
    entry = json.loads(JsonLdReportSerializer().render(report))["schema:result"][0]
    assert "fairagro:failures" not in entry


def test_jsonld_empty_result_array() -> None:
    """A run with no repositories emits an empty result array."""
    document = json.loads(JsonLdReportSerializer().render(_finished_report()))
    assert document["schema:result"] == []


def test_jsonld_multi_repository_action() -> None:
    """Two scopes produce two EntryPoints in schema:result."""

    def populate(report: HarvestReport) -> None:
        a = report.open_repository("rdi-a")
        b = report.open_repository("rdi-b")
        a.close(closed_at=_SCOPE_CLOSE)
        b.close(closed_at=_SCOPE_CLOSE)

    report = _finished_report(populate=populate)
    document = json.loads(JsonLdReportSerializer().render(report))
    assert len(document["schema:result"]) == _REPO_COUNT
    assert all(e["@type"] == "schema:EntryPoint" for e in document["schema:result"])


def test_serializer_returns_string() -> None:
    """The JSON-LD serializer returns a document string, not a dict."""
    rendered = JsonLdReportSerializer().render(_finished_report())
    assert isinstance(rendered, str)
    assert json.loads(rendered)["@type"] == "schema:Action"


def test_thread_safe_counting_on_one_handle() -> None:
    """Concurrent thread updates on one handle do not lose counts."""
    report = HarvestReport(start_time=_START)
    scope = report.open_repository("bonares")

    def harvest(_i: int) -> None:
        scope.record_harvested()

    def fail(_i: int) -> None:
        scope.record_failed("x")

    with ThreadPoolExecutor(max_workers=16) as pool:
        list(pool.map(harvest, range(_THREAD_HARVESTED)))
        list(pool.map(fail, range(_THREAD_FAILED)))

    snap = scope.snapshot()
    assert snap.harvested_datasets == _THREAD_HARVESTED
    assert snap.failed_datasets == _THREAD_FAILED


def test_asyncio_interleaved_counting() -> None:
    """Interleaved asyncio tasks on one handle preserve totals."""
    report = HarvestReport(start_time=_START)
    scope = report.open_repository("bonares")

    async def run() -> None:
        async def harvested() -> None:
            for _ in range(_ASYNC_HARVESTED):
                scope.record_harvested()
                await asyncio.sleep(0)

        async def failed() -> None:
            for _ in range(_ASYNC_FAILED):
                scope.record_failed("e")
                await asyncio.sleep(0)

        await asyncio.gather(harvested(), failed())

    asyncio.run(run())
    snap = scope.snapshot()
    assert snap.harvested_datasets == _ASYNC_HARVESTED
    assert snap.failed_datasets == _ASYNC_FAILED


def test_parallel_rdis_do_not_cross_count() -> None:
    """Concurrent tasks on different handles stay isolated."""
    report = HarvestReport(start_time=_START)
    first = report.open_repository("rdi-a")
    second = report.open_repository("rdi-b")
    barrier = threading.Barrier(_REPO_COUNT)

    def only_first() -> None:
        barrier.wait()
        for _ in range(_PARALLEL_HARVESTED):
            first.record_harvested()

    def idle_second() -> None:
        barrier.wait()

    t1 = threading.Thread(target=only_first)
    t2 = threading.Thread(target=idle_second)
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    assert first.snapshot().harvested_datasets == _PARALLEL_HARVESTED
    assert second.snapshot().harvested_datasets == 0
