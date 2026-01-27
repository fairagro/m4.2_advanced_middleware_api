"""Integration tests for the SQL-to-ARC workflow."""

import json
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
        """
        Initialize the WorkflowTester with mock dependencies.

        Args:
            mocker (MagicMock): Mocking utility for patching dependencies.
            mock_api_client (AsyncMock): Mocked API client for simulating API interactions.
        """
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

    def set_db_content(  # noqa: PLR0913
        self,
        investigations: list[dict[str, Any]] | None = None,
        studies: list[dict[str, Any]] | None = None,
        assays: list[dict[str, Any]] | None = None,
        contacts: list[dict[str, Any]] | None = None,
        publications: list[dict[str, Any]] | None = None,
        annotations: list[dict[str, Any]] | None = None,
    ) -> None:
        """Mock the database streaming methods with provided data."""
        self.db.stream_investigations.side_effect = lambda limit=None: self._as_gen(investigations or [])  # noqa: ARG005
        self.db.stream_studies.side_effect = lambda investigation_ids: self._as_gen(studies or [])  # noqa: ARG005
        self.db.stream_assays.side_effect = lambda investigation_ids: self._as_gen(assays or [])  # noqa: ARG005
        self.db.stream_contacts.side_effect = lambda investigation_ids: self._as_gen(contacts or [])  # noqa: ARG005
        self.db.stream_publications.side_effect = lambda investigation_ids: self._as_gen(publications or [])  # noqa: ARG005
        self.db.stream_annotation_tables.side_effect = lambda investigation_ids: self._as_gen(annotations or [])  # noqa: ARG005

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
async def test_investigation_with_publications_and_contacts(workflow_tester: WorkflowTester) -> None:
    """Test investigation with multiple publications and contacts at the investigation level."""
    inv_id = "INV_PUBLICATION_TEST"
    investigations = [{"identifier": inv_id, "title": "Publication and Contact Test"}]

    publications = [
        {
            "investigation_ref": inv_id,
            "target_type": "investigation",
            "title": "First Paper",
            "doi": "10.1234/1",
            "pubmed_id": "123456",
            "authors": "Author A, Author B",
            "status_term": "published",
        },
        {
            "investigation_ref": inv_id,
            "target_type": "investigation",
            "title": "Second Paper",
            "doi": "10.1234/2",
            "pubmed_id": "654321",
            "authors": "Author C",
            "status_term": "in review",
        },
    ]

    contacts = [
        {
            "investigation_ref": inv_id,
            "target_type": "investigation",
            "last_name": "Doe",
            "first_name": "John",
            "email": "john.doe@example.com",
            "affiliation": "Institute A",
            "roles": json.dumps([{"term": "Principal Investigator"}]),
        },
        {
            "investigation_ref": inv_id,
            "target_type": "investigation",
            "last_name": "Smith",
            "first_name": "Jane",
            "email": "jane.smith@example.com",
            "affiliation": "Institute B",
            "roles": json.dumps([{"term": "Data Curator"}]),
        },
    ]

    workflow_tester.set_db_content(
        investigations=investigations,
        publications=publications,
        contacts=contacts,
    )

    arcs = await workflow_tester.run()

    assert len(arcs) == 1
    arc = arcs[0]
    assert arc.Identifier == inv_id

    # Verify Publications
    assert len(arc.Publications) == 2  # noqa: PLR2004
    titles = {p.Title for p in arc.Publications}
    assert titles == {"First Paper", "Second Paper"}
    assert any(p.DOI == "10.1234/1" for p in arc.Publications)

    # Verify Contacts
    assert len(arc.Contacts) == 2  # noqa: PLR2004
    emails = {c.EMail for c in arc.Contacts}
    assert emails == {"john.doe@example.com", "jane.smith@example.com"}
    assert any(c.LastName == "Doe" for c in arc.Contacts)
    assert any(oa.Name == "Data Curator" for c in arc.Contacts for oa in c.Roles)
    
@pytest.mark.asyncio
async def test_study_with_publications_and_contacts(workflow_tester: WorkflowTester) -> None:
    """Test study with multiple publications and contacts at the study level."""
    inv_id = "INV_S"
    study_id = "STUDY_1"

    investigations = [{"identifier": inv_id, "title": "Study Level Metadata Test"}]
    studies = [{"identifier": study_id, "investigation_ref": inv_id, "title": "Target Study"}]

    publications = [
        {
            "investigation_ref": inv_id,
            "target_type": "study",
            "target_ref": study_id,
            "title": "Study Specific Paper 1",
            "doi": "10.1234/study.1",
        },
        {
            "investigation_ref": inv_id,
            "target_type": "study",
            "target_ref": study_id,
            "title": "Study Specific Paper 2",
            "doi": "10.1234/study.2",
        },
    ]

    contacts = [
        {
            "investigation_ref": inv_id,
            "target_type": "study",
            "target_ref": study_id,
            "last_name": "Scientist",
            "first_name": "Alice",
            "email": "alice@example.com",
            "roles": json.dumps([{"term": "Collaborator"}]),
        },
        {
            "investigation_ref": inv_id,
            "target_type": "study",
            "target_ref": study_id,
            "last_name": "Researcher",
            "first_name": "Bob",
            "email": "bob@example.com",
            "roles": json.dumps([{"term": "Lead Scientist"}]),
        },
    ]

    workflow_tester.set_db_content(
        investigations=investigations,
        studies=studies,
        publications=publications,
        contacts=contacts,
    )

    arcs = await workflow_tester.run()

    assert len(arcs) == 1
    arc = arcs[0]
    assert len(arc.Studies) == 1
    study = arc.Studies[0]
    assert study.Identifier == study_id

    # Verify Study Publications
    assert len(study.Publications) == 2  # noqa: PLR2004
    titles = {p.Title for p in study.Publications}
    assert titles == {"Study Specific Paper 1", "Study Specific Paper 2"}

    # Verify Study Contacts
    assert len(study.Contacts) == 2  # noqa: PLR2004
    emails = {c.EMail for c in study.Contacts}
    assert emails == {"alice@example.com", "bob@example.com"}


