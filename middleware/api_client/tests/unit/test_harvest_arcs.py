"""Unit tests for ApiClient.harvest_arcs (v3 API)."""

from __future__ import annotations

import http
import json

import httpx
import pytest
import respx
from arctrl import ARC, ArcInvestigation  # type: ignore[import-untyped]
from client_test_support import (
    ARC_RESPONSE,
    EXPECTED_ARC_UPLOADS,
    HARVEST_RESPONSE,
    arc_gen,
    rocrate_dict,
)

from middleware.api_client import ApiClient, ApiClientError, Config, HarvestErrorType, HarvestResult


@pytest.mark.asyncio
@respx.mock
async def test_harvest_arcs_success(client_config: Config) -> None:
    """harvest_arcs creates a harvest, submits all ARCs, then completes it."""
    completed_response = {**HARVEST_RESPONSE, "status": "COMPLETED", "completed_at": "2024-01-01T01:00:00Z"}
    respx.post(f"{client_config.api_url}v3/harvests").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=HARVEST_RESPONSE)
    )
    respx.post(f"{client_config.api_url}v3/harvests/harvest-456/arcs").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=ARC_RESPONSE)
    )
    respx.post(f"{client_config.api_url}v3/harvests/harvest-456/complete").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=completed_response)
    )

    arcs = arc_gen(rocrate_dict("arc-1"), rocrate_dict("arc-2"), rocrate_dict("arc-3"))
    async with ApiClient(client_config) as client:
        result = await client.harvest_arcs("test-rdi", arcs, expected_datasets=3)

    assert isinstance(result, HarvestResult)
    assert result.status == "COMPLETED"


@pytest.mark.asyncio
@respx.mock
async def test_harvest_arcs_success_with_parallelism(client_config: Config) -> None:
    """harvest_arcs supports bounded parallel uploads via config.max_concurrency."""
    client_config.max_concurrency = 2

    completed_response = {**HARVEST_RESPONSE, "status": "COMPLETED", "completed_at": "2024-01-01T01:00:00Z"}
    respx.post(f"{client_config.api_url}v3/harvests").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=HARVEST_RESPONSE)
    )
    route_submit = respx.post(f"{client_config.api_url}v3/harvests/harvest-456/arcs").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=ARC_RESPONSE)
    )
    respx.post(f"{client_config.api_url}v3/harvests/harvest-456/complete").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=completed_response)
    )

    arcs = arc_gen(rocrate_dict("arc-1"), rocrate_dict("arc-2"), rocrate_dict("arc-3"))
    async with ApiClient(client_config) as client:
        result = await client.harvest_arcs("test-rdi", arcs)

    assert isinstance(result, HarvestResult)
    assert route_submit.call_count == EXPECTED_ARC_UPLOADS


@pytest.mark.asyncio
@respx.mock
async def test_harvest_arcs_uses_config_default_concurrency(client_config: Config) -> None:
    """harvest_arcs uses config.max_concurrency when no override is passed."""
    client_config.max_concurrency = 2

    completed_response = {**HARVEST_RESPONSE, "status": "COMPLETED", "completed_at": "2024-01-01T01:00:00Z"}
    respx.post(f"{client_config.api_url}v3/harvests").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=HARVEST_RESPONSE)
    )
    route_submit = respx.post(f"{client_config.api_url}v3/harvests/harvest-456/arcs").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=ARC_RESPONSE)
    )
    respx.post(f"{client_config.api_url}v3/harvests/harvest-456/complete").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=completed_response)
    )

    arcs = arc_gen(rocrate_dict("arc-1"), rocrate_dict("arc-2"), rocrate_dict("arc-3"))
    async with ApiClient(client_config) as client:
        result = await client.harvest_arcs("test-rdi", arcs)

    assert isinstance(result, HarvestResult)
    assert route_submit.call_count == EXPECTED_ARC_UPLOADS


@pytest.mark.asyncio
@respx.mock
async def test_harvest_arcs_empty_generator(client_config: Config) -> None:
    """harvest_arcs with an empty generator creates and immediately completes the harvest."""
    completed_response = {**HARVEST_RESPONSE, "status": "COMPLETED", "completed_at": "2024-01-01T01:00:00Z"}
    respx.post(f"{client_config.api_url}v3/harvests").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=HARVEST_RESPONSE)
    )
    respx.post(f"{client_config.api_url}v3/harvests/harvest-456/complete").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=completed_response)
    )

    async with ApiClient(client_config) as client:
        result = await client.harvest_arcs("test-rdi", arc_gen())

    assert isinstance(result, HarvestResult)
    assert result.status == "COMPLETED"


