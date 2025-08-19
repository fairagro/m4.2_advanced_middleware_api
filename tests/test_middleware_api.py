from fastapi.testclient import TestClient
from app.middleware_api import app

client = TestClient(app)


def test_create_or_update_arcs_success():
    # Valid ARC RO-Crate structure
    rocrate = [{
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [
            {
                "@id": "./",
                "@type": "Dataset",
                "additionalType": "Investigation",
                "identifier": "ARC-001"
            },
            {
                "@id": "ro-crate-metadata.json",
                "@type": "CreativeWork",
                "conformsTo": {"@id": "https://w3id.org/ro/crate/1.1"},
                "about": {"@id": "./"}
            }
        ]
    }]
    response = client.post(
        "/v1/arcs",
        headers={"content-type": "application/ro-crate+json",
                 "accept": "application/json"},
        json=rocrate
    )
    assert response.status_code == 201
    data = response.json()
    assert isinstance(data, list)
    assert data[0]["id"] == "ARC-001"
    assert data[0]["status"] == "created"
    assert "updated_at" in data[0]
    assert response.headers["Location"] == "/v1/arcs/ARC-001"


def test_create_or_update_arcs_missing_identifier():
    rocrate = [{
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [
            {
                "@id": "./",
                "@type": "Dataset",
                "additionalType": "Investigation",
                # Missing Identifier
            },
            {
                "@id": "ro-crate-metadata.json",
                "@type": "CreativeWork",
                "conformsTo": {"@id": "https://w3id.org/ro/crate/1.1"},
                "about": {"@id": "./"}
            }
        ]
    }]
    response = client.post(
        "/v1/arcs",
        headers={"content-type": "application/ro-crate+json",
                 "accept": "application/json"},
        json=rocrate
    )
    assert response.status_code == 422


def test_create_or_update_arcs_invalid_json():
    # Send invalid JSON (not a list)
    response = client.post(
        "/v1/arcs",
        headers={"content-type": "application/ro-crate+json",
                 "accept": "application/json"},
        data="not a json"  # type: ignore
    )
    assert response.status_code == 400


def test_create_or_update_arcs_json_no_array():
    # Send invalid JSON (not a list)
    response = client.post(
        "/v1/arcs",
        headers={"content-type": "application/ro-crate+json",
                 "accept": "application/json"},
        json="not an array"
    )
    assert response.status_code == 400


def test_create_or_update_arcs_unsupported_content_type():
    rocrate = [{
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [
            {
                "@id": "./",
                "@type": "Dataset",
                "additionalType": "Investigation",
                "identifier": "ARC-002"
            },
            {
                "@id": "ro-crate-metadata.json",
                "@type": "CreativeWork",
                "conformsTo": {"@id": "https://w3id.org/ro/crate/1.1"},
                "about": {"@id": "./"}
            }
        ]
    }]
    response = client.post(
        "/v1/arcs",
        headers={"content-type": "application/json",
                 "accept": "application/json"},
        json=rocrate
    )
    assert response.status_code == 415
    assert "Unsupported Media Type" in response.json()["detail"]


def test_create_or_update_arcs_unsupported_accept():
    rocrate = [{
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [
            {
                "@id": "./",
                "@type": "Dataset",
                "additionalType": "Investigation",
                "identifier": "ARC-003"
            },
            {
                "@id": "ro-crate-metadata.json",
                "@type": "CreativeWork",
                "conformsTo": {"@id": "https://w3id.org/ro/crate/1.1"},
                "about": {"@id": "./"}
            }
        ]
    }]
    response = client.post(
        "/v1/arcs",
        headers={"content-type": "application/ro-crate+json",
                 "accept": "application/xml"},
        json=rocrate
    )
    assert response.status_code == 406
    assert "Unsupprted Response Type" in response.json()["detail"]


