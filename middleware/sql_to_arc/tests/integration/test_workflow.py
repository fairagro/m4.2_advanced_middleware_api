"""Integration tests for the SQL-to-ARC workflow."""

import multiprocessing
from collections.abc import AsyncGenerator
from concurrent.futures import ProcessPoolExecutor
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from arctrl import ARC  # type: ignore[import-untyped]
from middleware.api_client import ApiClient
from middleware.shared.api_models.models import CreateOrUpdateArcsResponse
from middleware.shared.config.config_base import OtelConfig
from middleware.sql_to_arc.main import WorkerContext, main, process_worker_investigations


@pytest.fixture
def mock_db_cursor() -> AsyncMock:
    """Mock database cursor."""
    cursor = AsyncMock()
    # Setup default behavior for fetchall/aiter
    cursor.fetchall.return_value = []
    cursor.__aiter__.return_value = []
    return cursor


@pytest.fixture
def mock_db_connection(mock_db_cursor: AsyncMock) -> AsyncMock:
    """Mock database connection."""
    conn = AsyncMock()
    # conn.cursor is synchronous, returns an async context manager
    conn.cursor = MagicMock()
    conn.cursor.return_value.__aenter__ = AsyncMock(return_value=mock_db_cursor)
    conn.cursor.return_value.__aexit__ = AsyncMock(return_value=None)
    return conn


@pytest.fixture
def mock_api_client() -> AsyncMock:
    """Mock API client."""
    client = AsyncMock(spec=ApiClient)
    client.create_or_update_arcs.return_value = CreateOrUpdateArcsResponse(
        client_id="test",
        message="success",
        rdi="test",
        arcs=[],
    )
    return client


class WorkflowTester:
    """Helper class to simplify integration tests for sql_to_arc."""

    def __init__(self, mocker: MagicMock, mock_api_client: AsyncMock) -> None:
        self.mocker = mocker
        self.api_client = mock_api_client
        self.db = MagicMock()
        self.db.to_jsonld.return_value = "{}"
        self.captured_arcs: list[ARC] = []

        # Default empty mocks
        self.set_db_content()

        # Patch Database class
        mocker.patch("middleware.sql_to_arc.main.Database", return_value=self.db)

        # Patch API Client context manager
        mocker.patch(
            "middleware.sql_to_arc.main.ApiClient",
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=self.api_client)),
        )

        # Patch configuration
        self.mock_config = MagicMock()
        self.mock_config.rdi = "test-rdi"
        self.mock_config.max_concurrent_arc_builds = 1
        self.mock_config.log_level = "INFO"
        self.mock_config.otel = OtelConfig(endpoint=None, log_console_spans=False, log_level="INFO")
        mock_conn = MagicMock()
        mock_conn.get_secret_value.return_value = "sqlite+aiosqlite:///:memory:"
        self.mock_config.connection_string = mock_conn

        mocker.patch("middleware.sql_to_arc.main.ConfigWrapper.from_yaml_file")
        mocker.patch("middleware.sql_to_arc.main.Config.from_config_wrapper", return_value=self.mock_config)
        mocker.patch("middleware.sql_to_arc.main.configure_logging")

        # Capture ARCs on API call
        async def capture_arcs(rdi: str, arcs: list[ARC]) -> CreateOrUpdateArcsResponse:
            self.captured_arcs.extend(arcs)
            return CreateOrUpdateArcsResponse(client_id="test", message="success", rdi=rdi, arcs=[])

        self.api_client.create_or_update_arcs.side_effect = capture_arcs

    def _as_gen(self, data: list[dict[str, Any]]) -> AsyncGenerator[dict[str, Any], None]:
        async def gen() -> AsyncGenerator[dict[str, Any], None]:
            for item in data:
                yield item

        return gen()

    def set_db_content(
        self,
        investigations: list[dict[str, Any]] | None = None,
        studies: list[dict[str, Any]] | None = None,
        assays: list[dict[str, Any]] | None = None,
        contacts: list[dict[str, Any]] | None = None,
        publications: list[dict[str, Any]] | None = None,
        annotations: list[dict[str, Any]] | None = None,
    ) -> None:
        """Mock the database streaming methods with provided data."""
        self.db.stream_investigations.side_effect = lambda limit=None: self._as_gen(investigations or [])
        self.db.stream_studies.side_effect = lambda investigation_ids: self._as_gen(studies or [])
        self.db.stream_assays.side_effect = lambda investigation_ids: self._as_gen(assays or [])
        self.db.stream_contacts.side_effect = lambda investigation_ids: self._as_gen(contacts or [])
        self.db.stream_publications.side_effect = lambda investigation_ids: self._as_gen(publications or [])
        self.db.stream_annotation_tables.side_effect = lambda investigation_ids: self._as_gen(annotations or [])

    async def run(self) -> list[ARC]:
        """Execute the main workflow and return captured ARC objects."""
        # Prevent real engine creation
        self.mocker.patch("sqlalchemy.ext.asyncio.create_async_engine", return_value=MagicMock())
        self.mocker.patch(
            "sqlalchemy.ext.asyncio.AsyncSession",
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=AsyncMock())),
        )

        await main()
        return self.captured_arcs