@pytest.mark.asyncio
@respx.mock
async def test_harvest_arcs_continues_on_item_error(client_config: Config) -> None:
    """harvest_arcs skips item-level errors and completes harvest."""
    respx.post(f"{client_config.api_url}v3/harvests").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=HARVEST_RESPONSE)
    )
    route_submit = respx.post(f"{client_config.api_url}v3/harvests/harvest-456/arcs").mock(
        side_effect=[
            httpx.Response(http.HTTPStatus.BAD_REQUEST, text="invalid arc"),
            httpx.Response(http.HTTPStatus.OK, json=ARC_RESPONSE),
            httpx.Response(http.HTTPStatus.OK, json=ARC_RESPONSE),
        ]
    )
    cancel_route = respx.delete(f"{client_config.api_url}v3/harvests/harvest-456").mock(
        return_value=httpx.Response(http.HTTPStatus.NO_CONTENT)
    )
    completed_response = {**HARVEST_RESPONSE, "status": "COMPLETED", "completed_at": "2024-01-01T01:00:00Z"}
    complete_route = respx.post(f"{client_config.api_url}v3/harvests/harvest-456/complete").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=completed_response)
    )

    async with ApiClient(client_config) as client:
        arcs = arc_gen(rocrate_dict("arc-1"), rocrate_dict("arc-2"), rocrate_dict("arc-3"))
        result = await client.harvest_arcs("test-rdi", arcs)

    assert isinstance(result, HarvestResult)
    assert route_submit.call_count == EXPECTED_ARC_UPLOADS
    assert complete_route.called
    assert not cancel_route.called
    assert len(result.errors) == 1
    assert result.errors[0].error_type == HarvestErrorType.SUBMISSION_FAILED
    assert result.errors[0].arc_id == "arc-1"
    assert "HTTP error 400" in result.errors[0].message


@pytest.mark.asyncio
@respx.mock
async def test_harvest_arcs_cancels_on_catastrophic_error(client_config: Config) -> None:
    """harvest_arcs marks the harvest as failed on catastrophic submission errors.

    409 Conflict (harvest in wrong state) is catastrophic → the harvest is
    immediately aborted and marked as failed.  HTTP 500 is *not* catastrophic;
    see test_harvest_arcs_500_is_submission_failed for that behaviour.
    """
    failed_response = {**HARVEST_RESPONSE, "status": "FAILED"}
    respx.post(f"{client_config.api_url}v3/harvests").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=HARVEST_RESPONSE)
    )
    respx.post(f"{client_config.api_url}v3/harvests/harvest-456/arcs").mock(
        return_value=httpx.Response(http.HTTPStatus.CONFLICT, text="harvest already closed")
    )
    fail_route = respx.patch(f"{client_config.api_url}v3/harvests/harvest-456").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=failed_response)
    )

    async with ApiClient(client_config) as client:
        with pytest.raises(ApiClientError, match="HTTP error 409"):
            await client.harvest_arcs("test-rdi", arc_gen(rocrate_dict("arc-1")))

    assert fail_route.called


@pytest.mark.asyncio
@respx.mock
async def test_harvest_arcs_skips_duplicate_identifier(client_config: Config) -> None:
    """harvest_arcs skips a duplicate ARC and completes the harvest successfully.

    When the same RO-Crate identifier appears twice in the input, the second
    occurrence is counted as a failed submission and the harvest continues.
    This prevents a single client-side data error from aborting the whole harvest.
    """
    arc_a = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [{"@id": "./", "@type": "Dataset", "identifier": "duplicate-arc", "name": "ARC A"}],
    }
    arc_b = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [{"@id": "./", "@type": "Dataset", "identifier": "duplicate-arc", "name": "ARC B"}],
    }
    completed_response = {**HARVEST_RESPONSE, "status": "COMPLETED", "completed_at": "2024-01-01T01:00:00Z"}
    respx.post(f"{client_config.api_url}v3/harvests").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=HARVEST_RESPONSE)
    )
    # Only the first ARC is submitted; the duplicate is skipped client-side.
    arc_route = respx.post(f"{client_config.api_url}v3/harvests/harvest-456/arcs").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=ARC_RESPONSE)
    )
    complete_route = respx.post(f"{client_config.api_url}v3/harvests/harvest-456/complete").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=completed_response)
    )

    async with ApiClient(client_config) as client:
        result = await client.harvest_arcs("test-rdi", arc_gen(arc_a, arc_b))

    assert result.status == "COMPLETED"
    assert arc_route.call_count == 1  # duplicate was skipped, not submitted
    assert complete_route.called
    assert len(result.errors) == 1
    assert result.errors[0].error_type == HarvestErrorType.DUPLICATE
    assert result.errors[0].arc_id == "duplicate-arc"
    assert "duplicate-arc" in result.errors[0].message


