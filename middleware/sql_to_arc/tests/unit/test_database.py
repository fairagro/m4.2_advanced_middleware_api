"""Unit tests for the Database class in middleware.sql_to_arc.database.

These tests cover async methods for retrieving investigations, studies, assays,
contacts, publications, and annotation tables using mocked database connections.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from middleware.sql_to_arc.database import Database


@pytest.mark.asyncio
async def test_get_investigations() -> None:
    """Test the get_investigations method of the Database class."""
    with patch("middleware.sql_to_arc.database.create_async_engine") as mock_engine:
        mock_conn = AsyncMock()
        mock_engine.return_value.connect.return_value.__aenter__.return_value = mock_conn

        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = [{"identifier": "1"}]
        mock_conn.execute.return_value = mock_result

        db = Database("sqlite+aiosqlite:///")
        res = await db.get_investigations(limit=5)

        assert len(res) == 1
        assert res[0]["identifier"] == "1"
        mock_conn.execute.assert_called()


@pytest.mark.asyncio
async def test_get_studies() -> None:
    """Test the get_studies method of the Database class."""
    with patch("middleware.sql_to_arc.database.create_async_engine") as mock_engine:
        mock_conn = AsyncMock()
        mock_engine.return_value.connect.return_value.__aenter__.return_value = mock_conn

        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = [{"identifier": "10"}]
        mock_conn.execute.return_value = mock_result

        db = Database("connection_string")
        res = await db.get_studies(["1", "2"])

        assert len(res) == 1
        assert res[0]["identifier"] == "10"
        mock_conn.execute.assert_called()


@pytest.mark.asyncio
async def test_get_assays() -> None:
    """Test the get_assays method of the Database class."""
    with patch("middleware.sql_to_arc.database.create_async_engine") as mock_engine:
        mock_conn = AsyncMock()
        mock_engine.return_value.connect.return_value.__aenter__.return_value = mock_conn

        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = []
        mock_conn.execute.return_value = mock_result

        db = Database("connection_string")
        await db.get_assays(["1"])
        mock_conn.execute.assert_called()


@pytest.mark.asyncio
async def test_get_contacts() -> None:
    """Test the get_contacts method of the Database class."""
    with patch("middleware.sql_to_arc.database.create_async_engine") as mock_engine:
        mock_conn = AsyncMock()
        mock_engine.return_value.connect.return_value.__aenter__.return_value = mock_conn

        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = []
        mock_conn.execute.return_value = mock_result

        db = Database("connection_string")
        await db.get_contacts(["1"])
        mock_conn.execute.assert_called()


@pytest.mark.asyncio
async def test_get_publications() -> None:
    """Test the get_publications method of the Database class."""
    with patch("middleware.sql_to_arc.database.create_async_engine") as mock_engine:
        mock_conn = AsyncMock()
        mock_engine.return_value.connect.return_value.__aenter__.return_value = mock_conn

        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = []
        mock_conn.execute.return_value = mock_result

        db = Database("connection_string")
        await db.get_publications(["1"])
        mock_conn.execute.assert_called()


@pytest.mark.asyncio
async def test_get_annotation_tables() -> None:
    """Test the get_annotation_tables method of the Database class."""
    with patch("middleware.sql_to_arc.database.create_async_engine") as mock_engine:
        mock_conn = AsyncMock()
        mock_engine.return_value.connect.return_value.__aenter__.return_value = mock_conn

        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = []
        mock_conn.execute.return_value = mock_result

        db = Database("connection_string")
        await db.get_annotation_tables(["1"])
        mock_conn.execute.assert_called()
