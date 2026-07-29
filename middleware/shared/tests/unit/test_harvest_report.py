"""Unit tests for the shared harvest report library."""

from __future__ import annotations

import json
import logging
from dataclasses import fields
from datetime import UTC, datetime
from typing import Any

import pytest

from middleware.shared.report import (
    FAIRAGRO_HARVEST_REPORT_NS,
    FailedRecord,
    HarvestReport,
    JsonLdReportSerializer,
    RepositoryReport,
    print_report,
)

_START = datetime(2026, 5, 6, 14, 0, 0, tzinfo=UTC)
_END = datetime(2026, 5, 6, 14, 3, 45, tzinfo=UTC)


def _sample_repo(**overrides: Any) -> RepositoryReport:
    """Build a repository report with sensible defaults."""
    values: dict[str, Any] = {
        "rdi": "bonares",
        "harvest_id": "harvest-1",
        "duration_seconds": 12.3,
        "expected_datasets": 100,
        "harvested_datasets": 95,
        "failed_datasets": 5,
        "skipped_datasets": 2,
        "failed_records": (
            FailedRecord(
                message="map failed",
                record_id="frl:123",
                url="https://example.test/frl:123",
            ),
        ),
    }
    values.update(overrides)
    return RepositoryReport(**values)


def _sample_report(
    repositories: list[RepositoryReport] | None = None,
) -> HarvestReport:
    """Build a harvest run report spanning a fixed UTC window."""
    return HarvestReport(
        start_time=_START,
        end_time=_END,
        repository_reports=([_sample_repo()] if repositories is None else repositories),
    )


def test_failed_record_with_optional_identifiers() -> None:
    """Failed records expose message, record id, and URL when provided."""
    record = FailedRecord(message="boom", record_id="id-1", url="https://x.test")
    assert record.message == "boom"
    assert record.record_id == "id-1"
    assert record.url == "https://x.test"


def test_failed_record_message_only() -> None:
    """Optional identifiers are unset when omitted."""
    record = FailedRecord(message="boom")
    assert record.record_id is None
    assert record.url is None


def test_harvest_report_with_one_repository() -> None:
    """A run report exposes timing and a single repository entry."""
    report = _sample_report()
    assert report.start_time == _START
    assert len(report.repository_reports) == 1
    assert report.repository_reports[0].rdi == "bonares"
    assert report.duration_seconds == (_END - _START).total_seconds()


def test_harvest_report_with_no_repositories() -> None:
    """An empty repository list is preserved."""
    report = _sample_report(repositories=[])
    assert not report.repository_reports
    assert report.duration_seconds == (_END - _START).total_seconds()


def test_optional_study_and_assay_counts_set() -> None:
    """Study and assay totals are available when provided."""
    total_studies = 10
    total_assays = 20
    repo = _sample_repo(total_studies=total_studies, total_assays=total_assays)
    assert repo.total_studies == total_studies
    assert repo.total_assays == total_assays


def test_optional_study_and_assay_counts_unset() -> None:
    """Unset study and assay totals are None, not zero."""
    repo = _sample_repo()
    assert repo.total_studies is None
    assert repo.total_assays is None


def test_model_is_format_neutral() -> None:
    """The domain model does not embed a serialized document."""
    report = _sample_report()
    assert not hasattr(report, "to_jsonld")
    assert "repository_reports" in {field.name for field in fields(report)}


def test_jsonld_context_and_types() -> None:
    """JSON-LD uses schema.org Action with EntryPoint results."""
    document = json.loads(JsonLdReportSerializer().render(_sample_report()))
    assert document["@context"]["@vocab"] == "https://schema.org/"
    assert document["@context"]["schema"] == "https://schema.org/"
    assert document["@context"]["fairagro"] == FAIRAGRO_HARVEST_REPORT_NS
    assert document["@context"]["fairagro"].endswith("/ns/harvest-report/v1/#")
    assert document["@type"] == "schema:Action"
    assert document["schema:result"][0]["@type"] == "schema:EntryPoint"


