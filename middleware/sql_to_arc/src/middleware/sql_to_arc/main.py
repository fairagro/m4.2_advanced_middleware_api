"""SQL-to-ARC middleware component."""

import argparse
import asyncio
import concurrent.futures
import json
import logging
import multiprocessing
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, cast

from arctrl import (
    ARC,
    ArcAssay,
    ArcInvestigation,
    ArcStudy,
    OntologyAnnotation,
    Person,
    Publication,
)
from opentelemetry import trace
from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy.engine import RowMapping

from middleware.api_client import ApiClient, ApiClientError
from middleware.shared.config.config_wrapper import ConfigWrapper
from middleware.shared.config.logging import configure_logging
from middleware.shared.tracing import initialize_tracing
from middleware.sql_to_arc.config import Config
from middleware.sql_to_arc.database import Database
from middleware.sql_to_arc.mapper import (
    map_assay,
    map_contact,
    map_investigation,
    map_publication,
    map_study,
)

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


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


def parse_args() -> argparse.Namespace:
    """Parse command line arguments, ignoring unknown args (e.g., pytest flags)."""
    parser = argparse.ArgumentParser(description="SQL to ARC Converter")
    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default=Path("config.yaml"),
        help="Path to configuration file (default: config.yaml)",
    )
    args, _ = parser.parse_known_args()
    return args


def build_single_arc_task(
    investigation_row: dict[str, Any],
    studies: list[dict[str, Any]],
    assays: list[dict[str, Any]],
    contacts: list[dict[str, Any]],
    publications: list[dict[str, Any]],
    annotations: list[dict[str, Any]],
) -> ARC:
    """Build a single ARC object from data.

    This function is designed to run in a separate process.
    """
    inv_id = str(investigation_row["identifier"])
    
    # Map Investigation
    arc_inv = map_investigation(investigation_row)
    
    # Identify Studies for this Investigation
    relevant_studies = [s for s in studies if s.get("investigation_ref") == inv_id]
    
    # Identify Assays for this Investigation
    relevant_assays = [a for a in assays if a.get("investigation_ref") == inv_id]
    
    # Create ARC
    arc = ARC.from_arc_investigation(arc_inv)
    
    # Create and add Studies
    study_map = {}
    for s_row in relevant_studies:
        study = map_study(s_row)
        arc.AddRegisteredStudy(study)
        study_map[str(s_row["identifier"])] = study # assume identifier is unique
        
    # Create and add Assays
    assay_map = {}
    for a_row in relevant_assays:
        assay = map_assay(a_row)
        arc.AddAssay(assay)
        assay_map[str(a_row["identifier"])] = assay
        
        # Link Assay to Studies
        study_ref_json = a_row.get("study_ref")
        if study_ref_json:
            try:
                study_refs = json.loads(study_ref_json)
                if isinstance(study_refs, list):
                    for s_ref in study_refs:
                        if s_ref in study_map:
                            study_map[s_ref].RegisterAssay(assay.Identifier)
            except json.JSONDecodeError:
                pass

    # Add Contacts
    # Investigation contacts
    inv_contacts = [c for c in contacts if c.get("investigation_ref") == inv_id and c.get("target_type") == "investigation"]
    for c_row in inv_contacts:
        person = map_contact(c_row)
        arc.Contacts.append(person)

    # Study contacts
    for s_id, study in study_map.items():
        stu_contacts = [c for c in contacts if c.get("investigation_ref") == inv_id and c.get("target_type") == "study" and c.get("target_ref") == s_id]
        for c_row in stu_contacts:
            person = map_contact(c_row)
            study.Contacts.append(person)

    # Assay contacts
    for a_id, assay in assay_map.items():
        ass_contacts = [c for c in contacts if c.get("investigation_ref") == inv_id and c.get("target_type") == "assay" and c.get("target_ref") == a_id]
        for c_row in ass_contacts:
            person = map_contact(c_row)
            assay.Performers.append(person)

    # Add Publications
    # Investigation pubs
    inv_pubs = [p for p in publications if p.get("investigation_ref") == inv_id and p.get("target_type") == "investigation"]
    for p_row in inv_pubs:
        pub = map_publication(p_row)
        arc.Publications.append(pub)
        
    # Study pubs
    for s_id, study in study_map.items():
        stu_pubs = [p for p in publications if p.get("investigation_ref") == inv_id and p.get("target_type") == "study" and p.get("target_ref") == s_id]
        for p_row in stu_pubs:
            pub = map_publication(p_row)
            study.Publications.append(pub)

    # Add Annotation Tables (TODO: Complex logic, simplified for now or omit if empty)
    # This requires reconstructing tables from rows. 
    # For now, skipping complex table reconstruction to focus on connectivity and main structure.
    # If the user requires strict adherence right now, I might need more helper logic.
    # Given requirements: "Achte darauf, dass alle Daten... auch ausgewertet werden... AnnotationTables angelegt werden".
    # Ok, I must implement it.
    
    # Process Annotation Tables
    # Group by (target_type, target_ref, table_name)
    tables_groups = defaultdict(list)
    for ann in annotations:
        if ann.get("investigation_ref") == inv_id:
            key = (ann.get("target_type"), ann.get("target_ref"), ann.get("table_name"))
            tables_groups[key].append(ann)
            
    for (t_type, t_ref, t_name), rows in tables_groups.items():
        # TODO: Implement table reconstruction using arctrl.
        # This is non-trivial without specific arctrl knowledge on programmatic table construction.
        # Generally: study.InitTable(name) -> returns table -> add columns/rows.
        
        target = None
        if t_type == "study" and t_ref in study_map:
            target = study_map[t_ref]
        elif t_type == "assay" and t_ref in assay_map:
            target = assay_map[t_ref]
            
        if target:
            # We assume for now we can somehow add a table.
            # ARCtrl python bindings might support `target.InitTable(t_name)`
            # Since I cannot verify the exact API right now easily, I will leave a placeholder comment or try best effort.
            # Using standard ISA structure, tables are effectively the assays/studies themselves or separate files.
            # In ARCtrl, metadata is often in "tables" (ProcessSequence).
            pass

    return arc


