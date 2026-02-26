"""Configuration models for worker-related components."""

import logging
from typing import Annotated, Any

from pydantic import BaseModel, Field, SecretStr, field_validator


class CeleryConfig(BaseModel):
    """Configuration for Celery worker."""

    broker_url: Annotated[
        SecretStr,
        Field(description="RabbitMQ broker URL"),
    ]
    result_backend: Annotated[
        SecretStr | None,
        Field(description="[DEPRECATED] Backend URL for results", deprecated=True),
    ] = None
    task_rate_limit: Annotated[str | None, Field(description="Rate limit for tasks (e.g. '10/m')")] = None
    retry_backoff: Annotated[bool, Field(description="Whether to use exponential backoff for retries")] = True
    retry_backoff_max: Annotated[int, Field(description="Max backoff time in seconds")] = 3600
    max_retries: Annotated[int, Field(description="Max number of retries for transient errors")] = 120

    @field_validator("result_backend", mode="before")
    @classmethod
    def warn_result_backend_deprecated(cls, v: Any) -> Any:
        """Warn that result_backend is deprecated."""
        if v is None:
            return v
        logging.warning(
            "Configuration setting 'celery.result_backend' is deprecated. "
            "The result backend is now managed internally or no longer required."
        )
        return v
