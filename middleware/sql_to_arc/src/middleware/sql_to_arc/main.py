"""A first prototype of the SQL-to-ARC middleware component."""

import asyncio

import psycopg
from arctrl import ArcInvestigation  # type: ignore[import-untyped]
from psycopg.rows import dict_row

from .config import Config

config = Config.from_data(
    {
        "db_name": "edaphobase",
        "db_user": "postgres",
        "db_password": "postgres",
        "db_host": "localhost",
    }
)


async def main() -> None:
    """Connect to the PostgreSQL database, execute a query, and print the result."""
    async with (
        await psycopg.AsyncConnection.connect(
            dbname=config.db_name,
            user=config.db_user,
            password=config.db_password.get_secret_value(),
            host=config.db_host,
            port=config.db_port,
        ) as conn,
        conn.cursor(row_factory=dict_row) as cur,
    ):
        await cur.execute(
            'SELECT id, investigation_id, title, description, submission_time, release_time FROM "ARC_Study"',
        )
        async for row in cur:
            _arc = ArcInvestigation.create(
                identifier=row["investigation_id"],
                title=row["title"],
                description=row["description"],
                submission_date=row["submission_time"],
                public_release_date=row["release_time"],
            )


if __name__ == "__main__":
    asyncio.run(main())
