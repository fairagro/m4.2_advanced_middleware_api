"""JSON-LD harvest report serializer."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from middleware.shared.report.model import FailedRecord, HarvestReport, RepositoryReport

FAIRAGRO_HARVEST_REPORT_NS = "https://fairagro.github.io/m4.2_advanced_middleware_api/ns/harvest-report/v1/#"

_JSON_LD_CONTEXT = {
    "@vocab": "https://schema.org/",
    "schema": "https://schema.org/",
    "fairagro": FAIRAGRO_HARVEST_REPORT_NS,
}


def _format_iso_duration(seconds: float) -> str:
    """Serialize a duration value as an ISO 8601 duration string."""
    remainder = f"{seconds:.6f}".rstrip("0").rstrip(".")
    if remainder == "":
        remainder = "0"
    return f"PT{remainder}S"


def _format_iso_timestamp(value: datetime) -> str:
    """Format a timezone-aware datetime as an ISO 8601 UTC timestamp ending in Z.

    Raises:
        ValueError: If ``value`` is naive (no ``tzinfo``). Callers must supply
            timezone-aware UTC times; treating naive values as local time would
            silently shift the wall clock on non-UTC hosts.
    """
    if value.tzinfo is None:
        raise ValueError("HarvestReport timestamps must be timezone-aware UTC")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _failed_record_to_jsonld(record: FailedRecord) -> dict[str, Any]:
    """Convert a failed record to its JSON-LD object, omitting unset fields."""
    result: dict[str, Any] = {"fairagro:message": record.message}
    if record.record_id:
        result["fairagro:recordId"] = record.record_id
    if record.url:
        result["fairagro:url"] = record.url
    return result


def _repository_to_jsonld(report: RepositoryReport) -> dict[str, Any]:
    """Convert a repository report to a schema.org EntryPoint JSON-LD object."""
    result: dict[str, Any] = {
        "@type": "schema:EntryPoint",
        "name": report.rdi,
        "identifier": report.rdi,
        "schema:duration": _format_iso_duration(report.duration_seconds),
        "fairagro:harvestId": report.harvest_id,
        "fairagro:skippedDatasets": report.skipped_datasets,
    }
    if report.harvested_datasets is not None:
        result["fairagro:harvestedDatasets"] = report.harvested_datasets
    if report.expected_datasets is not None:
        result["fairagro:expectedDatasets"] = report.expected_datasets
    if report.failed_datasets is not None:
        result["fairagro:failedDatasets"] = report.failed_datasets
    if report.total_studies is not None:
        result["fairagro:totalStudies"] = report.total_studies
    if report.total_assays is not None:
        result["fairagro:totalAssays"] = report.total_assays
    if report.failed_records:
        result["fairagro:failedRecords"] = [_failed_record_to_jsonld(record) for record in report.failed_records]
    return result


class JsonLdReportSerializer:
    """Render a harvest report as an operator-readable JSON-LD document."""

    def __init__(self, *, indent: int = 2) -> None:
        """Configure JSON indentation for operator-readable output."""
        self._indent = indent

    def render(self, report: HarvestReport) -> str:
        """Return the report as indented JSON-LD text."""
        document: dict[str, Any] = {
            "@context": _JSON_LD_CONTEXT,
            "@type": "schema:Action",
            "name": report.name,
            "schema:startTime": _format_iso_timestamp(report.start_time),
            "schema:endTime": _format_iso_timestamp(report.end_time),
            "fairagro:harvestDurationSeconds": report.duration_seconds,
            "schema:result": [_repository_to_jsonld(entry) for entry in report.repository_reports],
        }
        return json.dumps(document, ensure_ascii=False, indent=self._indent)
