"""Integration tests for creating or updating ARCs."""

from pathlib import Path
from fastapi.testclient import TestClient
from gitlab import Gitlab
import pytest
import json


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "json_info", [
        {
            "file_name": "minimal.json",
            "identifier": "Test"
        },
        {
            "file_name": "sample.json",
            "identifier": "AthalianaColdStress"
        }
    ]
)
async def test_create_arcs(
        client: TestClient,
        cert: str,
        gitlab_api: Gitlab,
        config: dict,
        json_info: dict):
    """Test creating ARCs via the /v1/arcs endpoint."""
    cert_with_linebreaks = cert.replace("\\n", "\n")

    headers = {
        "X-Client-Cert": cert_with_linebreaks,
        "content-type": "application/ro-crate+json"
    }
    arc_json_path = (Path(__file__).parent.parent.parent /
                     "ro_crates" / json_info["file_name"])
    with arc_json_path.open("r", encoding="utf-8") as f:
        body = [json.load(f)]

    response = client.post("/v1/arcs", headers=headers, json=body)

    assert response.status_code == 201 # nosec
    body = response.json()
    assert body["client_id"] == "TestClient" # nosec

    # check that we have a project/repo that contains the isa.investigation.xlsx file
    group_name = config["gitlab_api"]["group"].lower()
    group = gitlab_api.groups.get(group_name)
    project_light = group.projects.list(search=json_info["identifier"])[0]
    project = gitlab_api.projects.get(project_light.id)
    project.files.get(file_path='isa.investigation.xlsx', ref='main')
