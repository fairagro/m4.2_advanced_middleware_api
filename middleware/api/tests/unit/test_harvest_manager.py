"""Unit tests for HarvestManager."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from middleware.api.business_logic.config import HarvestConfig
from middleware.api.business_logic.exceptions import AccessDeniedError, ConflictError, ResourceNotFoundError
from middleware.api.business_logic.harvest_manager import HarvestManager
from middleware.api.document_store.harvest_document import HarvestDocument, HarvestStatistics
from middleware.shared.api_models.common.models import HarvestStatus


def _make_harvest(
    harvest_id: str = "harvest-1",
    rdi: str = "rdi-1",
    client_id: str = "client-a",
    status: HarvestStatus = HarvestStatus.RUNNING,
    statistics: HarvestStatistics | None = None,
) -> HarvestDocument:
    return HarvestDocument(
        doc_id=harvest_id,
        rdi=rdi,
        client_id=client_id,
        status=status,
        started_at=datetime.now(UTC),
        statistics=statistics or HarvestStatistics(),
    )


@pytest.fixture
def doc_store() -> MagicMock:
    """Provide a mocked DocumentStore."""
    return MagicMock()


@pytest.fixture
def harvest_config() -> HarvestConfig:
    """Provide a minimal HarvestConfig."""
    return HarvestConfig()


@pytest.fixture
def manager(doc_store: MagicMock, harvest_config: HarvestConfig) -> HarvestManager:
    """Provide a HarvestManager with mocked dependencies."""
    return HarvestManager(doc_store, harvest_config)


# ---------------------------------------------------------------------------
# from_config factory
# ---------------------------------------------------------------------------
def test_from_config_returns_instance(doc_store: MagicMock, harvest_config: HarvestConfig) -> None:
    """from_config creates a valid HarvestManager."""
    mgr = HarvestManager.from_config(harvest_config, doc_store)
    assert isinstance(mgr, HarvestManager)


# ---------------------------------------------------------------------------
# create_harvest
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_create_harvest(manager: HarvestManager, doc_store: MagicMock) -> None:
    """create_harvest delegates to doc_store and returns the harvest_id."""
    doc_store.create_harvest = AsyncMock(return_value="harvest-99")
    result = await manager.create_harvest("rdi-1", "client-a")
    assert result == "harvest-99"
    doc_store.create_harvest.assert_called_once()


@pytest.mark.asyncio
async def test_create_harvest_with_expected_datasets(manager: HarvestManager, doc_store: MagicMock) -> None:
    """create_harvest passes expected_datasets to doc_store."""
    doc_store.create_harvest = AsyncMock(return_value="harvest-99")
    await manager.create_harvest("rdi-1", "client-a", expected_datasets=42)
    _, kwargs = doc_store.create_harvest.call_args
    assert kwargs.get("expected_datasets") == 42  # noqa: PLR2004


# ---------------------------------------------------------------------------
# get_harvest
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_get_harvest_found(manager: HarvestManager, doc_store: MagicMock) -> None:
    """get_harvest returns the harvest document when found."""
    harvest = _make_harvest()
    doc_store.get_harvest = AsyncMock(return_value=harvest)
    result = await manager.get_harvest("harvest-1")
    assert result is harvest


@pytest.mark.asyncio
async def test_get_harvest_not_found(manager: HarvestManager, doc_store: MagicMock) -> None:
    """get_harvest returns None when not found."""
    doc_store.get_harvest = AsyncMock(return_value=None)
    result = await manager.get_harvest("does-not-exist")
    assert result is None


# ---------------------------------------------------------------------------
# validate_client_id
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_validate_client_id_success(manager: HarvestManager, doc_store: MagicMock) -> None:
    """validate_client_id passes when client_id matches."""
    harvest = _make_harvest(client_id="client-a")
    doc_store.get_harvest = AsyncMock(return_value=harvest)
    # Should not raise
    await manager.validate_client_id("harvest-1", "client-a")


@pytest.mark.asyncio
async def test_validate_client_id_mismatch(manager: HarvestManager, doc_store: MagicMock) -> None:
    """validate_client_id raises AccessDeniedError on client_id mismatch."""
    harvest = _make_harvest(client_id="client-a")
    doc_store.get_harvest = AsyncMock(return_value=harvest)
    with pytest.raises(AccessDeniedError, match="does not belong"):
        await manager.validate_client_id("harvest-1", "wrong-client")


@pytest.mark.asyncio
async def test_validate_client_id_harvest_not_found(manager: HarvestManager, doc_store: MagicMock) -> None:
    """validate_client_id raises ResourceNotFoundError when harvest not found."""
    doc_store.get_harvest = AsyncMock(return_value=None)
    with pytest.raises(ResourceNotFoundError, match="not found"):
        await manager.validate_client_id("no-such-harvest", "client-a")


# ---------------------------------------------------------------------------
# complete_harvest
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_complete_harvest_success(manager: HarvestManager, doc_store: MagicMock) -> None:
    """complete_harvest marks the harvest COMPLETED and updates statistics."""
    stats = HarvestStatistics(arcs_submitted=5)
    harvest = _make_harvest(client_id="client-a", statistics=stats)
    updated = _make_harvest(client_id="client-a", status=HarvestStatus.COMPLETED, statistics=stats)

    doc_store.get_harvest_statistics = AsyncMock(return_value=HarvestStatistics(arcs_submitted=5))
    doc_store.update_harvest = AsyncMock(return_value=updated)

    result = await manager.complete_harvest(harvest, "client-a")
    assert result.status == HarvestStatus.COMPLETED
    doc_store.update_harvest.assert_called_once()


@pytest.mark.asyncio
async def test_complete_harvest_preserves_expected_datasets(manager: HarvestManager, doc_store: MagicMock) -> None:
    """complete_harvest preserves expected_datasets already set in the harvest."""
    harvest = _make_harvest(client_id="client-a", statistics=HarvestStatistics(expected_datasets=10))
    updated = _make_harvest(client_id="client-a", status=HarvestStatus.COMPLETED)

    doc_store.get_harvest_statistics = AsyncMock(return_value=HarvestStatistics())
    doc_store.update_harvest = AsyncMock(return_value=updated)

    await manager.complete_harvest(harvest, "client-a")

    # expected_datasets should be forwarded to the update call
    call_args = doc_store.update_harvest.call_args
    assert call_args[0][1]["statistics"]["expected_datasets"] == 10  # noqa: PLR2004


@pytest.mark.asyncio
async def test_complete_harvest_client_id_mismatch(manager: HarvestManager) -> None:
    """complete_harvest raises AccessDeniedError when client_id does not match."""
    harvest = _make_harvest(client_id="client-a")
    with pytest.raises(AccessDeniedError, match="does not belong"):
        await manager.complete_harvest(harvest, "wrong-client")


# ---------------------------------------------------------------------------
# cancel_harvest
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_cancel_harvest_success(manager: HarvestManager, doc_store: MagicMock) -> None:
    """cancel_harvest updates status to CANCELLED and persists statistics."""
    harvest = _make_harvest(client_id="client-a")
    doc_store.get_harvest_statistics = AsyncMock(return_value=HarvestStatistics())
    doc_store.update_harvest = AsyncMock()

    await manager.cancel_harvest(harvest, "client-a")
    doc_store.update_harvest.assert_called_once()
    call_args = doc_store.update_harvest.call_args
    assert call_args[0][1]["status"] == HarvestStatus.CANCELLED


@pytest.mark.asyncio
async def test_cancel_harvest_client_id_mismatch(manager: HarvestManager) -> None:
    """cancel_harvest raises AccessDeniedError when client_id does not match."""
    harvest = _make_harvest(client_id="client-a")
    with pytest.raises(AccessDeniedError, match="does not belong"):
        await manager.cancel_harvest(harvest, "wrong-client")


# ---------------------------------------------------------------------------
# list_harvests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_list_harvests_all(manager: HarvestManager, doc_store: MagicMock) -> None:
    """list_harvests without rdi filter returns all harvests."""
    harvests = [_make_harvest("h1"), _make_harvest("h2")]
    doc_store.list_harvests = AsyncMock(return_value=harvests)
    result = await manager.list_harvests()
    assert result == harvests


@pytest.mark.asyncio
async def test_list_harvests_filtered(manager: HarvestManager, doc_store: MagicMock) -> None:
    """list_harvests with rdi filter forwards rdi to doc_store."""
    doc_store.list_harvests = AsyncMock(return_value=[_make_harvest()])
    await manager.list_harvests(rdi="rdi-1")
    doc_store.list_harvests.assert_called_once_with("rdi-1", skip=0, limit=None)


# ---------------------------------------------------------------------------
# transition_harvest
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@pytest.mark.parametrize("target_status", [HarvestStatus.COMPLETED, HarvestStatus.CANCELLED, HarvestStatus.FAILED])
async def test_transition_harvest_success(
    manager: HarvestManager, doc_store: MagicMock, target_status: HarvestStatus
) -> None:
    """transition_harvest updates status for all terminal states when harvest is RUNNING."""
    harvest = _make_harvest(client_id="client-a", status=HarvestStatus.RUNNING)
    updated = _make_harvest(client_id="client-a", status=target_status)
    doc_store.get_harvest_statistics = AsyncMock(return_value=HarvestStatistics())
    doc_store.update_harvest = AsyncMock(return_value=updated)

    result = await manager.transition_harvest(harvest, target_status, "client-a")

    doc_store.update_harvest.assert_called_once()
    call_args = doc_store.update_harvest.call_args
    assert call_args[0][1]["status"] == target_status
    assert result.status == target_status


@pytest.mark.asyncio
async def test_transition_harvest_client_id_mismatch(manager: HarvestManager) -> None:
    """transition_harvest raises AccessDeniedError when client_id does not match."""
    harvest = _make_harvest(client_id="client-a", status=HarvestStatus.RUNNING)
    with pytest.raises(AccessDeniedError, match="does not belong"):
        await manager.transition_harvest(harvest, HarvestStatus.CANCELLED, "wrong-client")


@pytest.mark.asyncio
@pytest.mark.parametrize("current_status", [HarvestStatus.COMPLETED, HarvestStatus.CANCELLED, HarvestStatus.FAILED])
async def test_transition_harvest_conflict(manager: HarvestManager, current_status: HarvestStatus) -> None:
    """transition_harvest raises ConflictError when harvest is not RUNNING."""
    harvest = _make_harvest(client_id="client-a", status=current_status)
    with pytest.raises(ConflictError, match="cannot transition"):
        await manager.transition_harvest(harvest, HarvestStatus.CANCELLED, "client-a")