def test_jsonld_timestamps_and_durations() -> None:
    """Timestamps end with Z and durations use ISO 8601 / seconds."""
    report = _sample_report()
    document = json.loads(JsonLdReportSerializer().render(report))
    assert document["schema:startTime"].endswith("Z")
    assert document["schema:endTime"].endswith("Z")
    assert document["fairagro:harvestDurationSeconds"] == report.duration_seconds
    assert document["schema:result"][0]["schema:duration"].startswith("PT")


def test_jsonld_metrics_and_failed_records() -> None:
    """Fairagro metrics and nested failed records are emitted."""
    repo = _sample_repo()
    entry = json.loads(JsonLdReportSerializer().render(_sample_report(repositories=[repo])))["schema:result"][0]
    assert entry["fairagro:harvestId"] == repo.harvest_id
    assert entry["fairagro:expectedDatasets"] == repo.expected_datasets
    assert entry["fairagro:harvestedDatasets"] == repo.harvested_datasets
    assert entry["fairagro:failedDatasets"] == repo.failed_datasets
    assert entry["fairagro:skippedDatasets"] == repo.skipped_datasets
    failed = repo.failed_records[0]
    assert entry["fairagro:failedRecords"] == [
        {
            "fairagro:message": failed.message,
            "fairagro:recordId": failed.record_id,
            "fairagro:url": failed.url,
        }
    ]


def test_jsonld_optional_study_and_assay_totals() -> None:
    """Optional study and assay totals appear as fairagro properties."""
    total_studies = 3
    total_assays = 7
    report = _sample_report(repositories=[_sample_repo(total_studies=total_studies, total_assays=total_assays)])
    entry = json.loads(JsonLdReportSerializer().render(report))["schema:result"][0]
    assert entry["fairagro:totalStudies"] == total_studies
    assert entry["fairagro:totalAssays"] == total_assays


def test_jsonld_omits_unset_expected_datasets() -> None:
    """Unset optional counts are omitted rather than null."""
    report = _sample_report(
        repositories=[
            _sample_repo(
                expected_datasets=None,
                harvested_datasets=None,
                failed_datasets=None,
                total_studies=None,
                total_assays=None,
            )
        ]
    )
    entry = json.loads(JsonLdReportSerializer().render(report))["schema:result"][0]
    assert "fairagro:expectedDatasets" not in entry
    assert "fairagro:harvestedDatasets" not in entry
    assert "fairagro:failedDatasets" not in entry
    assert "fairagro:totalStudies" not in entry
    assert "fairagro:totalAssays" not in entry
    assert "fairagro:harvestId" in entry


def test_jsonld_omits_empty_failed_records() -> None:
    """Empty failed-record lists are omitted from JSON-LD."""
    report = _sample_report(repositories=[_sample_repo(failed_records=())])
    entry = json.loads(JsonLdReportSerializer().render(report))["schema:result"][0]
    assert "fairagro:failedRecords" not in entry


def test_jsonld_empty_result_array() -> None:
    """A run with no repositories emits an empty result array."""
    document = json.loads(JsonLdReportSerializer().render(_sample_report(repositories=[])))
    assert document["schema:result"] == []


def test_print_report_writes_jsonld_to_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    """print_report writes a JSON-LD document to stdout."""
    print_report(_sample_report())
    captured = capsys.readouterr()
    document = json.loads(captured.out)
    assert document["@type"] == "schema:Action"
    assert captured.err == ""


def test_print_report_does_not_raise_on_serialization_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Serialization failures are logged and do not propagate."""

    class _BoomSerializer:
        def __init__(self) -> None:
            self._fail = True

        def render(self, report: HarvestReport) -> str:
            if self._fail:
                raise ValueError(f"cannot serialise {type(report).__name__}")
            return "{}"

    with caplog.at_level(logging.WARNING):
        print_report(_sample_report(), serializer=_BoomSerializer())

    assert any("Failed to serialise harvest report" in message for message in caplog.messages)