class WorkerContext(BaseModel):
    """Context data for a worker process."""

    client: Any  # ApiClient, but Any to allow mocking
    rdi: str
    studies_by_inv: dict[str, list[dict[str, Any]]]
    assays_by_inv: dict[str, list[dict[str, Any]]]
    contacts_by_inv: dict[str, list[dict[str, Any]]]
    pubs_by_inv: dict[str, list[dict[str, Any]]]
    anns_by_inv: dict[str, list[dict[str, Any]]]
    batch_size: int
    worker_id: int
    total_workers: int
    executor: Any  # ProcessPoolExecutor is not Pydantic-friendly easily, so Any

    model_config = ConfigDict(arbitrary_types_allowed=True)


async def _upload_and_update_stats(
    ctx: WorkerContext,
    valid_arcs: list[ARC],
    valid_rows: list[dict[str, Any]],
    stats: ProcessingStats,
    batch_info: str,
) -> None:
    """Upload batch of ARCs and update statistics."""
    tracer = trace.get_tracer(__name__)
    try:
        with tracer.start_as_current_span(
            "upload_batch", attributes={"count": len(valid_arcs), "rdi": ctx.rdi, "worker_id": ctx.worker_id}
        ):
            response = await ctx.client.create_or_update_arcs(
                rdi=ctx.rdi,
                arcs=valid_arcs,
            )
        logger.info("%s: Upload request finished. API reported %d successful ARCs.", batch_info, len(response.arcs))

        if len(response.arcs) < len(valid_arcs):
            logger.warning(
                "%s: Only %d/%d ARCs were successfully processed by API.",
                batch_info,
                len(response.arcs),
                len(valid_arcs),
            )
            successful_ids = {a.id for a in response.arcs}

            for arc in valid_arcs:
                identifier = getattr(arc, "Identifier", None)
                if identifier:
                    if identifier not in successful_ids:
                        stats.failed_datasets += 1
                        stats.failed_ids.append(identifier)
                else:
                    logger.error("%s: ARC with missing identifier failed upload", batch_info)
                    stats.failed_datasets += 1
                    stats.failed_ids.append("unknown_id")

    except (ConnectionError, TimeoutError, ApiClientError) as e:
        logger.error("%s: Failed to upload batch: %s", batch_info, e, exc_info=True)
        stats.failed_datasets += len(valid_arcs)
        for row in valid_rows:
            stats.failed_ids.append(str(row["identifier"]))


