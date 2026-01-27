"""Statistics tracking for the conversion process."""

import json
from pydantic import BaseModel, ConfigDict


class ProcessingStats(BaseModel):
    """Statistics for the conversion process."""

    found_datasets: int = 0
    total_studies: int = 0
    total_assays: int = 0
    failed_datasets: int = 0
    failed_ids: list[str] = []
    duration_seconds: float = 0.0

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def merge(self, other: "ProcessingStats") -> None:
        """Merge another stats object into this one."""
        self.found_datasets += other.found_datasets
        self.failed_datasets += other.failed_datasets
        self.failed_ids.extend(other.failed_ids)
        # Note: total_studies, total_assays are counted centrally, not merged from workers

    def to_jsonld(self, rdi_identifier: str | None = None, rdi_url: str | None = None) -> str:
        """Return JSON-LD representation of stats using Schema.org and PROV terms."""
        # Convert duration to ISO 8601 duration format (PTx.xS)
        duration_iso = f"PT{self.duration_seconds:.2f}S"

        ld_struct = {
            "@context": {
                "schema": "http://schema.org/",
                "prov": "http://www.w3.org/ns/prov#",
                "void": "http://rdfs.org/ns/void#",
                "xsd": "http://www.w3.org/2001/XMLSchema#",
                # Map duration to schema:duration (Expects ISO 8601 string)
                "duration": {"@id": "schema:duration", "@type": "schema:Duration"},
                # Map failed IDs to schema:error (list of strings)
                "failed_ids": {"@id": "schema:error", "@container": "@set"},
                # Map status
                "status": {"@id": "schema:actionStatus"},
                # Use VoID for counts (statistic items)
                "found_datasets": {"@id": "void:entities", "@type": "xsd:integer"},
                # Custom descriptive terms for study/assay counts as they are domain specific
                # We map them to schema:result for semantics, but keep key names
                "total_studies": {"@id": "schema:result", "@type": "xsd:integer"},
                "total_assays": {"@id": "schema:result", "@type": "xsd:integer"},
            },
            "@type": ["prov:Activity", "schema:CreateAction"],
            "schema:name": "SQL to ARC Conversion Run",
            "schema:instrument": {
                "@type": "schema:SoftwareApplication",
                "schema:name": "FAIRagro Middleware SQL-to-ARC",
            },
            # Process status
            "status": "schema:CompletedActionStatus" if self.failed_datasets == 0 else "schema:FailedActionStatus",
            # Metrics
            "duration": duration_iso,
            "duration_seconds": round(self.duration_seconds, 2),  # Keep raw float for easy parsing
            "found_datasets": self.found_datasets,
            "total_studies": self.total_studies,
            "total_assays": self.total_assays,
            "failed_datasets": self.failed_datasets,
            "failed_ids": sorted(self.failed_ids),
        }

        if rdi_identifier and rdi_url:
            ld_struct["prov:used"] = {
                "@id": rdi_url,
                "@type": "schema:Organization",  # RDI acts as an Organization/Service
                "schema:identifier": rdi_identifier,
                "schema:name": f"Research Data Infrastructure: {rdi_identifier}",
            }

        return json.dumps(ld_struct, indent=2)
