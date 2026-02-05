"""Unit tests for BusinessLogic refactoring."""
from unittest.mock import MagicMock, AsyncMock, patch
import pytest

from middleware.api.business_logic import AsyncBusinessLogic, DirectBusinessLogic, BusinessLogic
from middleware.api.business_logic_factory import BusinessLogicFactory
from middleware.shared.api_models.models import ArcOperationResult, ArcResponse, ArcStatus
from datetime import datetime

@pytest.fixture
def mock_config():
    """Mock configuration."""
    config = MagicMock()
    config.couchdb = MagicMock()
    config.gitlab_api = MagicMock()
    config.git_repo = None
    return config

@pytest.fixture
def mock_task_sender():
    """Mock Celery task sender."""
    sender = MagicMock()
    sender.delay.return_value = MagicMock(id="task-123")
    return sender

@pytest.mark.asyncio
async def test_async_business_logic(mock_task_sender):
    """Test AsyncBusinessLogic (Dispatcher)."""
    logic = AsyncBusinessLogic(task_sender=mock_task_sender)
    
    # Test submission
    result = await logic.create_or_update_arc(
        rdi="test-rdi", 
        arc={"some": "json"}, 
        client_id="client-1"
    )
    
    assert isinstance(result, ArcOperationResult)
    assert result.rdi == "test-rdi"
    assert result.message == "Task enqueued"
    assert result.task_id == "task-123"
    
    mock_task_sender.delay.assert_called_once()
    
    # Test health
    health = await logic.health_check()
    assert health["dispatcher"] is True

from middleware.shared.api_models.models import ArcOperationResult, ArcResponse, ArcStatus
from datetime import datetime

# ...

@pytest.mark.asyncio
async def test_direct_business_logic():
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
            rdi="test-rdi", 
            arc={"@id": "./", "Identifier": "abc"}, 
            client_id="client-1"
        )
        
        assert isinstance(result, ArcOperationResult)
        assert result.rdi == "test-rdi"
        assert result.message == "Processed ARC successfully"
        
        mock_create.assert_called_once()
        
    # Health check
    health = await logic.health_check()
    assert health["couchdb_reachable"] is True

def test_factory_dispatcher(mock_config):
    """Test Factory creating Dispatcher."""
    with patch("middleware.api.worker.process_arc") as mock_process_arc:
        logic = BusinessLogicFactory.create(mock_config, mode="dispatcher")
        assert isinstance(logic, AsyncBusinessLogic)
        assert logic._task_sender == mock_process_arc

def test_factory_processor(mock_config):
    """Test Factory creating Processor."""
    with patch("middleware.api.business_logic_factory.GitlabApi") as mock_gitlab, \
         patch("middleware.api.business_logic_factory.CouchDB") as mock_couchdb:
        
        logic = BusinessLogicFactory.create(mock_config, mode="processor")
        assert isinstance(logic, DirectBusinessLogic)
        mock_gitlab.assert_called_once()
        mock_couchdb.assert_called_once()
