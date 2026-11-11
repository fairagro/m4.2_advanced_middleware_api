"""Unit tests for BusinessLogic catalog finalize event typing."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from middleware.api.arc_store import ArcStoreError, ArcStoreTransientError, CatalogFinalizeResult
from middleware.api.business_logic import BusinessLogic, BusinessLogicError, TransientError


@pytest.mark.asyncio
async def test_finalize_catalog_requires_consolidated_store(
    worker_logic: BusinessLogic,
) -> None:
    """finalize_catalog fails closed when consolidated_store is absent."""
    with pytest.raises(BusinessLogicError, match="consolidated_store"):
        await worker_logic.finalize_catalog("test-rdi", harvest_id="harvest-1")


@pytest.mark.asyncio
async def test_finalize_catalog_records_success_event_for_catalog_backend(
    worker_logic_with_catalog: BusinessLogic,
    mock_store: MagicMock,
    mock_consolidated_store: MagicMock,
    mock_doc_store: MagicMock,
) -> None:
    """Consolidated catalog finalize records CATALOG_PUSH_SUCCESS on the harvest."""
    mock_consolidated_store.finalize = AsyncMock(return_value=CatalogFinalizeResult(pushed=True, dataset_count=3))
    mock_doc_store.update_harvest = AsyncMock()

    pushed = await worker_logic_with_catalog.finalize_catalog("test-rdi", harvest_id="harvest-1")

    assert pushed is True
    mock_consolidated_store.finalize.assert_awaited_once_with(rdi="test-rdi")
    mock_store.finalize.assert_not_called()
    mock_doc_store.update_harvest.assert_called_once()
    patch = mock_doc_store.update_harvest.call_args.args[1]
    assert patch["append_catalog_event"]["type"] == "CATALOG_PUSH_SUCCESS"
    assert "Published catalog for RDI test-rdi" in patch["append_catalog_event"]["message"]
    assert "skipped" not in patch["append_catalog_event"]["message"]


@pytest.mark.asyncio
async def test_finalize_catalog_records_skipped_when_not_pushed(
    worker_logic_with_catalog: BusinessLogic,
    mock_consolidated_store: MagicMock,
    mock_doc_store: MagicMock,
) -> None:
    """No-op catalog finalize records CATALOG_PUSH_SKIPPED, not SUCCESS."""
    mock_consolidated_store.finalize = AsyncMock(return_value=CatalogFinalizeResult(pushed=False, dataset_count=3))
    mock_doc_store.update_harvest = AsyncMock()

    pushed = await worker_logic_with_catalog.finalize_catalog("test-rdi", harvest_id="harvest-1")

    assert pushed is False
    patch = mock_doc_store.update_harvest.call_args.args[1]
    assert patch["append_catalog_event"]["type"] == "CATALOG_PUSH_SKIPPED"
    assert "Catalog for RDI test-rdi unchanged on remote" in patch["append_catalog_event"]["message"]


@pytest.mark.asyncio
async def test_finalize_catalog_skipped_message_includes_skip_summary(
    worker_logic_with_catalog: BusinessLogic,
    mock_consolidated_store: MagicMock,
    mock_doc_store: MagicMock,
) -> None:
    """Partial ARC skips on a no-op finalize stay visible on CATALOG_PUSH_SKIPPED."""
    mock_consolidated_store.finalize = AsyncMock(
        return_value=CatalogFinalizeResult(
            pushed=False,
            dataset_count=2,
            skipped=(("bad-arc", "JSON-LD expand/compact failed"),),
        )
    )
    mock_doc_store.update_harvest = AsyncMock()

    pushed = await worker_logic_with_catalog.finalize_catalog("test-rdi", harvest_id="harvest-1")

    assert pushed is False
    event = mock_doc_store.update_harvest.call_args.args[1]["append_catalog_event"]
    assert event["type"] == "CATALOG_PUSH_SKIPPED"
    assert "2 datasets" in event["message"]
    assert "1 skipped" in event["message"]
    assert "bad-arc" in event["message"]


@pytest.mark.asyncio
async def test_finalize_catalog_success_message_includes_skip_summary(
    worker_logic_with_catalog: BusinessLogic,
    mock_consolidated_store: MagicMock,
    mock_doc_store: MagicMock,
) -> None:
    """Partial-push skips must appear on CATALOG_PUSH_SUCCESS for harvest visibility."""
    mock_consolidated_store.finalize = AsyncMock(
        return_value=CatalogFinalizeResult(
            pushed=True,
            dataset_count=2,
            skipped=(("bad-arc", "JSON-LD expand/compact failed"),),
        )
    )
    mock_doc_store.update_harvest = AsyncMock()

    pushed = await worker_logic_with_catalog.finalize_catalog("test-rdi", harvest_id="harvest-1")

    assert pushed is True
    message = mock_doc_store.update_harvest.call_args.args[1]["append_catalog_event"]["message"]
    assert "2 datasets" in message
    assert "1 skipped" in message
    assert "bad-arc" in message


@pytest.mark.asyncio
async def test_finalize_catalog_success_message_uses_singular_dataset(
    worker_logic_with_catalog: BusinessLogic,
    mock_consolidated_store: MagicMock,
    mock_doc_store: MagicMock,
) -> None:
    """Single published dataset should use singular wording in the success event."""
    mock_consolidated_store.finalize = AsyncMock(
        return_value=CatalogFinalizeResult(
            pushed=True,
            dataset_count=1,
            skipped=(("bad-arc", "JSON-LD expand/compact failed"),),
        )
    )
    mock_doc_store.update_harvest = AsyncMock()

    pushed = await worker_logic_with_catalog.finalize_catalog("test-rdi", harvest_id="harvest-1")

    assert pushed is True
    message = mock_doc_store.update_harvest.call_args.args[1]["append_catalog_event"]["message"]
    assert "1 dataset" in message
    assert "1 datasets" not in message


@pytest.mark.asyncio
async def test_finalize_catalog_transient_error_skips_failure_event(
    worker_logic_with_catalog: BusinessLogic,
    mock_consolidated_store: MagicMock,
    mock_doc_store: MagicMock,
) -> None:
    """Transient finalize failures must not append CATALOG_PUSH_FAILED before Celery retry."""
    mock_consolidated_store.finalize = AsyncMock(side_effect=ArcStoreTransientError("git unreachable"))
    mock_doc_store.update_harvest = AsyncMock()

    with pytest.raises(TransientError, match="git unreachable"):
        await worker_logic_with_catalog.finalize_catalog("test-rdi", harvest_id="harvest-1")

    mock_doc_store.update_harvest.assert_not_called()


@pytest.mark.asyncio
async def test_finalize_catalog_exhausted_transient_records_failure_event(
    worker_logic_with_catalog: BusinessLogic,
    mock_consolidated_store: MagicMock,
    mock_doc_store: MagicMock,
) -> None:
    """Final Celery attempt records CATALOG_PUSH_FAILED before re-raising TransientError."""
    mock_consolidated_store.finalize = AsyncMock(side_effect=ArcStoreTransientError("git unreachable"))
    mock_doc_store.update_harvest = AsyncMock()

    with pytest.raises(TransientError, match="git unreachable"):
        await worker_logic_with_catalog.finalize_catalog(
            "test-rdi",
            harvest_id="harvest-1",
            record_transient_as_failed=True,
        )

    mock_doc_store.update_harvest.assert_called_once()
    patch = mock_doc_store.update_harvest.call_args.args[1]
    assert patch["append_catalog_event"]["type"] == "CATALOG_PUSH_FAILED"
    assert "git unreachable" in patch["append_catalog_event"]["message"]


@pytest.mark.asyncio
async def test_finalize_catalog_exhausted_transient_redacts_oauth_token(
    worker_logic_with_catalog: BusinessLogic,
    mock_consolidated_store: MagicMock,
    mock_doc_store: MagicMock,
) -> None:
    """Exhausted-transient CATALOG_PUSH_FAILED messages redact oauth2 credentials."""
    mock_consolidated_store.finalize = AsyncMock(
        side_effect=ArcStoreTransientError(
            "push failed: https://oauth2:secret-token@gitlab.example.com/group/catalog.git"
        )
    )
    mock_doc_store.update_harvest = AsyncMock()

    with pytest.raises(TransientError):
        await worker_logic_with_catalog.finalize_catalog(
            "test-rdi",
            harvest_id="harvest-1",
            record_transient_as_failed=True,
        )

    message = mock_doc_store.update_harvest.call_args.args[1]["append_catalog_event"]["message"]
    assert "secret-token" not in message
    assert "https://***@gitlab.example.com" in message


@pytest.mark.asyncio
async def test_finalize_catalog_permanent_error_records_failure_event(
    worker_logic_with_catalog: BusinessLogic,
    mock_consolidated_store: MagicMock,
    mock_doc_store: MagicMock,
) -> None:
    """Permanent catalog push failures record CATALOG_PUSH_FAILED on the harvest."""
    mock_consolidated_store.finalize = AsyncMock(side_effect=ArcStoreError("invalid catalog"))
    mock_doc_store.update_harvest = AsyncMock()

    with pytest.raises(BusinessLogicError, match="catalog finalize failed"):
        await worker_logic_with_catalog.finalize_catalog("test-rdi", harvest_id="harvest-1")

    mock_doc_store.update_harvest.assert_called_once()
    patch = mock_doc_store.update_harvest.call_args.args[1]
    assert patch["append_catalog_event"]["type"] == "CATALOG_PUSH_FAILED"


@pytest.mark.asyncio
async def test_finalize_catalog_redacts_oauth_token_in_failure_event(
    worker_logic_with_catalog: BusinessLogic,
    mock_consolidated_store: MagicMock,
    mock_doc_store: MagicMock,
) -> None:
    """CATALOG_PUSH_FAILED messages must not persist oauth2 credentials in CouchDB."""
    # Plain Exception: no ArcStoreError/BusinessLogicError.__str__ redaction.
    mock_consolidated_store.finalize = AsyncMock(
        side_effect=RuntimeError("push failed: https://oauth2:secret-token@gitlab.example.com/group/catalog.git")
    )
    mock_doc_store.update_harvest = AsyncMock()

    with pytest.raises(BusinessLogicError, match="catalog finalize failed"):
        await worker_logic_with_catalog.finalize_catalog("test-rdi", harvest_id="harvest-1")

    patch = mock_doc_store.update_harvest.call_args.args[1]
    message = patch["append_catalog_event"]["message"]
    assert "secret-token" not in message
    assert "https://***@gitlab.example.com" in message
