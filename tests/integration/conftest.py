from dotenv import load_dotenv
import os
from fastapi.testclient import TestClient
from gitlab import Gitlab
import pytest

from middleware_api.api import Api
from middleware_api.config import Config
from ..shared_fixtures import cert # noqa: F401


load_dotenv()

@pytest.fixture
def config():
    return {
        "gitlab_api": {
            "url": "https://datahub-dev.ipk-gatersleben.de",
            "group": "FAIRagro-advanced-middleware-integration-tests",
            "token": ""
        }
    }

@pytest.fixture
def gitlab_api(config):
    token = os.getenv("GITLAB_API_TOKEN")
    return Gitlab(
        config["gitlab_api"]["url"],
        private_token=token
    )

@pytest.fixture
def middleware_api(config):
    config_validated = Config.from_data(config)
    return Api(config_validated)

@pytest.fixture
def client(middleware_api):
    """TestClient-Fixture und sicheres Aufräumen der Dependency-Overrides."""
    with TestClient(middleware_api.app) as c:
        yield c