@pytest.mark.asyncio
async def test_assay_with_contacts(workflow_tester: WorkflowTester) -> None:
    """Test assay with multiple contacts (performers) at the assay level."""
    inv_id = "INV_A"
    assay_id = "ASSAY_1"

    investigations = [{"identifier": inv_id, "title": "Assay Metadata Test"}]
    # Assays need to be linked to studies in the DB row via study_ref if we want them registered in studies,
    # but the mapper/main logic also adds them to the ARC level.
    assays = [{"identifier": assay_id, "investigation_ref": inv_id}]

    contacts = [
        {
            "investigation_ref": inv_id,
            "target_type": "assay",
            "target_ref": assay_id,
            "last_name": "Technician",
            "first_name": "Tom",
            "email": "tom@example.com",
            "roles": json.dumps([{"term": "Operator"}]),
        },
        {
            "investigation_ref": inv_id,
            "target_type": "assay",
            "target_ref": assay_id,
            "last_name": "Analyst",
            "first_name": "Anna",
            "email": "anna@example.com",
            "roles": json.dumps([{"term": "Data Analyst"}]),
        },
    ]

    workflow_tester.set_db_content(
        investigations=investigations,
        assays=assays,
        contacts=contacts,
    )

    arcs = await workflow_tester.run()

    assert len(arcs) == 1
    arc = arcs[0]
    assert len(arc.Assays) == 1
    assay = arc.Assays[0]
    assert assay.Identifier == assay_id

    # Verify Assay Performers (contacts mapped to performers in assays)
    assert len(assay.Performers) == 2  # noqa: PLR2004
    emails = {p.EMail for p in assay.Performers}
    assert emails == {"tom@example.com", "anna@example.com"}
    assert any(p.LastName == "Technician" for p in assay.Performers)


@pytest.mark.asyncio
async def test_complex_hierarchy(workflow_tester: WorkflowTester) -> None:
    """Test investigation with multiple studies and assays linked to them."""
    inv_id = "INV_COMPLEX"
    s1_id = "S1"
    s2_id = "S2"
    a1_id = "A1"
    a2_id = "A2"
    a3_id = "A3"

    investigations = [{"identifier": inv_id, "title": "Complex Hierarchy Test"}]
    studies = [
        {"identifier": s1_id, "investigation_ref": inv_id, "title": "Study 1"},
        {"identifier": s2_id, "investigation_ref": inv_id, "title": "Study 2"},
    ]
    # Assays link to studies via 'study_ref' which is a JSON list of identifiers
    assays = [
        {"identifier": a1_id, "investigation_ref": inv_id, "study_ref": json.dumps([s1_id])},
        {"identifier": a2_id, "investigation_ref": inv_id, "study_ref": json.dumps([s1_id])},
        {"identifier": a3_id, "investigation_ref": inv_id, "study_ref": json.dumps([s2_id])},
    ]

    workflow_tester.set_db_content(
        investigations=investigations,
        studies=studies,
        assays=assays,
    )

    arcs = await workflow_tester.run()

    assert len(arcs) == 1
    arc = arcs[0]
    assert arc.Identifier == inv_id

    # Verify studies
    assert len(arc.Studies) == 2  # noqa: PLR2004
    s1 = next(s for s in arc.Studies if s.Identifier == s1_id)
    s2 = next(s for s in arc.Studies if s.Identifier == s2_id)

    # Verify assays in studies
    assert len(s1.RegisteredAssays) == 2  # noqa: PLR2004
    assert {a.Identifier for a in s1.RegisteredAssays} == {a1_id, a2_id}

    assert len(s2.RegisteredAssays) == 1
    assert s2.RegisteredAssays[0].Identifier == a3_id


@pytest.mark.asyncio
async def test_assay_with_complete_ontology_fields(workflow_tester: WorkflowTester) -> None:
    """Test assay with all ontology-related fields filled (measurement, technology, platform)."""
    inv_id = "INV_ONTOLOGY"
    assay_id = "ASSAY_ONT"

    investigations = [{"identifier": inv_id, "title": "Ontology Test"}]
    assays = [
        {
            "identifier": assay_id,
            "investigation_ref": inv_id,
            "measurement_type_term": "gene expression profiling",
            "measurement_type_uri": "http://purl.obolibrary.org/obo/OBI_0001271",
            "measurement_type_version": "v1",
            "technology_type_term": "nucleotide sequencing",
            "technology_type_uri": "http://purl.obolibrary.org/obo/OBI_0000626",
            "technology_type_version": "v1",
            "technology_platform": "Illumina HiSeq 2500",
        }
    ]

    workflow_tester.set_db_content(
        investigations=investigations,
        assays=assays,
    )

    arcs = await workflow_tester.run()

    assert len(arcs) == 1
    arc = arcs[0]
    assert len(arc.Assays) == 1
    assay = arc.Assays[0]

    # Verify Measurement Type
    assert assay.MeasurementType.Name == "gene expression profiling"
    assert assay.MeasurementType.TermAccessionNumber == "http://purl.obolibrary.org/obo/OBI_0001271"

    # Verify Technology Type
    assert assay.TechnologyType.Name == "nucleotide sequencing"
    assert assay.TechnologyType.TermAccessionNumber == "http://purl.obolibrary.org/obo/OBI_0000626"

    # Verify Technology Platform
    assert assay.TechnologyPlatform.Name == "Illumina HiSeq 2500"




