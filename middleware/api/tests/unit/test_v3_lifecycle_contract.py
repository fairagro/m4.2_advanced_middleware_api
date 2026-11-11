"""Contract smoke: production and offline expose the same MVP lifecycle surface."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from middleware.api.api.fastapi_app import Api
from middleware.api_local_offline.app import create_local_offline_app
from middleware.api_local_offline.config import LocalOfflineConfig
from middleware.api_v3 import MVP_LIFECYCLE_ROUTES
from middleware.api_v3.mount import (
    assert_mvp_lifecycle_routes,
    collect_route_methods,
    collect_route_response_models,
)
from middleware.shared.api_models.v3.models import ArcResponse, HarvestResponse, LivenessResponse


@pytest.mark.unit
def test_production_and_offline_share_mvp_lifecycle_routes(
    middleware_api: Api,
    tmp_path: Path,
) -> None:
    """Both apps expose the same MVP paths/methods and shared response models."""
    offline = create_local_offline_app(LocalOfflineConfig(output_root=tmp_path))

    assert_mvp_lifecycle_routes(middleware_api.app)
    assert_mvp_lifecycle_routes(offline)

    prod_methods = collect_route_methods(middleware_api.app)
    offline_methods = collect_route_methods(offline)
    for path, methods in MVP_LIFECYCLE_ROUTES:
        assert methods <= prod_methods[path]
        assert methods <= offline_methods[path]
        assert methods <= (prod_methods[path] & offline_methods[path])

    prod_models = collect_route_response_models(middleware_api.app)
    offline_models = collect_route_response_models(offline)
    for path, method, model in (
        ("/v3/harvests", "POST", HarvestResponse),
        ("/v3/arcs", "POST", ArcResponse),
        ("/v3/liveness", "GET", LivenessResponse),
    ):
        assert prod_models[(path, method)] is model
        assert offline_models[(path, method)] is model


@pytest.mark.unit
def test_contract_fails_when_offline_omits_lifecycle_path(tmp_path: Path) -> None:
    """assert_mvp_lifecycle_routes fails if a mounted app drops an MVP path."""
    offline = create_local_offline_app(LocalOfflineConfig(output_root=tmp_path))
    # Drop shared liveness by clearing included routers is hard; instead build a
    # bare app that only keeps /live and assert the helper raises.
    from fastapi import FastAPI

    bare = FastAPI()

    @bare.get("/live")
    def _live() -> dict[str, str]:
        return {"status": "ok"}

    with pytest.raises(AssertionError, match="MVP lifecycle routes incomplete"):
        assert_mvp_lifecycle_routes(bare)

    # Sanity: real offline app still serves GET /v3/liveness.
    transport_client = TestClient(offline)
    assert transport_client.get("/v3/liveness").status_code == 200