@pytest.fixture
def workflow_tester(mocker: MagicMock, mock_api_client: AsyncMock) -> WorkflowTester:
    """Fixture providing a WorkflowTester instance."""
    return WorkflowTester(mocker, mock_api_client)


@pytest.mark.asyncio
async def test_process_worker_investigations(mock_api_client: AsyncMock) -> None:
    """Test worker investigations processing."""
    investigation_rows: list[dict[str, Any]] = [
        {"identifier": 1, "title": "Test 1", "description": "Desc 1", "submission_time": None, "release_time": None},
        {"identifier": 2, "title": "Test 2", "description": "Desc 2", "submission_time": None, "release_time": None},
    ]
    studies_by_investigation: dict[str, list[dict[str, Any]]] = {"1": [], "2": []}
    assays_by_study: dict[str, list[dict[str, Any]]] = {}

    mp_context = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(max_workers=5, mp_context=mp_context) as executor:
        ctx = WorkerContext(
            client=mock_api_client,
            rdi="edaphobase",
            studies_by_inv=studies_by_investigation,
            assays_by_inv=assays_by_study,
            contacts_by_inv={},
            pubs_by_inv={},
            anns_by_inv={},
            worker_id=1,
            total_workers=1,
            executor=executor,
        )
        await process_worker_investigations(ctx, investigation_rows)

    assert mock_api_client.create_or_update_arcs.called
    # There should be two calls, each with one ARC (since batch size is always 1)
    assert mock_api_client.create_or_update_arcs.call_count == 2  # noqa: PLR2004
    for call in mock_api_client.create_or_update_arcs.call_args_list:
        assert call.kwargs["rdi"] == "edaphobase"
        assert len(call.kwargs["arcs"]) == 1


@pytest.mark.asyncio
async def test_main_workflow(workflow_tester: WorkflowTester) -> None:
    """Test the main workflow with mocked DB and API using WorkflowTester."""
    # Setup DB data
    investigations = [
        {"identifier": "1", "title": "Inv 1", "description_text": "Desc 1"},
        {"identifier": "2", "title": "Inv 2", "description_text": "Desc 2"},
    ]
    studies = [
        {"identifier": "10", "investigation_ref": "1", "title": "Study 1", "description_text": "Desc S1"},
        {"identifier": "11", "investigation_ref": "2", "title": "Study 2", "description_text": "Desc S2"},
    ]
    assays = [
        {"identifier": "100", "study_ref": '["10"]', "investigation_ref": "1"},
        {"identifier": "101", "study_ref": '["11"]', "investigation_ref": "2"},
    ]

    workflow_tester.set_db_content(investigations=investigations, studies=studies, assays=assays)

    # Run main
    arcs = await workflow_tester.run()

    # Verify results
    assert len(arcs) == 2  # noqa: PLR2004
    identifiers = {arc.Identifier for arc in arcs}
    assert identifiers == {"1", "2"}

    # Spot check deep property
    arc1 = next(a for a in arcs if a.Identifier == "1")
    assert arc1.Studies[0].Identifier == "10"
    # In this version of arctrl, studies have RegisteredAssays
    assert arc1.Studies[0].RegisteredAssays[0].Identifier == "100"


@pytest.mark.asyncio
async def test_concise_arc_verification(workflow_tester: WorkflowTester) -> None:
    """Demonstrate a very concise integration test using the new tools."""
    workflow_tester.set_db_content(
        investigations=[{"identifier": "INV_ABC", "title": "Simplified Test"}],
        studies=[{"identifier": "ST_1", "investigation_ref": "INV_ABC", "title": "Study A"}],
    )

    arcs = await workflow_tester.run()

    assert len(arcs) == 1
    assert arcs[0].Identifier == "INV_ABC"
    assert arcs[0].Studies[0].Title == "Study A"
