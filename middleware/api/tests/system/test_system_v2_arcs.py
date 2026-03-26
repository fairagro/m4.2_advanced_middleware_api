"""System tests for v2 ARC endpoint: task-record persistence contract."""

import http
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from middleware.api.api.fastapi_app import Api

pytestmark = [
    pytest.mark.filterwarnings(
        "ignore:gitlab_api configuration is deprecated; prefer git_repo instead\\.:DeprecationWarning:pydantic\\.main"
    ),
    pytest.mark.filterwarnings(
        "ignore:deprecated:DeprecationWarning:middleware\\.api\\.business_logic\\.business_logic_factory"
    ),
]

_RO_CRATE = Path(__file__).parent.parent.parent.parent.parent / "ro_crates" / "minimal.json"


def _v2_headers(cert: str) -> dict[str, str]:
    return {
        "ssl-client-cert": cert.replace("\\n", "\n"),
        "ssl-client-verify": "SUCCESS",
        "content-type": "application/json",
    }


def _v2_body() -> dict[str, Any]:
    with _RO_CRATE.open("r", encoding="utf-8") as f:
        arc = json.load(f)
    return {"rdi": "rdi-1", "arc": arc}


@pytest.mark.system
def test_create_or_update_arc_v2_accepted(
    client: TestClient,
    middleware_api: Api,
    cert: str,
) -> None:
    """POST /v2/arcs returns 202 and status SUCCESS when task record is persisted."""
    doc_store = middleware_api.business_logic._doc_store  # noqa: SLF001

    with patch.object(doc_store, "save_task_record", new=AsyncMock()):
        response = client.post("/v2/arcs", headers=_v2_headers(cert), json=_v2_body())

    assert response.status_code == http.HTTPStatus.ACCEPTED
    data = response.json()
    assert "task_id" in data
    assert data["status"] == "SUCCESS"


@pytest.mark.system
def test_create_or_update_arc_v2_returns_500_on_task_write_failure(
    client: TestClient,
    middleware_api: Api,
    cert: str,
) -> None:
    """POST /v2/arcs must return 500 when the task-record write to CouchDB fails.

    Regression test for the silent-failure bug: before the fix, a timed-out or
    otherwise failed ``save_task_record`` call was silently swallowed and a
    202 was returned with a task_id that had no backing document.  The client
    would then poll /v2/tasks/{id} forever (all polls returning PENDING),
    effectively reverting to the old genuinely-asynchronous behaviour — even
    though the ARC was already fully stored.

    The correct contract is: 202 may only be sent when the task record has
    been durably persisted so that the very first GET /v2/tasks/{id} returns
    SUCCESS immediately.
    """
    doc_store = middleware_api.business_logic._doc_store  # noqa: SLF001

    with patch.object(
        doc_store,
        "save_task_record",
        new=AsyncMock(side_effect=TimeoutError("CouchDB write timed out")),
    ):
        response = client.post("/v2/arcs", headers=_v2_headers(cert), json=_v2_body())

    assert response.status_code == http.HTTPStatus.INTERNAL_SERVER_ERROR
