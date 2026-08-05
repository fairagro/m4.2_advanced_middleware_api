"""JSON-LD serializer for HarvestReport (harvester-compatible wire shape)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from middleware.shared.report.model import HarvestIssue, HarvestReport, RepositoryReport

FAIRAGRO_HARVEST_REPORT_NS = "https://fairagro.github.io/m4.2_advanced_middleware_api/ns/harvest-report/v2/#"

_JSON_LD_CONTEXT: dict[str, Any] = {
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
    """Format a UTC datetime value as an ISO 8601 timestamp ending in Z."""
    if value.tzinfo is None:
        raise ValueError("HarvestReport timestamps must be timezone-aware UTC")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _failure_node(issue: HarvestIssue) -> dict[str, Any]:
    node: dict[str, Any] = {
        "fairagro:message": issue.message,
        "fairagro:kind": issue.kind.value,
    }
    if issue.record_id is not None:
        node["fairagro:recordId"] = issue.record_id
    if issue.url is not None:
        node["fairagro:url"] = issue.url
    return node


def _entry_point(repo: RepositoryReport) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "@type": "schema:EntryPoint",
        "@id": repo.rdi,
        "name": repo.rdi,
        "identifier": repo.rdi,
        "schema:duration": _format_iso_duration(repo.duration_seconds),
        "fairagro:harvestId": repo.harvest_id,
        "fairagro:harvestedDatasets": repo.harvested_datasets,
        "fairagro:failedDatasets": repo.failed_datasets,
        "fairagro:skippedDatasets": repo.skipped_datasets,
    }
    if repo.expected_datasets is not None:
        entry["fairagro:expectedDatasets"] = repo.expected_datasets
    if repo.total_studies is not None:
        entry["fairagro:totalStudies"] = repo.total_studies
    if repo.total_assays is not None:
        entry["fairagro:totalAssays"] = repo.total_assays
    if repo.failures:
        entry["fairagro:failures"] = [_failure_node(issue) for issue in repo.failures]
    return entry


class JsonLdReportSerializer:
    """Serialize a finished :class:`HarvestReport` to a JSON-LD document string."""

    context: dict[str, Any] = _JSON_LD_CONTEXT

    def render(self, report: HarvestReport) -> str:
        """Return a JSON-LD document encoding the finished harvest run.

        Raises:
            ValueError: If :meth:`HarvestReport.finish` has not been called, or
                timestamps are naive.
        """
        start = _format_iso_timestamp(report.start_time)
        end = _format_iso_timestamp(report.end_time)
        document: dict[str, Any] = {
            "@context": self.context,
            "@type": "schema:Action",
            "name": report.name,
            "schema:startTime": start,
            "schema:endTime": end,
            "fairagro:harvestDurationSeconds": report.duration_seconds,
            "schema:result": [_entry_point(repo) for repo in report.repository_reports],
        }
        return json.dumps(document, indent=2, ensure_ascii=False) + "\n"
