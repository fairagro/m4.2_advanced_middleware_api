"""Fixtures and marks for system_local tests (Testcontainers, no remote secrets)."""

import pytest

# Directory-level mark so pre-push `-m "not system_local"` cannot miss new tests.
pytestmark = pytest.mark.system_local