def test_create_or_update_arcs_empty_list():
    response = client.post(
        "/v1/arcs",
        headers={"content-type": "application/ro-crate+json",
                 "accept": "application/json"},
        json=[]
    )
    assert response.status_code == 200
    assert response.json() == []
    assert response.headers["Location"] == ""


def test_create_or_update_arcs_multiple_arcs():
    rocrate = [
        {
            "@context": "https://w3id.org/ro/crate/1.1/context",
            "@graph": [
                {
                    "@id": "./",
                    "@type": "Dataset",
                    "additionalType": "Investigation",
                    "identifier": "ARC-004"
                },
                {
                    "@id": "ro-crate-metadata.json",
                    "@type": "CreativeWork",
                    "conformsTo": {"@id": "https://w3id.org/ro/crate/1.1"},
                    "about": {"@id": "./"}
                }
            ]
        },
        {
            "@context": "https://w3id.org/ro/crate/1.1/context",
            "@graph": [
                {
                    "@id": "./",
                    "@type": "Dataset",
                    "additionalType": "Investigation",
                    "identifier": "ARC-005"
                },
                {
                    "@id": "ro-crate-metadata.json",
                    "@type": "CreativeWork",
                    "conformsTo": {"@id": "https://w3id.org/ro/crate/1.1"},
                    "about": {"@id": "./"}
                }
            ]
        }
    ]
    response = client.post(
        "/v1/arcs",
        headers={"content-type": "application/ro-crate+json",
                 "accept": "application/json"},
        json=rocrate
    )
    assert response.status_code == 201
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["id"] == "ARC-004"
    assert data[1]["id"] == "ARC-005"
    assert response.headers["Location"] == "/v1/arcs/ARC-004"


def test_create_or_update_arcs_graph_missing():
    # Missing @graph key
    rocrate = [{
        "@context": "https://w3id.org/ro/crate/1.1/context"
        # No @graph
    }]
    response = client.post(
        "/v1/arcs",
        headers={"content-type": "application/ro-crate+json",
                 "accept": "application/json"},
        json=rocrate
    )
    assert response.status_code == 422


def test_create_or_update_arcs_context_missing():
    # Missing @context key
    rocrate = [{
        "@graph": [
            {
                "@id": "./",
                "@type": "Dataset",
                "additionalType": "Investigation",
                "identifier": "ARC-006"
            },
            {
                "@id": "ro-crate-metadata.json",
                "@type": "CreativeWork",
                "conformsTo": {"@id": "https://w3id.org/ro/crate/1.1"},
                "about": {"@id": "./"}
            }
        ]
    }]
    response = client.post(
        "/v1/arcs",
        headers={"content-type": "application/ro-crate+json",
                 "accept": "application/json"},
        json=rocrate
    )
    # Should fail if @context is required by ARC.from_rocrate_json_string
    assert response.status_code == 422


def test_create_or_update_arcs_dataset_missing():
    # @graph exists but no Dataset entry
    rocrate = [{
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [
            {
                "@id": "ro-crate-metadata.json",
                "@type": "CreativeWork",
                "about": {"@id": "./"}
            }
            # No Dataset
        ]
    }]
    response = client.post(
        "/v1/arcs",
        headers={"content-type": "application/ro-crate+json",
                 "accept": "application/json"},
        json=rocrate
    )
    assert response.status_code == 422


def test_create_or_update_arcs_non_list_payload():
    # Send a dict instead of a list
    rocrate = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [
            {
                "@id": "./",
                "@type": "Dataset",
                "additionalType": "Investigation",
                "identifier": "ARC-006"
            },
            {
                "@id": "ro-crate-metadata.json",
                "@type": "CreativeWork",
                "conformsTo": {"@id": "https://w3id.org/ro/crate/1.1"},
                "about": {"@id": "./"}
            }
        ]
    }
    response = client.post(
        "/v1/arcs",
        headers={"content-type": "application/ro-crate+json",
                 "accept": "application/json"},
        json=rocrate
    )
    # Should fail because the API expects a list
    assert response.status_code == 400
