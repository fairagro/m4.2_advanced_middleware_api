"""Integration tests for creating or updating ARCs."""

import hashlib
import http
import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from gitlab import Gitlab


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "json_info",
    [
        {"file_name": "minimal.json", "identifier": "Test"},
        {"file_name": "sample.json", "identifier": "AthalianaColdStressSugar"},
    ],
)
async def test_create_arcs(
    client: TestClient,
    cert: str,
    json_info: dict[str, Any],
) -> None:
    """Test creating ARCs via the /v1/arcs endpoint."""
    cert_with_linebreaks = cert.replace("\\n", "\n")

    headers = {
        "ssl-client-cert": cert_with_linebreaks,
        "ssl-client-verify": "SUCCESS",
        "content-type": "application/json",
    }
    arc_json_path = Path(__file__).parent.parent.parent.parent.parent / "ro_crates" / json_info["file_name"]
    with arc_json_path.open("r", encoding="utf-8") as f:
        body = {"rdi": "rdi-1", "arcs": [json.load(f)]}

    response = client.post("/v1/arcs", headers=headers, json=body)

    assert response.status_code == http.HTTPStatus.ACCEPTED  # nosec (202 for async processing)
    body = response.json()
    assert "task_id" in body  # nosec
    assert body["status"] == "processing"  # nosec

    # Note: In integration tests, we would need to poll /v1/tasks/{task_id} to verify completion
    # For now, we skip verification as it requires Celery worker to be running
    # _verify_gitlab_project(gitlab_api, config, json_info)


def _verify_gitlab_project(gitlab_api: Gitlab, config: dict[str, Any], json_info: dict[str, Any]) -> None:
    """Verify that the project was created in GitLab and contains the expected file."""
    # check that we have a project/repo that contains the isa.investigation.xlsx file
    group_name = config["gitlab_api"]["group"].lower()
    group = gitlab_api.groups.get(group_name)
    arc_id = hashlib.sha256(f"{json_info['identifier']}:rdi-1".encode()).hexdigest()
    project_light = group.projects.list(search=arc_id)[0]
    project = gitlab_api.projects.get(project_light.id)
    project.files.get(file_path="isa.investigation.xlsx", ref="main")
