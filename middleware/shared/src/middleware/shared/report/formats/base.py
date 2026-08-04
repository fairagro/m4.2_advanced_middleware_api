"""Report serializer protocol."""

from __future__ import annotations

from typing import Protocol

from middleware.shared.report.model import HarvestReport


class ReportSerializer(Protocol):
    """Serialize a harvest report to a string in a specific format."""

    def render(self, report: HarvestReport) -> str:
        """Return the serialized report document."""
        raise NotImplementedError