@pytest.mark.asyncio
@respx.mock
async def test_harvest_arcs_with_json_string(client_config: Config) -> None:
    """harvest_arcs supports JSON strings in async generator."""
    completed_response = {**HARVEST_RESPONSE, "status": "COMPLETED", "completed_at": "2024-01-01T01:00:00Z"}
    respx.post(f"{client_config.api_url}v3/harvests").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=HARVEST_RESPONSE)
    )
    respx.post(f"{client_config.api_url}v3/harvests/harvest-456/arcs").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=ARC_RESPONSE)
    )
    respx.post(f"{client_config.api_url}v3/harvests/harvest-456/complete").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=completed_response)
    )

    arcs = arc_gen(
        json.dumps(rocrate_dict("arc-1-string")),
        rocrate_dict("arc-2-dict"),
        ARC.from_arc_investigation(ArcInvestigation.create(identifier="test", title="Test")),
    )
    async with ApiClient(client_config) as client:
        result = await client.harvest_arcs("test-rdi", arcs, expected_datasets=3)

    assert isinstance(result, HarvestResult)
    assert result.status == "COMPLETED"


@pytest.mark.asyncio
@respx.mock
async def test_harvest_arcs_with_invalid_json_string(client_config: Config) -> None:
    """harvest_arcs raises ApiClientError when JSON string is invalid."""
    failed_response = {**HARVEST_RESPONSE, "status": "FAILED"}
    respx.post(f"{client_config.api_url}v3/harvests").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=HARVEST_RESPONSE)
    )
    respx.patch(f"{client_config.api_url}v3/harvests/harvest-456").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=failed_response)
    )

    async with ApiClient(client_config) as client:
        arcs = arc_gen('{"id": "arc-1"')  # Single invalid JSON string
        with pytest.raises(ApiClientError, match="Invalid JSON string provided for ARC"):
            await client.harvest_arcs("test-rdi", arcs)


@pytest.mark.asyncio
@respx.mock
async def test_harvest_arcs_cancel_failure_does_not_mask_original_error(client_config: Config) -> None:
    """If fail_harvest itself raises, the original submission error is still propagated."""
    respx.post(f"{client_config.api_url}v3/harvests").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=HARVEST_RESPONSE)
    )
    # 409 is catastrophic → triggers fail_harvest; 500 is NOT (see dedicated test).
    respx.post(f"{client_config.api_url}v3/harvests/harvest-456/arcs").mock(
        return_value=httpx.Response(http.HTTPStatus.CONFLICT, text="harvest already closed")
    )
    # Also make the fail call fail
    respx.patch(f"{client_config.api_url}v3/harvests/harvest-456").mock(
        return_value=httpx.Response(http.HTTPStatus.INTERNAL_SERVER_ERROR, text="fail error")
    )

    async with ApiClient(client_config) as client:
        with pytest.raises(ApiClientError, match="HTTP error 409"):
            await client.harvest_arcs("test-rdi", arc_gen(rocrate_dict("arc-1")))


@pytest.mark.asyncio
@respx.mock
async def test_harvest_arcs_all_exceptions_retrieved_when_multiple_tasks_catastrophic(
    client_config: Config,
) -> None:
    """All task exceptions are retrieved when multiple tasks fail catastrophically.

    Regression test for the "Task exception was never retrieved" asyncio warning
    (confirmed in production: Task-1149, HTTP 500 for harvest arc submission).

    Root cause: the old `_process_completed_arc_tasks` returned early after the
    first catastrophic error, leaving the remaining done tasks' exceptions
    unretrieved. asyncio then emitted a RuntimeWarning.

    With max_concurrency=10 and 3 ARCs, all three tasks land in the same done
    batch during the final drain (asyncio.wait). The early-return bug would leave
    the 2nd and 3rd exceptions unretrieved. This test is run with
    -W error::RuntimeWarning (see pyproject.toml) so any unretrieved exception
    would immediately fail the test.

    Note: 409 Conflict is used here because it is catastrophic (abort harvest).
    HTTP 500 is *not* catastrophic since this fix — see
    test_harvest_arcs_500_is_submission_failed for the non-catastrophic path.
    The asyncio-warning fix (no early return in _process_completed_arc_tasks)
    applies to both paths.
    """
    respx.post(f"{client_config.api_url}v3/harvests").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=HARVEST_RESPONSE)
    )
    respx.post(f"{client_config.api_url}v3/harvests/harvest-456/arcs").mock(
        return_value=httpx.Response(http.HTTPStatus.CONFLICT, text="harvest already closed")
    )
    fail_route = respx.patch(f"{client_config.api_url}v3/harvests/harvest-456").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json={**HARVEST_RESPONSE, "status": "FAILED"})
    )

    # 3 ARCs all returning 409 (catastrophic). With max_concurrency=10, no
    # intermediate wait fires — all three tasks accumulate in pending_tasks and
    # are drained together. If _process_completed_arc_tasks returned early after
    # the first catastrophic error, the remaining two exceptions would be
    # unretrieved → RuntimeWarning (promoted to error by -W error).
    async with ApiClient(client_config) as client:
        with pytest.raises(ApiClientError, match="HTTP error 409"):
            await client.harvest_arcs(
                "test-rdi",
                arc_gen(rocrate_dict("arc-1"), rocrate_dict("arc-2"), rocrate_dict("arc-3")),
            )

    assert fail_route.called


