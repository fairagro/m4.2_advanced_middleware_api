
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from middleware.sql_to_arc.database import Database

@pytest.mark.asyncio
async def test_get_investigations() -> None:
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
    with patch("middleware.sql_to_arc.database.create_async_engine") as mock_engine:
        mock_conn = AsyncMock()
        mock_engine.return_value.connect.return_value.__aenter__.return_value = mock_conn
        
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = []
        mock_conn.execute.return_value = mock_result
        
        db = Database("connection_string")
        await db.get_annotation_tables(["1"])
        mock_conn.execute.assert_called()
