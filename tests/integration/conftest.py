"""Integration tests configuration and fixtures."""

import os

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from gitlab import Gitlab, GitlabError

from middleware_api.api import Api
from middleware_api.config import Config

from ..shared_fixtures import cert  # noqa: F401, pylint: disable=unused-import

load_dotenv()


@pytest.fixture(scope="session")
def config():
    """Provide configuration for tests."""
    return {
        "gitlab_api": {
            "url": "https://datahub-dev.ipk-gatersleben.de",
            "group": "FAIRagro-advanced-middleware-integration-tests",
            "token": "",
        }
    }


@pytest.fixture(scope="session")
def gitlab_api(config):  # pylint: disable=redefined-outer-name
    """Provide a Gitlab API client for tests."""
    token = os.getenv("GITLAB_API_TOKEN")
    return Gitlab(config["gitlab_api"]["url"], private_token=token)


@pytest.fixture(scope="session")
def gitlab_group(config, gitlab_api):  # pylint: disable=redefined-outer-name
    """Provide the Gitlab group for tests."""
    group = gitlab_api.groups.get(config["gitlab_api"]["group"])
    return group


@pytest.fixture
def middleware_api(config):  # pylint: disable=redefined-outer-name
    """Provide the Middleware API instance for tests."""
    config_validated = Config.from_data(config)
    return Api(config_validated)


@pytest.fixture
def client(middleware_api):  # pylint: disable=redefined-outer-name
    """Provide a TestClient for the Middleware API."""
    with TestClient(middleware_api.app) as c:
        yield c


@pytest.fixture(scope="session", autouse=True)
def cleanup_gitlab_group(
    gitlab_group, gitlab_api
):  # pylint: disable=redefined-outer-name
    """Cleanup the Gitlab group before tests."""
    # delete all projects in the group
    for project in gitlab_group.projects.list(all=True):
        try:
            full_project = gitlab_api.projects.get(project.id)
            full_project.delete()
            print(f"Deleted test project: {project.name}")
        except GitlabError as e:
            print(f"Failed to delete project {project.name}: {e}")
