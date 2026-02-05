"""
Unit tests for business logic components in the middleware API.

This module includes tests for:
- AsyncBusinessLogic (Dispatcher)
- DirectBusinessLogic (Processor)
- BusinessLogicFactory
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from middleware.api.business_logic import AsyncBusinessLogic, DirectBusinessLogic
from middleware.api.business_logic_factory import BusinessLogicFactory
from middleware.shared.api_models.models import ArcOperationResult, ArcResponse, ArcStatus, ArcTaskTicket


@pytest.fixture
def mock_config() -> MagicMock:
    """Mock configuration."""
    config = MagicMock()
    config.couchdb = MagicMock()
    config.gitlab_api = MagicMock()
    config.git_repo = None
    return config


@pytest.fixture
def mock_task_sender() -> MagicMock:
    """Mock Celery task sender."""
    sender = MagicMock()
    sender.delay.return_value = MagicMock(id="task-123")
    return sender


@pytest.mark.asyncio
async def test_async_business_logic(mock_task_sender: MagicMock) -> None:
    """Test AsyncBusinessLogic (Dispatcher)."""
    logic = AsyncBusinessLogic(task_sender=mock_task_sender)

    # Test submission
    result = await logic.create_or_update_arc(rdi="test-rdi", arc={"some": "json"}, client_id="client-1")

    assert isinstance(result, ArcTaskTicket)
    assert result.rdi == "test-rdi"
    assert result.message == "Task enqueued"
    assert result.task_id == "task-123"

    # pylint: disable=protected-access
    assert logic._task_sender == mock_task_sender
    mock_task_sender.delay.assert_called_once()

    # Test health
    health = await logic.health_check()
    assert health["dispatcher"] is True


@pytest.mark.asyncio
async def test_direct_business_logic() -> None:
    """Test DirectBusinessLogic (Processor)."""
    # ... setup mocks ...
    store = MagicMock()
    store.arc_id.return_value = "arc_id"
    store.exists = AsyncMock(return_value=False)
    store.create_or_update = AsyncMock()

    doc_store = MagicMock()
    doc_store.store_arc = AsyncMock()
    doc_store.store_arc.return_value = MagicMock(is_new=True, has_changes=True, should_trigger_git=True)
    doc_store.health_check = AsyncMock(return_value=True)

    logic = DirectBusinessLogic(store=store, doc_store=doc_store)

    # Mock ARC parsing to avoid internal complexities for this unit test
    with patch.object(logic, "_create_arc_from_rocrate", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = ArcResponse(
            id="arc_id", status=ArcStatus.CREATED, timestamp=datetime.now().isoformat()
        )

        result = await logic.create_or_update_arc(
            rdi="test-rdi", arc={"@id": "./", "Identifier": "abc"}, client_id="client-1"
        )

        assert isinstance(result, ArcOperationResult)
        assert result.rdi == "test-rdi"
        assert result.message == "Processed ARC successfully"

        mock_create.assert_called_once()

    # Health check
    health = await logic.health_check()
    assert health["couchdb_reachable"] is True


@pytest.mark.asyncio
async def test_direct_business_logic_store_arc_exception() -> None:
    """Test DirectBusinessLogic exception handling when doc_store fails."""
    store = MagicMock()
    store.arc_id.return_value = "arc-id"
    store.exists = AsyncMock(return_value=False)
    store.create_or_update = AsyncMock()

    doc_store = MagicMock()
    doc_store.store_arc = AsyncMock(side_effect=Exception("CouchDB Down"))

    logic = DirectBusinessLogic(store=store, doc_store=doc_store)

    # Use a real dict that ARC can parse or mock ARC.from_rocrate_json_string
    arc_dict = {"@id": "./", "Identifier": "abc"}

    with patch("middleware.api.business_logic.ARC") as mock_arc_class:
        mock_arc = MagicMock()
        mock_arc.Identifier = "abc"
        mock_arc_class.from_rocrate_json_string.return_value = mock_arc

        # This calls _create_arc_from_rocrate internally
        result = await logic.create_or_update_arc(rdi="test-rdi", arc=arc_dict, client_id="client-1")

        # Verify it proceeded despite CouchDB error
        assert result.arc.id == "arc-id"
        assert result.arc.status == ArcStatus.CREATED
        store.create_or_update.assert_called_once()


@pytest.mark.asyncio
async def test_direct_business_logic_no_doc_store() -> None:
    """Test DirectBusinessLogic with no doc_store (legacy behavior)."""
    store = MagicMock()
    store.arc_id.return_value = "arc-id"
    store.exists = AsyncMock(return_value=True)
    store.create_or_update = AsyncMock()

    logic = DirectBusinessLogic(store=store, doc_store=None)
    arc_dict = {"Identifier": "abc"}

    with patch("middleware.api.business_logic.ARC") as mock_arc_class:
        mock_arc = MagicMock()
        mock_arc.Identifier = "abc"
        mock_arc_class.from_rocrate_json_string.return_value = mock_arc

        result = await logic.create_or_update_arc(rdi="test-rdi", arc=arc_dict, client_id="client-1")

        assert result.arc.status == ArcStatus.UPDATED
        # Verify doc_store access didn't happen
        store.exists.assert_called_once()


def test_factory_dispatcher(mock_config: MagicMock) -> None:
    """Test Factory creating Dispatcher."""
    with patch("middleware.api.worker.process_arc") as mock_process_arc:
        logic = BusinessLogicFactory.create(mock_config, mode="dispatcher")
        assert isinstance(logic, AsyncBusinessLogic)
        # pylint: disable=protected-access
        assert logic._task_sender == mock_process_arc


def test_factory_processor(mock_config: MagicMock) -> None:
    """Test Factory creating Processor."""
    with (
        patch("middleware.api.business_logic_factory.GitlabApi") as mock_gitlab,
        patch("middleware.api.business_logic_factory.CouchDB") as mock_couchdb,
    ):
        logic = BusinessLogicFactory.create(mock_config, mode="processor")
        assert isinstance(logic, DirectBusinessLogic)
        mock_gitlab.assert_called_once()
        mock_couchdb.assert_called_once()
