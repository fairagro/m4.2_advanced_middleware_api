"""Unit tests for CouchDB harvest statistics, catalog events, and finalize lock."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import SecretStr, ValidationError

from middleware.api.document_store.config import CouchDBConfig
from middleware.api.document_store.couchdb import CouchDB
from middleware.api.document_store.couchdb_client import DocumentConflictError
from middleware.shared.api_models.common.models import HarvestStatus


@pytest.fixture
def config() -> CouchDBConfig:
    """Create test configuration."""
    return CouchDBConfig(url="http://test:5984", user="user", password=SecretStr("pass"))


@pytest.fixture
def mock_client_instance() -> MagicMock:
    """Create a mock client instance."""
    client = MagicMock()
    # Async methods need to be AsyncMock
    client.connect = AsyncMock()
    client.close = AsyncMock()
    client.health_check = AsyncMock(return_value=True)
    client.get_document = AsyncMock()
    client.save_document = AsyncMock()
    client.save_document_if_revision_matches = AsyncMock()
    client.create_index = AsyncMock()
    client.set_reinit_hook = MagicMock()
    client.application_database_exists = AsyncMock(return_value=True)
    client._inside_reinit = False
    client._client = MagicMock()
    client._db = MagicMock()
    client._db_name = "test"
    return client


@pytest.fixture
def store(config: CouchDBConfig, mock_client_instance: MagicMock) -> CouchDB:
    """Create CouchDB store with mocked client."""
    # Patch where CouchDB calls CouchDBClient.from_config
    with patch("middleware.api.document_store.couchdb.CouchDBClient.from_config", return_value=mock_client_instance):
        store_inst = CouchDB(config)
        return store_inst


def test_max_catalog_event_log_size_defaults_to_100_and_rejects_below_one() -> None:
    """Catalog-event cap defaults to 100 and cannot drop the event just appended."""
    config = CouchDBConfig(url="http://test:5984")
    assert config.max_catalog_event_log_size == 100
    with pytest.raises(ValidationError):
        CouchDBConfig(url="http://test:5984", max_catalog_event_log_size=0)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "meta_patch, expected_new, expected_updated, expected_unchanged",
    [
        # ARC created in this harvest
        ({"first_harvest_id": "h1", "last_changed_harvest_id": "h1"}, 1, 0, 0),
        # ARC updated in this harvest (existed before)
        ({"first_harvest_id": "h0", "last_changed_harvest_id": "h1"}, 0, 1, 0),
        # ARC seen but unchanged
        ({"first_harvest_id": "h0", "last_changed_harvest_id": "h0"}, 0, 0, 1),
        # ARC seen but last_changed_harvest_id is None (old document, no field)
        ({"first_harvest_id": "h0", "last_changed_harvest_id": None}, 0, 0, 1),
    ],
)
async def test_get_harvest_statistics(  # noqa: PLR0913, PLR0917
    store: CouchDB,
    mock_client_instance: MagicMock,
    meta_patch: dict,
    expected_new: int,
    expected_updated: int,
    expected_unchanged: int,
) -> None:
    """get_harvest_statistics classifies ARCs via first_harvest_id and last_changed_harvest_id."""
    harvest_id = "h1"
    mock_client_instance.find_projected = AsyncMock(return_value=[{"metadata": meta_patch}])

    stats = await store.get_harvest_statistics(harvest_id)

    mock_client_instance.find_projected.assert_awaited_once_with(
        {"doc_type": "arc", "metadata.last_harvest_id": harvest_id},
        fields=["metadata.first_harvest_id", "metadata.last_changed_harvest_id"],
        limit=100,
        skip=0,
    )

    assert stats.arcs_submitted == 1
    assert stats.arcs_new == expected_new
    assert stats.arcs_updated == expected_updated
    assert stats.arcs_unchanged == expected_unchanged


@pytest.mark.asyncio
async def test_get_harvest_statistics_paginates_beyond_default_query_limit(
    mock_client_instance: MagicMock,
) -> None:
    """Statistics scan all Mango pages, not only the first default_query_limit rows."""
    page_size = 3
    page_config = CouchDBConfig(
        url="http://test:5984",
        user="user",
        password=SecretStr("pass"),
        default_query_limit=page_size,
    )
    with patch(
        "middleware.api.document_store.couchdb.CouchDBClient.from_config",
        return_value=mock_client_instance,
    ):
        store = CouchDB(page_config)

    harvest_id = "h1"
    page_one = [
        {"metadata": {"first_harvest_id": harvest_id, "last_changed_harvest_id": harvest_id}} for _ in range(page_size)
    ]
    page_two = [{"metadata": {"first_harvest_id": "h0", "last_changed_harvest_id": harvest_id}}]
    expected_submitted = page_size + len(page_two)
    expected_pages = 2

    async def _find_projected(
        _selector: dict,
        *,
        fields: list[str],
        limit: int | None = None,
        skip: int = 0,
    ) -> list[dict]:
        assert fields == ["metadata.first_harvest_id", "metadata.last_changed_harvest_id"]
        assert limit == page_size
        if skip == 0:
            return page_one
        if skip == page_size:
            return page_two
        return []

    mock_client_instance.find_projected = AsyncMock(side_effect=_find_projected)

    stats = await store.get_harvest_statistics(harvest_id)

    assert mock_client_instance.find_projected.await_count == expected_pages
    assert stats.arcs_submitted == expected_submitted
    assert stats.arcs_new == page_size
    assert stats.arcs_updated == len(page_two)
    assert stats.arcs_unchanged == 0


@pytest.mark.asyncio
async def test_iter_arc_contents_by_rdi(store: CouchDB, mock_client_instance: MagicMock) -> None:
    """iter_arc_contents_by_rdi streams arc_id and RO-Crate bodies for an RDI."""
    content = {"@context": "https://w3id.org/ro/crate/1.1/context", "@graph": []}
    mock_client_instance.find_page = AsyncMock(
        return_value=([{"_id": "arc_ds-1", "doc_type": "arc", "rdi": "edal", "arc_content": content}], "bm-1"),
    )

    results = [item async for item in store.iter_arc_contents_by_rdi("edal")]

    assert results == [("ds-1", content)]
    mock_client_instance.find_page.assert_awaited_once_with(
        {"doc_type": "arc", "rdi": "edal"},
        limit=500,
        bookmark=None,
        sort=[{"doc_type": "asc"}, {"rdi": "asc"}, {"_id": "asc"}],
    )


@pytest.mark.asyncio
async def test_iter_arc_contents_by_rdi_pages(
    store: CouchDB,
    mock_client_instance: MagicMock,
) -> None:
    """Streaming walks multiple Mango bookmark pages without building a full list."""
    page_size = 2
    store._config.catalog_list_page_size = page_size  # noqa: SLF001
    content = {"@context": "https://w3id.org/ro/crate/1.1/context", "@graph": []}
    page1 = [
        {"_id": "arc_ds-1", "doc_type": "arc", "rdi": "edal", "arc_content": content},
        {"_id": "arc_ds-2", "doc_type": "arc", "rdi": "edal", "arc_content": content},
    ]
    page2 = [
        {"_id": "arc_ds-3", "doc_type": "arc", "rdi": "edal", "arc_content": content},
    ]
    mock_client_instance.find_page = AsyncMock(
        side_effect=[(page1, "bm-after-1"), (page2, "bm-after-2")],
    )

    results = [item async for item in store.iter_arc_contents_by_rdi("edal")]

    assert [arc_id for arc_id, _ in results] == ["ds-1", "ds-2", "ds-3"]
    assert mock_client_instance.find_page.await_count == 2
    first_call = mock_client_instance.find_page.await_args_list[0]
    second_call = mock_client_instance.find_page.await_args_list[1]
    assert first_call.kwargs["limit"] == page_size
    assert first_call.kwargs["bookmark"] is None
    assert second_call.kwargs["limit"] == page_size
    assert second_call.kwargs["bookmark"] == "bm-after-1"


@pytest.mark.asyncio
async def test_iter_arc_contents_by_rdi_rejects_malformed_docs(
    store: CouchDB,
    mock_client_instance: MagicMock,
) -> None:
    """Malformed ARC documents must fail the catalog stream, not be skipped."""
    mock_client_instance.find_page = AsyncMock(
        return_value=([{"_id": "not_an_arc", "doc_type": "arc", "rdi": "edal", "arc_content": {}}], None),
    )
    with pytest.raises(ValueError, match="expected _id starting with 'arc_'"):
        async for _ in store.iter_arc_contents_by_rdi("edal"):
            pass

    mock_client_instance.find_page = AsyncMock(
        return_value=([{"_id": "arc_ds-1", "doc_type": "arc", "rdi": "edal", "arc_content": "oops"}], None),
    )
    with pytest.raises(ValueError, match="arc_content must be an object"):
        async for _ in store.iter_arc_contents_by_rdi("edal"):
            pass


@pytest.mark.asyncio
async def test_update_harvest_append_catalog_event_retries_on_conflict(
    store: CouchDB,
    mock_client_instance: MagicMock,
) -> None:
    """Concurrent harvest updates re-fetch and re-append instead of clobbering events."""
    harvest_id = "harvest-1"
    base = {
        "_id": harvest_id,
        "type": "harvest",
        "rdi": "edal",
        "started_at": "2024-01-01T00:00:00+00:00",
        "status": HarvestStatus.COMPLETED.value,
        "statistics": {},
        "catalog_events": [],
    }
    concurrent = {
        **base,
        "_rev": "2-bbb",
        "catalog_events": [
            {
                "timestamp": "2024-01-01T00:00:01+00:00",
                "type": "CATALOG_PUSH_SUCCESS",
                "message": "first",
            }
        ],
    }
    mock_client_instance.get_document = AsyncMock(
        side_effect=[
            {**base, "_rev": "1-aaa"},
            concurrent,
        ]
    )
    mock_client_instance.save_document_if_revision_matches = AsyncMock(
        side_effect=[DocumentConflictError("conflict"), {**concurrent, "_rev": "3-ccc"}],
    )

    updated = await store.update_harvest(
        harvest_id,
        {
            "append_catalog_event": {
                "timestamp": "2024-01-01T00:00:02+00:00",
                "type": "CATALOG_PUSH_FAILED",
                "message": "second",
            }
        },
    )

    assert len(updated.catalog_events) == 2
    assert updated.catalog_events[0].message == "first"
    assert updated.catalog_events[1].message == "second"
    assert mock_client_instance.save_document_if_revision_matches.await_count == 2
    second_payload = mock_client_instance.save_document_if_revision_matches.await_args_list[1].args[1]
    assert len(second_payload["catalog_events"]) == 2
    mock_client_instance.save_document.assert_not_called()


def _harvest_with_catalog_events(messages: list[str]) -> dict[str, object]:
    """Harvest document body with one catalog event per message."""
    return {
        "_id": "harvest-1",
        "_rev": "1-aaa",
        "type": "harvest",
        "rdi": "edal",
        "started_at": "2024-01-01T00:00:00+00:00",
        "status": HarvestStatus.COMPLETED.value,
        "statistics": {},
        "catalog_events": [
            {
                "timestamp": f"2024-01-01T00:00:{index:02d}+00:00",
                "type": "CATALOG_PUSH_SUCCESS",
                "message": message,
            }
            for index, message in enumerate(messages)
        ],
    }


@pytest.mark.asyncio
async def test_update_harvest_append_catalog_event_drops_oldest_past_maximum(
    store: CouchDB,
    mock_client_instance: MagicMock,
) -> None:
    """An append past the cap keeps the newest events and drops the oldest."""
    store._config.max_catalog_event_log_size = 2  # noqa: SLF001
    mock_client_instance.get_document = AsyncMock(return_value=_harvest_with_catalog_events(["oldest", "middle"]))
    mock_client_instance.save_document_if_revision_matches = AsyncMock(return_value={"_rev": "2-bbb"})

    updated = await store.update_harvest(
        "harvest-1",
        {
            "append_catalog_event": {
                "timestamp": "2024-01-01T00:00:03+00:00",
                "type": "CATALOG_PUSH_FAILED",
                "message": "newest",
            }
        },
    )

    assert [event.message for event in updated.catalog_events] == ["middle", "newest"]
    saved = mock_client_instance.save_document_if_revision_matches.await_args.args[1]
    assert [event["message"] for event in saved["catalog_events"]] == ["middle", "newest"]


@pytest.mark.asyncio
async def test_update_harvest_append_catalog_event_keeps_events_under_maximum(
    store: CouchDB,
    mock_client_instance: MagicMock,
) -> None:
    """An append under the cap keeps every previous event and puts the new one last."""
    store._config.max_catalog_event_log_size = 3  # noqa: SLF001
    mock_client_instance.get_document = AsyncMock(return_value=_harvest_with_catalog_events(["first", "second"]))
    mock_client_instance.save_document_if_revision_matches = AsyncMock(return_value={"_rev": "2-bbb"})

    updated = await store.update_harvest(
        "harvest-1",
        {
            "append_catalog_event": {
                "timestamp": "2024-01-01T00:00:03+00:00",
                "type": "CATALOG_PUSH_SUCCESS",
                "message": "third",
            }
        },
    )

    assert [event.message for event in updated.catalog_events] == ["first", "second", "third"]


@pytest.mark.asyncio
async def test_update_harvest_without_catalog_event_leaves_over_maximum_list(
    store: CouchDB,
    mock_client_instance: MagicMock,
) -> None:
    """A status-only update does not trim a catalog-event list that is already over the cap."""
    store._config.max_catalog_event_log_size = 1  # noqa: SLF001
    mock_client_instance.get_document = AsyncMock(return_value=_harvest_with_catalog_events(["first", "second"]))
    mock_client_instance.save_document_if_revision_matches = AsyncMock(return_value={"_rev": "2-bbb"})

    updated = await store.update_harvest("harvest-1", {"status": HarvestStatus.RUNNING})

    assert [event.message for event in updated.catalog_events] == ["first", "second"]


@pytest.mark.asyncio
async def test_catalog_finalize_lock_exclusive_create_and_release(
    store: CouchDB,
    mock_client_instance: MagicMock,
) -> None:
    """Finalize claim is created exclusively and deleted by the holder on exit."""
    held: dict[str, str] = {}

    async def _create_exclusive(doc_id: str, data: dict) -> dict:
        held["holder"] = data["holder"]
        return {"_id": doc_id, **data}

    async def _get_document(_doc_id: str) -> dict:
        return {"holder": held["holder"], "rdi": "edal"}

    mock_client_instance.create_document_exclusive = AsyncMock(side_effect=_create_exclusive)
    mock_client_instance.delete_document = AsyncMock(return_value=True)
    mock_client_instance.get_document = AsyncMock(side_effect=_get_document)

    async with store.catalog_finalize_lock.acquire("edal", wait_timeout_s=1.0):
        mock_client_instance.create_document_exclusive.assert_awaited_once()
        doc_id = mock_client_instance.create_document_exclusive.await_args.args[0]
        assert doc_id.startswith("catalog_finalize_lock_")

    mock_client_instance.delete_document.assert_awaited_once_with(doc_id)


@pytest.mark.asyncio
async def test_catalog_finalize_lock_release_failure_does_not_mask_success(
    store: CouchDB,
    mock_client_instance: MagicMock,
) -> None:
    """A CouchDB error while releasing the claim must not fail a successful finalize."""
    mock_client_instance.create_document_exclusive = AsyncMock(return_value={"ok": True})
    mock_client_instance.get_document = AsyncMock(side_effect=RuntimeError("couch down"))
    mock_client_instance.delete_document = AsyncMock()

    async with store.catalog_finalize_lock.acquire("edal", wait_timeout_s=1.0):
        pass

    mock_client_instance.delete_document.assert_not_called()


@pytest.mark.asyncio
async def test_catalog_finalize_lock_release_failure_preserves_body_error(
    store: CouchDB,
    mock_client_instance: MagicMock,
) -> None:
    """A release error must not replace the exception raised inside the lock."""
    held: dict[str, str] = {}

    async def _create_exclusive(_doc_id: str, data: dict) -> dict:
        held["holder"] = data["holder"]
        return {"ok": True}

    async def _get_document(_doc_id: str) -> dict:
        return {"holder": held["holder"]}

    mock_client_instance.create_document_exclusive = AsyncMock(side_effect=_create_exclusive)
    mock_client_instance.get_document = AsyncMock(side_effect=_get_document)
    mock_client_instance.delete_document = AsyncMock(side_effect=RuntimeError("couch down"))

    with pytest.raises(ValueError, match="finalize failed"):
        async with store.catalog_finalize_lock.acquire("edal", wait_timeout_s=1.0):
            raise ValueError("finalize failed")


@pytest.mark.asyncio
async def test_catalog_finalize_lock_wait_timeout(
    store: CouchDB,
    mock_client_instance: MagicMock,
    config: CouchDBConfig,
) -> None:
    """Held non-stale claim times out as TimeoutError for transient mapping."""
    store.catalog_finalize_lock._config = config.model_copy(  # noqa: SLF001
        update={
            "catalog_finalize_lock_wait_timeout_s": 0.05,
            "catalog_finalize_lock_poll_delay_s": 0.01,
            "catalog_finalize_lock_ttl_s": 600.0,
        }
    )
    mock_client_instance.create_document_exclusive = AsyncMock(side_effect=DocumentConflictError("held"))
    mock_client_instance.get_document = AsyncMock(
        return_value={
            "holder": "other",
            "rdi": "edal",
            "acquired_at": datetime.now(UTC).isoformat(),
        }
    )

    with pytest.raises(TimeoutError, match="timed out"):
        async with store.catalog_finalize_lock.acquire("edal"):
            pass  # pragma: no cover
