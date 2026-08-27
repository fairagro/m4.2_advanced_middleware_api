"""Configuration models for ARC store components."""

from collections.abc import Mapping, Sequence
from typing import Annotated

from pydantic import Field, field_validator

from middleware.api.arc_store.git_cli_settings import GitCliSettings


class GitRepoConfig(GitCliSettings):
    """Configuration for per-ARC Git CLI based ArcStore."""

    url: Annotated[str, Field(description="Base URL of the git server (e.g. https://gitlab.com)")]
    group: Annotated[str, Field(description="The group/namespace the ARC repos belong to")]
    rdi_gitlab_topics: Annotated[
        dict[str, str],
        Field(
            description=(
                "Map from middleware RDI name to GitLab project topic. When "
                "known_rdis is configured, must contain exactly one non-empty "
                "entry per known RDI (e.g. edal -> e!DAL)."
            ),
        ),
    ] = {}

    @staticmethod
    def validate_rdi_gitlab_topics_for_known_rdis(
        known_rdis: Sequence[str],
        rdi_gitlab_topics: Mapping[str, str],
    ) -> dict[str, str]:
        """Ensure GitLab topic mapping covers ``known_rdis`` exactly.

        Raises:
            ValueError: When mapping keys diverge from ``known_rdis`` or values are empty.
        """
        if not known_rdis:
            return dict(rdi_gitlab_topics)

        known_set = set(known_rdis)
        topic_keys = set(rdi_gitlab_topics)
        extra_keys = topic_keys - known_set
        if extra_keys:
            msg = f"rdi_gitlab_topics contains keys that are not in known_rdis: {sorted(extra_keys)}"
            raise ValueError(msg)

        missing_keys = known_set - topic_keys
        if missing_keys:
            msg = f"known_rdis entries missing from rdi_gitlab_topics: {sorted(missing_keys)}"
            raise ValueError(msg)

        validated: dict[str, str] = {}
        for rdi in known_rdis:
            topic = rdi_gitlab_topics[rdi].strip()
            if not topic:
                msg = f"rdi_gitlab_topics[{rdi!r}] must not be empty"
                raise ValueError(msg)
            validated[rdi] = topic
        return validated

    @field_validator("rdi_gitlab_topics")
    @classmethod
    def validate_rdi_gitlab_topics(cls, topics: Mapping[str, str]) -> dict[str, str]:
        """Ensure topic mapping keys and values are non-empty."""
        validated: dict[str, str] = {}
        for key, value in topics.items():
            rdi_key = key.strip()
            topic = value.strip()
            if not rdi_key or not topic:
                msg = "rdi_gitlab_topics entries must have non-empty keys and values"
                raise ValueError(msg)
            validated[rdi_key] = topic
        return validated

    @field_validator("url")
    @classmethod
    def validate_url_scheme(cls, value: str) -> str:
        """Ensure URL uses HTTP, HTTPS or FILE (for tests)."""
        return GitCliSettings.validate_git_url_scheme(value)
