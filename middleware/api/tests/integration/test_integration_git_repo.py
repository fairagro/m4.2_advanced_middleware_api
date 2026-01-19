"""Integration tests for GitRepo backend."""

import hashlib
import http
import json
import shutil
import tempfile
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from cryptography import x509
from fastapi.testclient import TestClient
from git import Repo

from middleware.api.api import Api
from middleware.api.config import Config
from middleware.shared.config.config_wrapper import ConfigWrapper


@pytest.fixture
def git_server_root() -> Generator[Path, None, None]:
    """Create a temporary directory simulating a git server root."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def git_repo_cache_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for GitRepo cache."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def git_repo_config(git_server_root: Path, git_repo_cache_dir: Path, oid: x509.ObjectIdentifier) -> dict[str, Any]:
    """Provide configuration for GitRepo backend."""
    return {
        "log_level": "DEBUG",
        "known_rdis": ["rdi-1"],
        "client_auth_oid": oid.dotted_string,
        "require_client_cert": True,
        "git_repo": {
            "url": f"file://{git_server_root}",
            "group": "test-group",
            "branch": "main",
            "cache_dir": str(git_repo_cache_dir),
        },
        "celery": {
            "broker_url": "memory://",
            "result_backend": "cache+memory://",
        },
    }


@pytest.fixture
def api_client(git_repo_config: dict[str, Any]) -> Generator[TestClient, None, None]:
    """Provide a TestClient with GitRepo backend."""
    config_wrapper = ConfigWrapper.from_data(git_repo_config)
    unwrapped_config = config_wrapper.unwrap()
    assert isinstance(unwrapped_config, dict), "Config must be a dictionary"
    config = Config.from_data(unwrapped_config)
    api = Api(config)
    with TestClient(api.app) as c:
        yield c


@pytest.mark.asyncio
async def test_create_arc_via_git_repo(
    api_client: TestClient,
    git_server_root: Path,
    cert: str,
) -> None:
    """Test creating an ARC using the GitRepo backend."""
    # 1. Prepare Request
    cert_with_linebreaks = cert.replace("\\n", "\n")
    headers = {
        "ssl-client-cert": cert_with_linebreaks,
        "ssl-client-verify": "SUCCESS",
        "content-type": "application/json",
    }

    # Load minimal.json
    arc_json_path = Path("/workspaces/m4.2_advanced_middleware_api/ro_crates/minimal.json")
    with arc_json_path.open("r", encoding="utf-8") as f:
        json_content = json.load(f)

    # Wrap in API expected format
    body = {"rdi": "rdi-1", "arcs": [json_content]}

    # Calculate expected ARC ID for identifier "Test"
    arc_id = hashlib.sha256(b"Test:rdi-1").hexdigest()

    # 2. Pre-create the bare repo
    # Expected remote path: base / group / arc_id.git
    group_dir = git_server_root / "test-group"
    group_dir.mkdir(parents=True, exist_ok=True)
    repo_path = group_dir / f"{arc_id}.git"

    # Initialize bare repo
    Repo.init(repo_path, bare=True)

    # 3. Call API
    response = api_client.post("/v1/arcs", headers=headers, json=body)

    # Assert
    # API now returns 202 (Accepted) for async processing
    assert response.status_code == http.HTTPStatus.ACCEPTED, f"Response: {response.text}"
    response_data = response.json()
    assert "task_id" in response_data
    assert response_data["status"] == "processing"

    # Note: In integration tests, we would need to poll /v1/tasks/{task_id} and wait for completion
    # For now, we skip verification as it requires Celery worker to be running
    # _verify_repo_content(repo_path)


def _verify_repo_content(repo_path: Path) -> None:
    """Verify the content of the pushed repository."""
    with tempfile.TemporaryDirectory() as tmp_clone:
        Repo.clone_from(str(repo_path), tmp_clone, branch="main")

        # Check files exist
        cloned_path = Path(tmp_clone)

        # The ARC.Write() operation writes the ARC structure (isa.investigation.xlsx, etc.)
        # It does not necessarily preserve ro-crate-metadata.json at the root
        assert (cloned_path / "isa.investigation.xlsx").exists()
        assert (cloned_path / "studies").exists()
        assert (cloned_path / "assays").exists()
        assert (cloned_path / "workflows").exists()
        assert (cloned_path / "runs").exists()
