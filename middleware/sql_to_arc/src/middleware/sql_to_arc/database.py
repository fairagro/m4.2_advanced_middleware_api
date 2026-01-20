"""Database module for SQL-to-ARC."""

from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import (
    Column,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    TIMESTAMP,
)
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine
from sqlalchemy.sql import select

# Define metadata
metadata = MetaData()

# Define Tables (Views)
# Note: We use the Table construct to reflect the view structure.
# SQLAlchemy will treat them as tables for querying purposes.

# vInvestigation
vInvestigation = Table(
    "vInvestigation",
    metadata,
    Column("identifier", Text, primary_key=True),
    Column("title", Text),
    Column("description_text", Text),
    Column("submission_date", TIMESTAMP),
    Column("public_release_date", TIMESTAMP),
)

# vStudy
vStudy = Table(
    "vStudy",
    metadata,
    Column("identifier", Text, primary_key=True),
    Column("title", Text),
    Column("description_text", Text),
    Column("submission_date", TIMESTAMP),
    Column("public_release_date", TIMESTAMP),
    Column("investigation_ref", Text),  # FK to Investigation
)

# vAssay
vAssay = Table(
    "vAssay",
    metadata,
    Column("identifier", Text, primary_key=True),
    Column("title", Text),
    Column("description_text", Text),
    Column("measurement_type_term", Text),
    Column("measurement_type_uri", Text),
    Column("measurement_type_version", Text),
    Column("technology_type_term", Text),
    Column("technology_type_uri", Text),
    Column("technology_type_version", Text),
    Column("technology_platform", Text),
    Column("investigation_ref", Text),  # FK to Investigation
    Column("study_ref", Text),  # JSON string
)

# vPublication
vPublication = Table(
    "vPublication",
    metadata,
    Column("pubmed_id", Text),
    Column("doi", Text),
    Column("authors", Text),
    Column("title", Text),
    Column("status_term", Text),
    Column("status_uri", Text),
    Column("status_version", Text),
    Column("target_type", Text),  # investigation, study
    Column("target_ref", Text),
    Column("investigation_ref", Text),
)

# vContact
vContact = Table(
    "vContact",
    metadata,
    Column("last_name", Text),
    Column("first_name", Text),
    Column("mid_initials", Text),
    Column("email", Text),
    Column("phone", Text),
    Column("fax", Text),
    Column("postal_address", Text),
    Column("affiliation", Text),
    Column("roles", Text),  # JSON string
    Column("target_type", Text),  # investigation, study, assay
    Column("target_ref", Text),
    Column("investigation_ref", Text),
)

# vAnnotationTable
vAnnotationTable = Table(
    "vAnnotationTable",
    metadata,
    Column("table_name", Text),
    Column("target_type", Text),  # study, assay
    Column("target_ref", Text),
    Column("investigation_ref", Text),
    Column("column_type", Text),
    Column("column_io_type", Text),
    Column("column_value", Text),
    Column("column_annotation_term", Text),
    Column("column_annotation_uri", Text),
    Column("column_annotation_version", Text),
    Column("row_index", Integer),
    Column("cell_value", Text),
    Column("cell_annotation_term", Text),
    Column("cell_annotation_uri", Text),
    Column("cell_annotation_version", Text),
)


class Database:
    """Database handler using SQLAlchemy."""

    def __init__(self, connection_string: str) -> None:
        """Initialize database with connection string."""
        self.engine: AsyncEngine = create_async_engine(connection_string, echo=False)

    async def get_investigations(
        self, limit: int | None = None
    ) -> Sequence[Any]:
        """Fetch investigations."""
        async with self.engine.connect() as conn:
            stmt = select(vInvestigation)
            if limit:
                stmt = stmt.limit(limit)
            result = await conn.execute(stmt)
            return result.mappings().all()

    async def get_studies(self, investigation_ids: list[str]) -> Sequence[Any]:
        """Fetch studies for given investigations."""
        if not investigation_ids:
            return []
        async with self.engine.connect() as conn:
            stmt = select(vStudy).where(vStudy.c.investigation_ref.in_(investigation_ids))
            result = await conn.execute(stmt)
            return result.mappings().all()

    async def get_assays(self, investigation_ids: list[str]) -> Sequence[Any]:
        """Fetch assays for given investigations."""
        if not investigation_ids:
            return []
        async with self.engine.connect() as conn:
            stmt = select(vAssay).where(vAssay.c.investigation_ref.in_(investigation_ids))
            result = await conn.execute(stmt)
            return result.mappings().all()

    async def get_contacts(self, investigation_ids: list[str]) -> Sequence[Any]:
        """Fetch contacts for given investigations."""
        if not investigation_ids:
            return []
        async with self.engine.connect() as conn:
            stmt = select(vContact).where(vContact.c.investigation_ref.in_(investigation_ids))
            result = await conn.execute(stmt)
            return result.mappings().all()

    async def get_publications(self, investigation_ids: list[str]) -> Sequence[Any]:
        """Fetch publications for given investigations."""
        if not investigation_ids:
            return []
        async with self.engine.connect() as conn:
            stmt = select(vPublication).where(vPublication.c.investigation_ref.in_(investigation_ids))
            result = await conn.execute(stmt)
            return result.mappings().all()

    async def get_annotation_tables(self, investigation_ids: list[str]) -> Sequence[Any]:
        """Fetch annotation tables for given investigations."""
        if not investigation_ids:
            return []
        async with self.engine.connect() as conn:
            stmt = select(vAnnotationTable).where(vAnnotationTable.c.investigation_ref.in_(investigation_ids))
            result = await conn.execute(stmt)
            return result.mappings().all()

    @asynccontextmanager
    async def connect(self) -> AsyncGenerator[AsyncConnection, None]:
        """Context manager for database connection."""
        async with self.engine.connect() as conn:
            yield conn
