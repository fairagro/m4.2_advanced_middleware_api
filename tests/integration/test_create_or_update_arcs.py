from fastapi.testclient import TestClient
from gitlab import Gitlab
import pytest


@pytest.mark.asyncio
async def test_create_or_update_arcs(client: TestClient, cert: str, gitlab_api: Gitlab, config: dict):
    # Optional Base64 encodieren, falls dein Code das erwartet
    cert_with_linebreaks = cert.replace("\\n", "\n")

    headers = {
        "X-Client-Cert": cert_with_linebreaks,
        "content-type": "application/ro-crate+json"
    }
    body = [{
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [
            {
            "@id": "./",
            "@type": "Dataset",
            "additionalType": "Investigation",
            "identifier": "Test"
            },
            {
            "@id": "ro-crate-metadata.json",
            "@type": "CreativeWork",
            "conformsTo": { "@id": "https://w3id.org/ro/crate/1.1" },
            "about": { "@id": "./" }
            }
        ]
    }] 

    response = client.post("/v1/arcs", headers=headers, json=body)

    assert response.status_code == 200 # nosec
    body = response.json()
    assert body["client_id"] == "TestClient" # nosec
    
    # check that we have a project/repo that contains the isa.investigation.xlsx file
    group_name = config["gitlab_api"]["group"].lower()
    group = gitlab_api.groups.get(group_name)
    project_light = group.projects.list(search="Test")[0]
    project = gitlab_api.projects.get(project_light.id)
    project.files.get(file_path='isa.investigation.xlsx', ref='main')