"""Optional live Docker arc-export smoke test (skipped unless opted in)."""

from __future__ import annotations

import os

import pytest

from middleware.arc_validation import validate_rocrate

# Minimal structurally empty RO-Crate — live test only asserts the Docker path runs.
# Real RDI fixtures live in consumer repos (harvester / SQL-to-ARC).
_MINIMAL_ROCRATE = """\
{
  "@context": "https://w3id.org/ro/crate/1.1/context",
  "@graph": [
    {
      "@id": "ro-crate-metadata.json",
      "@type": "CreativeWork",
      "about": {"@id": "./"},
      "conformsTo": {"@id": "https://w3id.org/ro/crate/1.1"}
    },
    {
      "@id": "./",
      "@type": "Dataset",
      "name": "fairagro-arc-validation-smoke"
    }
  ]
}
"""

_LIVE_ENV = "FAIRAGRO_ARC_VALIDATE_LIVE"


@pytest.mark.requires_docker
@pytest.mark.skipif(
    os.environ.get(_LIVE_ENV) != "1",
    reason=f"set {_LIVE_ENV}=1 to run live Docker arc-export",
)
def test_validate_rocrate_invokes_live_docker() -> None:
    """Opt-in: requires Docker + pull of the default arc-export image."""
    result = validate_rocrate(_MINIMAL_ROCRATE)
    # Either pass or fail with a structured result — must not raise.
    assert isinstance(result.ok, bool)
    assert isinstance(result.exit_code, int)
