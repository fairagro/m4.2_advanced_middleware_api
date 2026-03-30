"""System tests for creating or updating ARCs."""

import copy
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


# ---------------------------------------------------------------------------
# Shared helpers for v3 harvest-based tests
# ---------------------------------------------------------------------------

_RO_CRATES_DIR = Path(__file__).parent.parent.parent.parent.parent / "ro_crates"

_DEFAULT_HEADERS = {
    "ssl-client-verify": "SUCCESS",
    "content-type": "application/json",
    "accept": "application/json",
}


def _harvest_headers(cert: str) -> dict[str, str]:
    """Build request headers that include the PEM client certificate."""
    return {**_DEFAULT_HEADERS, "ssl-client-cert": cert.replace("\\n", "\n")}


def _arc_for_identifier(identifier: str) -> dict[str, Any]:
    """Build a minimal RO-Crate dict with the given identifier."""
    minimal_path = _RO_CRATES_DIR / "minimal.json"
    with minimal_path.open("r", encoding="utf-8") as fh:
        arc: dict[str, Any] = json.load(fh)
    # Patch the root Dataset node's identifier in-place
    for node in arc.get("@graph", []):
        if node.get("@id") == "./" and node.get("@type") == "Dataset":
            node["identifier"] = identifier
            break
    return arc


def _submit_arc_via_harvest(
    client: TestClient,
    headers: dict[str, str],
    rdi: str,
    arc_data: dict[str, Any],
) -> dict[str, Any]:
    """Run the full v3 harvest flow for one ARC and return key result fields.

    1. POST /v3/harvests          → harvest_id
    2. POST /v3/harvests/{id}/arcs → arc_id, arc_status
    3. POST /v3/harvests/{id}/complete

    Returns a dict with keys ``harvest_id``, ``arc_id``, ``arc_status``.
    """
    # Step 1: create harvest
    harvest_resp = client.post(
        "/v3/harvests",
        headers=headers,
        json={"rdi": rdi},
    )
    assert harvest_resp.status_code == http.HTTPStatus.OK, (  # nosec
        f"create_harvest failed: {harvest_resp.text}"
    )
    harvest_id: str = harvest_resp.json()["harvest_id"]

    # Step 2: submit ARC
    arc_resp = client.post(
        f"/v3/harvests/{harvest_id}/arcs",
        headers=headers,
        json={"arc": arc_data},
    )
    assert arc_resp.status_code == http.HTTPStatus.OK, (  # nosec
        f"submit_arc_in_harvest failed: {arc_resp.text}"
    )
    arc_body = arc_resp.json()

    # Step 3: complete harvest
    complete_resp = client.post(
        f"/v3/harvests/{harvest_id}/complete",
        headers=headers,
    )
    assert complete_resp.status_code == http.HTTPStatus.OK, (  # nosec
        f"complete_harvest failed: {complete_resp.text}"
    )

    return {
        "harvest_id": harvest_id,
        "arc_id": arc_body["arc_id"],
        "arc_status": arc_body["status"],
    }


def _arc_id_for(identifier: str, rdi: str) -> str:
    """Return the SHA-256 arc_id that the middleware derives for an ARC."""
    return hashlib.sha256(f"{identifier}:{rdi}".encode()).hexdigest()


def _get_latest_commit_sha(
    gitlab_api: Gitlab,
    config: dict[str, Any],
    arc_id: str,
) -> str | None:
    """Return the latest commit SHA on *main* for the GitLab project of *arc_id*.

    Returns ``None`` when the project does not yet exist or has no commits.
    """
    group_name = config["gitlab_api"]["group"].lower()
    try:
        group = gitlab_api.groups.get(group_name)
        projects = group.projects.list(search=arc_id)
        if not projects:
            return None
        project = gitlab_api.projects.get(projects[0].id)
        commits = project.commits.list(ref_name="main", per_page=1, get_all=False)
        if not commits:
            return None
        return str(commits[0].id)
    except GitlabError:
        return None


def _wait_for_commit_change(
    gitlab_api: Gitlab,
    config: dict[str, Any],
    arc_id: str,
    original_sha: str,
    timeout_seconds: int = 180,
) -> None:
    """Poll until the latest commit SHA on *main* differs from *original_sha*."""
    timeout_seconds = int(os.getenv("SYSTEM_EXTERNAL_GITLAB_TIMEOUT", str(timeout_seconds)))
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        current = _get_latest_commit_sha(gitlab_api, config, arc_id)
        if current is not None and current != original_sha:
            return
        time.sleep(2)

    pytest.fail(
        f"Expected a new commit on arc project {arc_id!r} after update, "
        f"but the latest SHA remained {original_sha!r} for {timeout_seconds}s."
    )


def _assert_commit_unchanged(
    gitlab_api: Gitlab,
    config: dict[str, Any],
    arc_id: str,
    expected_sha: str,
    wait_seconds: int = 60,
) -> None:
    """Assert that no new commit appears for *arc_id* within *wait_seconds*.

    Fails immediately if the SHA changes, i.e. an unexpected git push occurred.
    """
    wait_seconds = int(os.getenv("SYSTEM_EXTERNAL_NOGIT_WAIT", str(wait_seconds)))
    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        current = _get_latest_commit_sha(gitlab_api, config, arc_id)
        if current is not None and current != expected_sha:
            pytest.fail(
                f"Expected NO new commit for unchanged arc {arc_id!r}, "
                f"but a new commit appeared: {current!r} (was {expected_sha!r})."
            )
        time.sleep(2)


