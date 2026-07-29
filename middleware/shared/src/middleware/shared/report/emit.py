"""Stdout emission for harvest reports."""

from __future__ import annotations

import logging

from middleware.shared.report.formats.base import ReportSerializer
from middleware.shared.report.formats.jsonld import JsonLdReportSerializer
from middleware.shared.report.model import HarvestReport

logger = logging.getLogger(__name__)


def print_report(
    report: HarvestReport,
    serializer: ReportSerializer | None = None,
) -> None:
    """Serialize the report and print it to stdout.

    Serialization or print failures are logged as warnings and do not raise.
    """
    active_serializer: ReportSerializer = serializer or JsonLdReportSerializer()
    try:
        print(active_serializer.render(report))
    except (OSError, OverflowError, TypeError, ValueError) as exc:
        logger.warning("Failed to serialise harvest report: %s", exc)