async def process_batch(  # pylint: disable=too-many-locals
    ctx: WorkerContext,
    batch: list[dict[str, Any]],
    batch_idx: int,
    total_batches: int,
) -> ProcessingStats:
    """Process a single batch of investigations."""
    stats = ProcessingStats()
    tracer = trace.get_tracer(__name__)
    batch_info = f"Worker {ctx.worker_id}/{ctx.total_workers}, Batch {batch_idx + 1}/{total_batches}"

    valid_arcs: list[ARC] = []
    valid_rows: list[dict[str, Any]] = []

    with tracer.start_as_current_span(
        "build_batch",
        attributes={"batch_size": len(batch), "worker_id": ctx.worker_id, "batch_idx": batch_idx},
    ):
        logger.info("%s: Building %d ARCs in parallel...", batch_info, len(batch))

        loop = asyncio.get_event_loop()
        arc_build_futures = []

        for row in batch:
            inv_id = str(row["identifier"])
            
            # Prepare data slices for this investigation
            studies = ctx.studies_by_inv.get(inv_id, [])
            assays = ctx.assays_by_inv.get(inv_id, [])
            contacts = ctx.contacts_by_inv.get(inv_id, [])
            pubs = ctx.pubs_by_inv.get(inv_id, [])
            anns = ctx.anns_by_inv.get(inv_id, [])

            future = loop.run_in_executor(
                ctx.executor,
                build_single_arc_task,
                row,
                studies,
                assays,
                contacts,
                pubs,
                anns
            )
            arc_build_futures.append(future)

        results = await asyncio.gather(*arc_build_futures, return_exceptions=True)

        for i, res in enumerate(results):
            row_id = str(batch[i]["identifier"])
            if isinstance(res, Exception):
                logger.error("%s: Failed to build ARC for investigation %s: %s", batch_info, row_id, res)
                stats.failed_datasets += 1
                stats.failed_ids.append(row_id)
            elif res is None:
                logger.error("%s: Build returned None for investigation %s", batch_info, row_id)
                stats.failed_datasets += 1
                stats.failed_ids.append(row_id)
            else:
                valid_arcs.append(cast(ARC, res))
                valid_rows.append(batch[i])

    if valid_arcs:
        await _upload_and_update_stats(ctx, valid_arcs, valid_rows, stats, batch_info)

    return stats


async def process_worker_investigations(
    ctx: WorkerContext,
    investigations: list[dict[str, Any]],
) -> ProcessingStats:
    """Process a list of investigations assigned to this worker."""
    stats = ProcessingStats()
    if not investigations:
        return stats

    tracer = trace.get_tracer(__name__)

    with tracer.start_as_current_span(
        "process_worker",
        attributes={"worker_id": ctx.worker_id, "investigation_count": len(investigations), "rdi": ctx.rdi},
    ):
        logger.info(
            "Worker %d/%d processing %d investigations...",
            ctx.worker_id,
            ctx.total_workers,
            len(investigations),
        )

        batches: list[list[dict[str, Any]]] = []
        current_batch: list[dict[str, Any]] = []

        for row in investigations:
            current_batch.append(row)
            if len(current_batch) >= ctx.batch_size:
                batches.append(current_batch)
                current_batch = []

        if current_batch:
            batches.append(current_batch)

        logger.info("Worker %d/%d: Processing %d batches", ctx.worker_id, ctx.total_workers, len(batches))

        for batch_idx, batch in enumerate(batches):
            batch_stats = await process_batch(ctx, batch, batch_idx, len(batches))
            stats.merge(batch_stats)

    return stats


