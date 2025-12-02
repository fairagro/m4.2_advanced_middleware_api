"""SQL-to-ARC middleware component."""

import asyncio
import logging
from typing import Any

import psycopg
from arctrl import ARC, ArcInvestigation  # type: ignore[import-untyped]
from psycopg.rows import dict_row

from middleware.api_client import ApiClient
from middleware.sql_to_arc.config import Config
from middleware.sql_to_arc.mapper import map_assay, map_investigation, map_study

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load configuration
# In a real app, this might come from env vars or a file
config = Config.from_data(
    {
        "db_name": "edaphobase",
        "db_user": "postgres",
        "db_password": "postgres",
        "db_host": "localhost",
        "rdi": "edaphobase",
        "api_client": {
            "api_url": "http://localhost:8000",
            "client_cert_path": "/path/to/cert.pem",
            "client_key_path": "/path/to/key.pem",
            "verify_ssl": "false",
        },
    }
)


async def fetch_assays(cur: psycopg.AsyncCursor[dict[str, Any]], study_id: int) -> list[dict[str, Any]]:
    """Fetch assays for a given study."""
    await cur.execute(
        'SELECT id, study_id, measurement_type, technology_type FROM "ARC_Assay" WHERE study_id = %s',
        (study_id,),
    )
    return await cur.fetchall()


async def fetch_studies(cur: psycopg.AsyncCursor[dict[str, Any]], investigation_id: int) -> list[dict[str, Any]]:
    """Fetch studies for a given investigation."""
    await cur.execute(
        "SELECT id, investigation_id, title, description, submission_time, release_time "
        'FROM "ARC_Study" WHERE investigation_id = %s',
        (investigation_id,),
    )
    return await cur.fetchall()


async def process_batch(client: ApiClient, batch: list[ArcInvestigation]) -> None:
    """Send a batch of ARCs to the API."""
    if not batch:
        return

    logger.info("Uploading batch of %d ARCs...", len(batch))

    # Wrap ArcInvestigation objects in ARC containers
    arc_objects = [ARC.from_arc_investigation(inv) for inv in batch]

    try:
        response = await client.create_or_update_arcs(
            rdi=config.rdi,
            arcs=arc_objects,
        )
        logger.info("Batch upload successful. Created/Updated: %d", len(response.arcs))
    except (psycopg.Error, ConnectionError, TimeoutError) as e:
        logger.error("Failed to upload batch: %s", e)


async def main() -> None:
    """Connect to DB, process investigations, and upload ARCs."""
    logger.info("Starting SQL-to-ARC conversion...")

    async with (
        ApiClient(config.api_client) as client,
        await psycopg.AsyncConnection.connect(
            dbname=config.db_name,
            user=config.db_user,
            password=config.db_password.get_secret_value(),
            host=config.db_host,
            port=config.db_port,
        ) as conn,
        conn.cursor(row_factory=dict_row) as cur,
    ):
        # 1. Fetch all investigations
        await cur.execute(
            'SELECT id, title, description, submission_time, release_time FROM "ARC_Investigation"',
        )

        batch: list[ArcInvestigation] = []

        async for row in cur:
            # Map Investigation
            arc = map_investigation(row)
            current_inv_id = row["id"]

            # 2. Fetch Studies
            studies_rows = await fetch_studies(cur, current_inv_id)
            for study_row in studies_rows:
                study = map_study(study_row)
                arc.AddRegisteredStudy(study)

                # 3. Fetch Assays
                assays_rows = await fetch_assays(cur, study_row["id"])
                for assay_row in assays_rows:
                    assay = map_assay(assay_row)
                    study.AddRegisteredAssay(assay)

            # Add to batch
            batch.append(arc)

            # Process batch if full
            if len(batch) >= config.batch_size:
                await process_batch(client, batch)
                batch = []

        # Process remaining
        if batch:
            await process_batch(client, batch)

    logger.info("SQL-to-ARC conversion completed.")


if __name__ == "__main__":
    asyncio.run(main())