@pytest.mark.asyncio
@respx.mock
async def test_harvest_arcs_500_is_submission_failed(client_config: Config) -> None:
    """HTTP 5xx from ARC submission yields SUBMISSION_FAILED; the harvest continues.

    All 5xx responses are treated as transient: a server error on one ARC does
    not mean the next ARC will fail too.  Only auth/state errors (401, 403, 404,
    409) are truly catastrophic and abort the harvest.
    """
    completed_response = {**HARVEST_RESPONSE, "status": "COMPLETED", "completed_at": "2024-01-01T01:00:00Z"}
    respx.post(f"{client_config.api_url}v3/harvests").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=HARVEST_RESPONSE)
    )
    # arc-1: 500, arc-2: success, arc-3: 500 → 2 SUBMISSION_FAILED errors
    respx.post(f"{client_config.api_url}v3/harvests/harvest-456/arcs").mock(
        side_effect=[
            httpx.Response(http.HTTPStatus.INTERNAL_SERVER_ERROR, text="processing error"),
            httpx.Response(http.HTTPStatus.OK, json=ARC_RESPONSE),
            httpx.Response(http.HTTPStatus.INTERNAL_SERVER_ERROR, text="processing error"),
        ]
    )
    fail_route = respx.patch(f"{client_config.api_url}v3/harvests/harvest-456").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json={**HARVEST_RESPONSE, "status": "FAILED"})
    )
    complete_route = respx.post(f"{client_config.api_url}v3/harvests/harvest-456/complete").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=completed_response)
    )

    async with ApiClient(client_config) as client:
        result = await client.harvest_arcs(
            "test-rdi",
            arc_gen(rocrate_dict("arc-1"), rocrate_dict("arc-2"), rocrate_dict("arc-3")),
        )

    assert complete_route.called
    assert not fail_route.called
    assert len(result.errors) == 2  # noqa: PLR2004
    assert all(e.error_type == HarvestErrorType.SUBMISSION_FAILED for e in result.errors)


@pytest.mark.asyncio
@respx.mock
async def test_harvest_arcs_502_is_submission_failed(client_config: Config) -> None:
    """Exhausted 502 retries on one ARC yield SUBMISSION_FAILED; harvest continues.

    ARC POSTs are retried on transient gateway errors. After retries are
    exhausted the failed ARC is recorded as SUBMISSION_FAILED rather than
    aborting; a later ARC may still succeed.
    """
    client_config.retry_backoff_factor = 0.01
    client_config.max_retries = 2
    client_config.max_concurrency = 1  # sequential so side_effect order is deterministic
    completed_response = {**HARVEST_RESPONSE, "status": "COMPLETED", "completed_at": "2024-01-01T01:00:00Z"}
    respx.post(f"{client_config.api_url}v3/harvests").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=HARVEST_RESPONSE)
    )
    # arc-1: exhaust retries on 502, arc-2: success
    exhausted_attempts = client_config.max_retries + 1
    respx.post(f"{client_config.api_url}v3/harvests/harvest-456/arcs").mock(
        side_effect=[
            *[httpx.Response(http.HTTPStatus.BAD_GATEWAY, text="gateway error") for _ in range(exhausted_attempts)],
            httpx.Response(http.HTTPStatus.OK, json=ARC_RESPONSE),
        ]
    )
    fail_route = respx.patch(f"{client_config.api_url}v3/harvests/harvest-456").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json={**HARVEST_RESPONSE, "status": "FAILED"})
    )
    complete_route = respx.post(f"{client_config.api_url}v3/harvests/harvest-456/complete").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=completed_response)
    )

    async with ApiClient(client_config) as client:
        result = await client.harvest_arcs("test-rdi", arc_gen(rocrate_dict("arc-1"), rocrate_dict("arc-2")))

    assert complete_route.called
    assert not fail_route.called
    assert len(result.errors) == 1
    assert result.errors[0].error_type == HarvestErrorType.SUBMISSION_FAILED
    assert "502" in result.errors[0].message
