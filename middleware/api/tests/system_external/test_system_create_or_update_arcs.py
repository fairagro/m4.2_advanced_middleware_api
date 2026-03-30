"""System tests for creating or updating ARCs."""

import hashlib
import http
import json
import os
import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from gitlab import Gitlab, GitlabError

pytestmark = [
    pytest.mark.filterwarnings(
        "ignore:gitlab_api configuration is deprecated; prefer git_repo instead\\.:DeprecationWarning:pydantic\\.main"
    ),
    pytest.mark.filterwarnings(
        "ignore:deprecated:DeprecationWarning:middleware\\.api\\.business_logic\\.business_logic_factory"
    ),
]


@pytest.mark.asyncio
@pytest.mark.system_external
@pytest.mark.usefixtures("worker_process")
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
    gitlab_api: Gitlab,
    config: dict[str, Any],
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

    _wait_for_gitlab_project(gitlab_api, config, json_info)


def _verify_gitlab_project(gitlab_api: Gitlab, config: dict[str, Any], json_info: dict[str, Any]) -> bool:
    """Verify that the project was created in GitLab and contains the expected file."""
    group_name = config["gitlab_api"]["group"].lower()
    group = gitlab_api.groups.get(group_name)
    arc_id = hashlib.sha256(f"{json_info['identifier']}:rdi-1".encode()).hexdigest()
    try:
        projects = group.projects.list(search=arc_id)
        if not projects:
            return False
        project = gitlab_api.projects.get(projects[0].id)
        project.files.get(file_path="isa.investigation.xlsx", ref="main")
        return True
    except GitlabError:
        return False


def _wait_for_gitlab_project(
    gitlab_api: Gitlab,
    config: dict[str, Any],
    json_info: dict[str, Any],
    timeout_seconds: int = 180,
    poll_interval_seconds: int = 2,
) -> None:
    """Poll GitLab until the ARC project and expected file are present."""
    timeout_seconds = int(os.getenv("SYSTEM_EXTERNAL_GITLAB_TIMEOUT", str(timeout_seconds)))
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if _verify_gitlab_project(gitlab_api, config, json_info):
            return
        time.sleep(poll_interval_seconds)

    pytest.fail(
        "GitLab side effect not observed within timeout: expected project and "
        "isa.investigation.xlsx file were not found. "
        "Ensure the sync worker path is active for system_external tests."
    )