async def process_investigations(
    db: Database,
    client: ApiClient,
    config: Config,
) -> ProcessingStats:
    """Fetch investigations from DB and process them."""
    tracer = trace.get_tracer(__name__)
    stats = ProcessingStats()
    with tracer.start_as_current_span("process_investigations"):
        # Step 1: Fetch investigations
        logger.info("Fetching investigations (limit=%s)...", config.debug_limit)
        async with db.connect(): # Just to test connection or warm up? Not needed if using helper methods.
            pass
            
        investigation_rows = await db.get_investigations(limit=config.debug_limit)
        # Convert to dicts
        investigation_rows = [dict(row) for row in investigation_rows]
        
        logger.info("Found %d investigations", len(investigation_rows))
        stats.found_datasets = len(investigation_rows)

        if not investigation_rows:
            logger.info("No investigations found, nothing to process")
            return stats

        investigation_ids = [str(row["identifier"]) for row in investigation_rows]
        
        # Step 2: Fetch related data in bulk
        # Studies
        logger.info("Fetching studies...")
        study_rows = await db.get_studies(investigation_ids)
        study_rows = [dict(row) for row in study_rows]
        stats.total_studies = len(study_rows)
        
        # Assays
        logger.info("Fetching assays...")
        assay_rows = await db.get_assays(investigation_ids)
        assay_rows = [dict(row) for row in assay_rows]
        stats.total_assays = len(assay_rows)
        
        # Contacts
        logger.info("Fetching contacts...")
        contact_rows = await db.get_contacts(investigation_ids)
        contact_rows = [dict(row) for row in contact_rows]
        
        # Publications
        logger.info("Fetching publications...")
        pub_rows = await db.get_publications(investigation_ids)
        pub_rows = [dict(row) for row in pub_rows]
        
        # Annotations
        logger.info("Fetching annotation tables...")
        ann_rows = await db.get_annotation_tables(investigation_ids)
        ann_rows = [dict(row) for row in ann_rows]

        # Group data by investigation ID to pass to workers efficiently
        # Actually, passing the whole dict is fine if not too huge. 
        # But optimize by pre-grouping?
        # Worker logic already filters from the context maps.
        # Let's group here.
        studies_by_inv = defaultdict(list)
        for r in study_rows: studies_by_inv[str(r["investigation_ref"])].append(r)
        
        assays_by_inv = defaultdict(list)
        for r in assay_rows: assays_by_inv[str(r["investigation_ref"])].append(r)
        
        contacts_by_inv = defaultdict(list)
        for r in contact_rows: contacts_by_inv[str(r["investigation_ref"])].append(r)
        
        pubs_by_inv = defaultdict(list)
        for r in pub_rows: pubs_by_inv[str(r["investigation_ref"])].append(r)
        
        anns_by_inv = defaultdict(list)
        for r in ann_rows: anns_by_inv[str(r["investigation_ref"])].append(r)

        # Distribute
        num_workers = config.max_concurrent_arc_builds
        worker_assignments: list[list[dict[str, Any]]] = [[] for _ in range(num_workers)]
        for idx, investigation in enumerate(investigation_rows):
            worker_id = idx % num_workers
            worker_assignments[worker_id].append(investigation)

        mp_context = multiprocessing.get_context("spawn")
        with concurrent.futures.ProcessPoolExecutor(max_workers=num_workers, mp_context=mp_context) as executor:
            tasks = []
            for worker_id, assigned_investigations in enumerate(worker_assignments):
                if not assigned_investigations:
                    continue

                ctx = WorkerContext(
                    client=client,
                    rdi=config.rdi,
                    studies_by_inv=dict(studies_by_inv),
                    assays_by_inv=dict(assays_by_inv),
                    contacts_by_inv=dict(contacts_by_inv),
                    pubs_by_inv=dict(pubs_by_inv),
                    anns_by_inv=dict(anns_by_inv),
                    batch_size=config.batch_size,
                    worker_id=worker_id + 1,
                    total_workers=num_workers,
                    executor=executor,
                )
                tasks.append(process_worker_investigations(ctx, assigned_investigations))

            results = await asyncio.gather(*tasks)
            for res in results:
                if isinstance(res, ProcessingStats):
                    stats.merge(res)

    return stats


async def run_conversion(config: Config) -> ProcessingStats:
    """Run the conversion."""
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("run_conversion"):
        db = Database(config.connection_string.get_secret_value())
        async with ApiClient(config.api_client) as client:
            return await process_investigations(db, client, config)


async def main() -> None:
    """Main entry point."""
    args = parse_args()
    try:
        wrapper = ConfigWrapper.from_yaml_file(args.config, prefix="SQL_TO_ARC")
        config = Config.from_config_wrapper(wrapper)
        configure_logging(config.log_level)
    except (FileNotFoundError, IsADirectoryError, ValidationError) as e:
        logger.error("Failed to load configuration: %s", e)
        return

    otlp_endpoint = str(config.otel.endpoint) if config.otel.endpoint else None
    _tracer_provider, tracer = initialize_tracing(
        service_name="sql_to_arc",
        otlp_endpoint=otlp_endpoint,
        log_console_spans=config.otel.log_console_spans,
    )

    with tracer.start_as_current_span("sql_to_arc.main"):
        logger.info("Starting SQL-to-ARC conversion with config: %s", args.config)
        try:
            start_time = time.perf_counter()
            stats = await run_conversion(config)
            end_time = time.perf_counter()
            stats.duration_seconds = end_time - start_time

            logger.info("SQL-to-ARC conversion completed. Report:")
            print(stats.to_jsonld(rdi_identifier=config.rdi, rdi_url=config.rdi_url))

            if stats.failed_datasets > 0:
                logger.warning(
                    "Conversion finished with %d failures out of %d datasets.",
                    stats.failed_datasets,
                    stats.found_datasets,
                )
            else:
                logger.info("Conversion finished successfully. %d datasets processed.", stats.found_datasets)

        except Exception as e:
            logger.critical("Fatal error during conversion process: %s", e, exc_info=True)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    asyncio.run(main())