# ---------------------------------------------------------------------------
# End-to-end tests – v3 harvest flow
# ---------------------------------------------------------------------------


@pytest.mark.system_external
@pytest.mark.usefixtures("worker_process")
def test_new_arc_created_in_gitlab_via_harvest(
    client: TestClient,
    cert: str,
    gitlab_api: Gitlab,
    config: dict[str, Any],
) -> None:
    """A brand-new ARC submitted via the harvest flow must appear as a GitLab project."""
    identifier = "test-e2e-new-arc"
    rdi = "rdi-1"
    arc_data = _arc_for_identifier(identifier)
    headers = _harvest_headers(cert)

    result = _submit_arc_via_harvest(client, headers, rdi, arc_data)

    assert result["arc_status"] == "created"  # nosec

    arc_id = _arc_id_for(identifier, rdi)
    _wait_for_gitlab_project(
        gitlab_api,
        config,
        {"identifier": identifier, "file_name": ""},
    )
    # Verify arc_id reported by API matches our expectation
    assert result["arc_id"] == arc_id  # nosec


@pytest.mark.system_external
@pytest.mark.usefixtures("worker_process")
def test_changed_arc_creates_new_commit_in_gitlab(
    client: TestClient,
    cert: str,
    gitlab_api: Gitlab,
    config: dict[str, Any],
) -> None:
    """Re-submitting an ARC with changed content must produce a new Git commit."""
    identifier = "test-e2e-update-arc"
    rdi = "rdi-1"
    arc_id = _arc_id_for(identifier, rdi)
    headers = _harvest_headers(cert)

    # --- first harvest: create ---
    arc_v1 = _arc_for_identifier(identifier)
    result_v1 = _submit_arc_via_harvest(client, headers, rdi, arc_v1)
    assert result_v1["arc_status"] == "created"  # nosec

    _wait_for_gitlab_project(gitlab_api, config, {"identifier": identifier, "file_name": ""})
    sha_a = _get_latest_commit_sha(gitlab_api, config, arc_id)
    assert sha_a is not None  # nosec

    # --- second harvest: update (add a title field) ---
    arc_v2 = copy.deepcopy(arc_v1)
    for node in arc_v2.get("@graph", []):
        if node.get("@id") == "./" and node.get("@type") == "Dataset":
            node["title"] = "Updated title for e2e test"
            break

    result_v2 = _submit_arc_via_harvest(client, headers, rdi, arc_v2)
    assert result_v2["arc_status"] == "updated"  # nosec

    _wait_for_commit_change(gitlab_api, config, arc_id, original_sha=sha_a)

    sha_b = _get_latest_commit_sha(gitlab_api, config, arc_id)
    assert sha_b != sha_a  # nosec


@pytest.mark.system_external
@pytest.mark.usefixtures("worker_process")
def test_unchanged_arc_does_not_trigger_git_push(
    client: TestClient,
    cert: str,
    gitlab_api: Gitlab,
    config: dict[str, Any],
) -> None:
    """Re-submitting an identical ARC must NOT create a new Git commit."""
    identifier = "test-e2e-unchanged-arc"
    rdi = "rdi-1"
    arc_id = _arc_id_for(identifier, rdi)
    headers = _harvest_headers(cert)
    arc_data = _arc_for_identifier(identifier)

    # --- first harvest: create ---
    _submit_arc_via_harvest(client, headers, rdi, arc_data)
    _wait_for_gitlab_project(gitlab_api, config, {"identifier": identifier, "file_name": ""})
    sha_a = _get_latest_commit_sha(gitlab_api, config, arc_id)
    assert sha_a is not None  # nosec

    # --- second harvest: same content, no changes ---
    _submit_arc_via_harvest(client, headers, rdi, copy.deepcopy(arc_data))

    # Assert that no new commit appears for 60 s (or SYSTEM_EXTERNAL_NOGIT_WAIT)
    _assert_commit_unchanged(gitlab_api, config, arc_id, expected_sha=sha_a)


@pytest.mark.system_external
@pytest.mark.usefixtures("worker_process")
def test_same_arc_different_rdis_creates_separate_gitlab_projects(
    client: TestClient,
    cert: str,
    gitlab_api: Gitlab,
    config: dict[str, Any],
) -> None:
    """The same ARC submitted under two RDIs must produce two independent GitLab projects."""
    identifier = "test-e2e-two-rdis"
    rdi_1 = "rdi-1"
    rdi_2 = "rdi-2"
    arc_data = _arc_for_identifier(identifier)
    headers = _harvest_headers(cert)

    # Submit under rdi-1
    result_1 = _submit_arc_via_harvest(client, headers, rdi_1, copy.deepcopy(arc_data))
    # Submit under rdi-2
    result_2 = _submit_arc_via_harvest(client, headers, rdi_2, copy.deepcopy(arc_data))

    arc_id_1 = _arc_id_for(identifier, rdi_1)
    arc_id_2 = _arc_id_for(identifier, rdi_2)

    # The derived arc_ids must differ because the RDI is part of the hash input
    assert arc_id_1 != arc_id_2  # nosec
    assert result_1["arc_id"] == arc_id_1  # nosec
    assert result_2["arc_id"] == arc_id_2  # nosec

    # Both projects must appear independently in GitLab
    _wait_for_gitlab_project(gitlab_api, config, {"identifier": identifier, "file_name": "", "_rdi": rdi_1})
    _wait_for_gitlab_project(gitlab_api, config, {"identifier": identifier, "file_name": "", "_rdi": rdi_2})
