"""HTTP smoke tests for the local offline stand-in."""

from __future__ import annotations

import asyncio
import socket
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import uvicorn
from fastapi import FastAPI
from httpx import ASGITransport

from middleware.api_client import ApiClient
from middleware.api_client.config import Config as ApiClientConfig
from middleware.api_client.models import ArcResult, HarvestResult
from middleware.api_local_offline.app import create_local_offline_app
from middleware.api_local_offline.config import LocalOfflineConfig
from middleware.api_local_offline.filesystem_store import FilesystemArcStoreError

_MINIMAL_ARC = {
    "@context": "https://w3id.org/ro/crate/1.1/context",
    "@graph": [
        {
            "@id": "./",
            "@type": "Dataset",
            "additionalType": "Investigation",
            "identifier": "offline-smoke",
            "name": "Offline Smoke",
        }
    ],
}


@pytest.fixture
def offline_app(tmp_path: Path) -> tuple[FastAPI, Path]:
    config = LocalOfflineConfig(output_root=tmp_path)
    return create_local_offline_app(config), tmp_path


@pytest.mark.asyncio
async def test_live_and_harvest_lifecycle_writes_disk(offline_app: tuple[FastAPI, Path]) -> None:
    app, output_root = offline_app
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        live = await client.get("/live")
        assert live.status_code == 200
        assert live.json()["status"] == "ok"

        created = await client.post("/v3/harvests", json={"rdi": "publisso", "expected_datasets": 1})
        assert created.status_code == 200
        harvest = HarvestResult.model_validate(created.json())
        assert harvest.status.value == "RUNNING"

        submitted = await client.post(
            f"/v3/harvests/{harvest.harvest_id}/arcs",
            json={"arc": _MINIMAL_ARC},
        )
        assert submitted.status_code == 200
        arc_result = ArcResult.model_validate(submitted.json())
        assert arc_result.arc_id
        assert any(output_root.iterdir()), "ARC tree must exist before HTTP success returns"

        completed = await client.post(f"/v3/harvests/{harvest.harvest_id}/complete")
        assert completed.status_code == 200
        done = HarvestResult.model_validate(completed.json())
        assert done.status.value == "COMPLETED"


@pytest.mark.asyncio
async def test_disk_write_failure_is_server_error(
    offline_app: tuple[FastAPI, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    app, _output_root = offline_app
    store = app.state.filesystem_arc_store

    async def _boom(*_args: object, **_kwargs: object) -> bool:
        raise FilesystemArcStoreError("disk full")

    monkeypatch.setattr(store, "create_or_update", _boom)
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        created = await client.post("/v3/harvests", json={"rdi": "publisso"})
        harvest_id = created.json()["harvest_id"]
        submitted = await client.post(
            f"/v3/harvests/{harvest_id}/arcs",
            json={"arc": _MINIMAL_ARC},
        )
        assert submitted.status_code == 500


@pytest.mark.asyncio
async def test_api_client_harvest_arcs_against_stand_in(tmp_path: Path) -> None:
    """End-to-end: ApiClient.harvest_arcs against an in-process uvicorn stand-in."""
    config = LocalOfflineConfig(output_root=tmp_path)
    app = create_local_offline_app(config)

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    serve_task = asyncio.create_task(server.serve())
    try:
        for _ in range(50):
            if server.started:
                break
            await asyncio.sleep(0.05)
        assert server.started

        async def arcs() -> AsyncIterator[dict[str, Any]]:
            yield _MINIMAL_ARC

        client_cfg = ApiClientConfig(api_url=f"http://127.0.0.1:{port}")
        async with ApiClient(client_cfg) as api_client:
            result = await api_client.harvest_arcs("publisso", arcs(), expected_datasets=1)
        assert result.status.value == "COMPLETED"
        assert any(tmp_path.iterdir())
    finally:
        server.should_exit = True
        await serve_task
