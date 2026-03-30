"""Unit tests for the unified BusinessLogic class."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from middleware.api.business_logic import (
    BusinessLogic,
    BusinessLogicError,
    BusinessLogicFactory,
    InvalidJsonSemanticError,
    SetupError,
)
from middleware.api.business_logic.ports import BusinessLogicPorts
from middleware.api.business_logic.task_payloads import ArcSyncTask
from middleware.api.document_store import ArcStoreResult
from middleware.api.document_store.harvest_document import HarvestStatistics
from middleware.shared.api_models.common.models import ArcOperationResult, ArcStatus


@pytest.fixture
def mock_store() -> MagicMock:
    """Mock ArcStore."""
    store = MagicMock()
    # Mock arc_id to use hashing or simpler return
    store.arc_id.side_effect = lambda i, r: f"arc_{i}_{r}"
    store.create_or_update = AsyncMock()
    store.shutdown = AsyncMock()
    return store


@pytest.fixture
def mock_doc_store() -> MagicMock:
    """Mock DocumentStore."""
    doc_store = MagicMock()
    doc_store.store_arc = AsyncMock()
    doc_store.add_event = AsyncMock()
    doc_store.health_check = AsyncMock(return_value=True)
    doc_store.setup = AsyncMock()
    doc_store.connect = AsyncMock()
    doc_store.close = AsyncMock()
    return doc_store


@pytest.fixture
def mock_task_dispatcher() -> MagicMock:
    """Mock TaskDispatcher."""
    dispatcher = MagicMock()
    dispatcher.dispatch_sync_arc = MagicMock()
    return dispatcher


@pytest.fixture
def mock_broker_health_checker() -> MagicMock:
    """Mock BrokerHealthChecker."""
    broker_checker = MagicMock()
    broker_checker.is_healthy = MagicMock(return_value=True)
    return broker_checker


@pytest.fixture
def mock_config() -> MagicMock:
    """Mock Config."""
    config = MagicMock()
    config.celery.result_backend.get_secret_value.return_value = "redis://localhost:6379/0"
    return config


@pytest.fixture
def api_logic(
    mock_config: MagicMock,
    mock_store: MagicMock,
    mock_doc_store: MagicMock,
    api_ports: BusinessLogicPorts,
) -> BusinessLogic:
    """BusinessLogic in API mode."""
    return BusinessLogic(
        config=mock_config,
        store=mock_store,
        doc_store=mock_doc_store,
        ports=api_ports,
    )


@pytest.fixture
def api_ports(
    mock_task_dispatcher: MagicMock,
    mock_broker_health_checker: MagicMock,
) -> BusinessLogicPorts:
    """Bundle API mode ports for BusinessLogic."""
    return BusinessLogicPorts(
        task_dispatcher=mock_task_dispatcher,
        broker_health_checker=mock_broker_health_checker,
    )


@pytest.fixture
def worker_logic(mock_config: MagicMock, mock_store: MagicMock, mock_doc_store: MagicMock) -> BusinessLogic:
    """BusinessLogic in Worker mode."""
    return BusinessLogic(config=mock_config, store=mock_store, doc_store=mock_doc_store)


@pytest.mark.asyncio
async def test_api_mode_create_or_update_success(
    api_logic: BusinessLogic, mock_doc_store: MagicMock, mock_task_dispatcher: MagicMock
) -> None:
    """Test create_or_update_arc in API mode."""
    rdi = "test-rdi"
    arc_data = {"@context": "https://w3id.org/ro/crate/1.1/context", "@graph": [{"@id": "./", "identifier": "ABC"}]}
    client_id = "test-client"

    # Mock doc_store result
    mock_doc_store.store_arc.return_value = ArcStoreResult(arc_id="arc_id", is_new=True, has_changes=True)

    # Mock ARC
    with patch("middleware.api.business_logic.arc_manager.ARC") as mock_arc_class:
        mock_arc_instance = MagicMock()
        mock_arc_instance.Identifier = "ABC"
        mock_arc_class.from_rocrate_json_string.return_value = mock_arc_instance

        with patch("middleware.api.business_logic.arc_manager.calculate_arc_id", return_value="arc_id"):
            result = await api_logic.create_or_update_arc(rdi, arc_data, client_id)

    assert isinstance(result, ArcOperationResult)
    assert result.arc.id == "arc_id"
    assert result.arc.status == ArcStatus.CREATED

    # Verify calls
    mock_doc_store.store_arc.assert_called_once()
    mock_task_dispatcher.dispatch_sync_arc.assert_called_once_with(
        ArcSyncTask(rdi=rdi, arc=arc_data, client_id=client_id)
    )


@pytest.mark.asyncio
async def test_api_mode_sync_to_gitlab_forbidden(api_logic: BusinessLogic) -> None:
    """Test calling sync_to_gitlab in API mode raises error."""
    with pytest.raises(BusinessLogicError, match="sync_to_gitlab must not be called in API mode"):
        await api_logic.sync_to_gitlab("rdi", {})


@pytest.mark.asyncio
async def test_health_check(
    api_logic: BusinessLogic, mock_doc_store: MagicMock, mock_broker_health_checker: MagicMock
) -> None:
    """Test health_check includes only real dependencies."""
    mock_doc_store.health_check.return_value = True

    mock_broker_health_checker.is_healthy.return_value = True
    result = await api_logic.health_check()

    assert result == {
        "couchdb_reachable": True,
        "rabbitmq": True,
    }


@pytest.mark.asyncio
async def test_health_check_failures(
    api_logic: BusinessLogic, mock_doc_store: MagicMock, mock_broker_health_checker: MagicMock
) -> None:
    """Test aggregated health check with failures."""
    mock_doc_store.health_check.return_value = False

    mock_broker_health_checker.is_healthy.return_value = False

    status = await api_logic.health_check()
    assert status["couchdb_reachable"] is False
    assert status["rabbitmq"] is False


@pytest.mark.asyncio
async def test_lifecycle_methods(api_logic: BusinessLogic, mock_doc_store: MagicMock) -> None:
    """Test lifecycle methods through the business logic."""
    async with api_logic as ctx:
        assert ctx == api_logic
        mock_doc_store.setup.assert_called_once()
        mock_doc_store.connect.assert_called_once()

    mock_doc_store.close.assert_called_once()


@pytest.mark.asyncio
async def test_setup_failure(api_logic: BusinessLogic, mock_doc_store: MagicMock) -> None:
    """Test setup failure."""
    mock_doc_store.setup.side_effect = Exception("DB Fail")
    with pytest.raises(SetupError, match="Failed to setup business logic"):
        await api_logic.startup()


@pytest.mark.asyncio
async def test_worker_mode_sync_to_gitlab_success(worker_logic: BusinessLogic, mock_store: MagicMock) -> None:
    """Test sync_to_gitlab in Worker mode."""
    rdi = "test-rdi"
    arc_data = {"@context": "https://w3id.org/ro/crate/1.1/context", "@graph": [{"@id": "./", "identifier": "ABC"}]}

    with patch("middleware.api.business_logic.arc_manager.ARC") as mock_arc_class:
        mock_arc_instance = MagicMock()
        mock_arc_instance.Identifier = "ABC"
        mock_arc_class.from_rocrate_json_string.return_value = mock_arc_instance

        with patch("middleware.api.business_logic.arc_manager.calculate_arc_id", return_value="arc_id"):
            await worker_logic.sync_to_gitlab(rdi, arc_data)

    # Verify store called
    mock_store.create_or_update.assert_called_once()
    args, _ = mock_store.create_or_update.call_args
    assert args[0] == "arc_id"
    # Can't check isinstance ARC because we mocked it
    # assert isinstance(args[1], ARC)


@pytest.mark.asyncio
async def test_worker_mode_create_or_update_forbidden(worker_logic: BusinessLogic) -> None:
    """Test calling create_or_update_arc in Worker mode raises error."""
    with pytest.raises(BusinessLogicError, match="create_or_update_arc can only be called in API mode"):
        await worker_logic.create_or_update_arc("rdi", {}, "client")


@pytest.mark.asyncio
async def test_api_mode_skips_sync_if_no_changes(
    api_logic: BusinessLogic, mock_doc_store: MagicMock, mock_task_dispatcher: MagicMock
) -> None:
    """Test that GitLab sync is skipped if no changes."""
    mock_doc_store.store_arc.return_value = ArcStoreResult(arc_id="arc_id", is_new=False, has_changes=False)

    rdi = "test-rdi"
    arc_data = {"@context": "https://w3id.org/ro/crate/1.1/context", "@graph": [{"@id": "./", "identifier": "ABC"}]}

    with patch("middleware.api.business_logic.arc_manager.ARC") as mock_arc_class:
        mock_arc_instance = MagicMock()
        mock_arc_instance.Identifier = "ABC"
        mock_arc_class.from_rocrate_json_string.return_value = mock_arc_instance

        with patch("middleware.api.business_logic.arc_manager.calculate_arc_id", return_value="arc_id"):
            await api_logic.create_or_update_arc(rdi, arc_data, "client")

    mock_doc_store.store_arc.assert_called_once()
    mock_task_dispatcher.dispatch_sync_arc.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case",
    [
        (True, True, "arcs_new"),
        (False, True, "arcs_updated"),
        (False, False, "arcs_unchanged"),
    ],
)
async def test_api_mode_increments_harvest_statistics(
    api_logic: BusinessLogic,
    mock_doc_store: MagicMock,
    mock_task_dispatcher: MagicMock,
    case: tuple[bool, bool, str],
) -> None:
    """ARC submissions in a harvest increment the corresponding harvest counters."""
    is_new, has_changes, counter_key = case
    mock_doc_store.store_arc.return_value = ArcStoreResult(
        arc_id="arc_id",
        is_new=is_new,
        has_changes=has_changes,
    )
    mock_doc_store.get_harvest = AsyncMock(
        return_value=MagicMock(
            client_id="client",
            statistics=HarvestStatistics(),
        )
    )
    mock_doc_store.update_harvest = AsyncMock()

    rdi = "test-rdi"
    harvest_id = "harvest-1"
    arc_data = {"@context": "https://w3id.org/ro/crate/1.1/context", "@graph": [{"@id": "./", "identifier": "ABC"}]}

    await api_logic.create_or_update_arc(rdi, arc_data, "client", harvest_id=harvest_id)

    mock_doc_store.update_harvest.assert_called_once()
    _, kwargs = mock_doc_store.update_harvest.call_args
    assert kwargs == {}
    call_args = mock_doc_store.update_harvest.call_args[0]
    assert call_args[0] == harvest_id
    stats = call_args[1]["statistics"]
    assert stats["arcs_submitted"] == 1  # noqa: PLR2004
    assert stats[counter_key] == 1  # noqa: PLR2004

    if is_new or has_changes:
        mock_task_dispatcher.dispatch_sync_arc.assert_called_once()
    else:
        mock_task_dispatcher.dispatch_sync_arc.assert_not_called()


def test_factory_create_api_mode() -> None:
    """Test factory creates API mode BusinessLogic."""
    config = MagicMock()
    config.git_repo = MagicMock()
    config.couchdb = MagicMock()

    with (
        patch("middleware.api.business_logic.business_logic_factory.CouchDB"),
        patch("middleware.api.business_logic.business_logic_factory.GitRepo"),
    ):
        bl = BusinessLogicFactory.create(
            config,
            mode="api",
            task_dispatcher=MagicMock(),
            broker_health_checker=MagicMock(),
        )

    assert isinstance(bl, BusinessLogic)


@pytest.mark.asyncio
async def test_create_or_update_arc_parse_failure(api_logic: BusinessLogic) -> None:
    """Test create_or_update_arc with missing identifier."""
    # Since we now use fast validation, an empty dict fails the identifier check
    with pytest.raises(InvalidJsonSemanticError, match="must contain an 'identifier'"):
        await api_logic.create_or_update_arc("test_rdi", {}, "client_1")


@pytest.mark.asyncio
async def test_create_or_update_missing_identifier(api_logic: BusinessLogic) -> None:
    """Test create_or_update_arc with missing Identifier in RO-Crate graph."""
    # Data has @graph but no "@id": "./" element with identifier
    arc_data = {"@context": "https://w3id.org/ro/crate/1.1/context", "@graph": [{"@id": "not-root"}]}

    with pytest.raises(InvalidJsonSemanticError, match="must contain an 'identifier'"):
        await api_logic.create_or_update_arc("test_rdi", arc_data, "client_1")


@pytest.mark.asyncio
async def test_create_or_update_generic_exception(api_logic: BusinessLogic, mock_doc_store: MagicMock) -> None:
    """Test create_or_update_arc with unexpected exception."""
    mock_doc_store.store_arc.side_effect = Exception("Unexpected failure")
    # Valid data to pass the fast identifier check
    arc_data = {"@context": "https://w3id.org/ro/crate/1.1/context", "@graph": [{"@id": "./", "identifier": "test"}]}

    with pytest.raises(BusinessLogicError, match="unexpected error encountered"):
        await api_logic.create_or_update_arc("test_rdi", arc_data, "client_1")


@pytest.mark.asyncio
async def test_sync_to_gitlab_missing_identifier(worker_logic: BusinessLogic) -> None:
    """Test sync_to_gitlab with missing Identifier."""
    arc_data = {"@context": "https://w3id.org/ro/crate/1.1/context", "@graph": [{"@id": "arc"}]}

    with pytest.raises(InvalidJsonSemanticError, match="must contain an 'identifier'"):
        await worker_logic.sync_to_gitlab("test_rdi", arc_data)


@pytest.mark.asyncio
async def test_sync_to_gitlab_generic_exception(worker_logic: BusinessLogic, mock_store: MagicMock) -> None:
    """Test sync_to_gitlab with unexpected exception."""
    mock_store.create_or_update.side_effect = Exception("Git failure")
    arc_data = {"@context": "https://w3id.org/ro/crate/1.1/context", "@graph": [{"@id": "./", "identifier": "test"}]}

    with patch("middleware.api.business_logic.arc_manager.ARC") as mock_arc_class:
        mock_arc_obj = MagicMock()
        mock_arc_obj.Identifier = "test"
        mock_arc_class.from_rocrate_json_string.return_value = mock_arc_obj

        with pytest.raises(BusinessLogicError, match="unexpected error encountered"):
            await worker_logic.sync_to_gitlab("test_rdi", arc_data)


@pytest.mark.asyncio
async def test_sync_to_gitlab_business_logic_error(api_logic: BusinessLogic) -> None:
    """Test sync_to_gitlab in API mode (should fail)."""
    with pytest.raises(BusinessLogicError, match="must not be called in API mode"):
        await api_logic.sync_to_gitlab("test_rdi", {})
