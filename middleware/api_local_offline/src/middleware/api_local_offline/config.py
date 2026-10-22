"""Configuration for the local offline Middleware stand-in."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, ClassVar

from pydantic import ConfigDict, Field, field_validator

from middleware.shared.config.config_base import ConfigBase

# Reject production stack keys if someone points the stand-in at a full API config.
_FORBIDDEN_TOP_LEVEL_KEYS = frozenset({
    "couchdb",
    "celery",
    "arc_store",
    "consolidated_store",
    "harvest",
    "health_checks",
    "rate_limiting",
    "known_rdis",
    "client_auth_oid",
    "max_concurrent_requests",
})


class LocalOfflineConfig(ConfigBase):
    """Stand-alone config for the local offline stand-in (no CouchDB / Celery / Git)."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    output_root: Annotated[
        Path,
        Field(description="Directory under which accepted ARCs are written (arctrl WriteAsync)."),
    ] = Path("/data/arcs")

    @field_validator("output_root", mode="before")
    @classmethod
    def _coerce_output_root(cls, value: object) -> object:
        if isinstance(value, str):
            return Path(value)
        return value

    @classmethod
    def from_data(cls, data: dict) -> LocalOfflineConfig:
        """Load config and reject production Middleware API config keys."""
        unknown_forbidden = sorted(_FORBIDDEN_TOP_LEVEL_KEYS.intersection(data))
        if unknown_forbidden:
            raise ValueError("local offline stand-in refuses production config keys: " + ", ".join(unknown_forbidden))
        return super().from_data(data)
