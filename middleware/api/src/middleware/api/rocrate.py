"""RO-Crate parsing helpers for business logic."""

from typing import Any

from pydantic import ValidationError

from middleware.api.business_logic.exceptions import InvalidJsonSemanticError
from middleware.shared.api_models.common.rocrate import RoCratePayload


def parse_rocrate(arc: RoCratePayload | dict[str, Any]) -> RoCratePayload:
    """Parse and validate a RO-Crate payload, mapping schema errors to domain errors.

    Lightweight structural validation only (``RoCratePayload`` / Pydantic). Does
    not call arctrl — that parse is deferred to the Celery worker (see
    ``arc-manager`` spec).
    """
    if isinstance(arc, RoCratePayload):
        return arc
    try:
        return RoCratePayload.model_validate(arc)
    except ValidationError as exc:
        message = _first_validation_message(exc)
        raise InvalidJsonSemanticError(message) from exc


def _first_validation_message(exc: ValidationError) -> str:
    for error in exc.errors():
        msg = error.get("msg")
        if isinstance(msg, str) and msg:
            return msg
    return "RO-Crate JSON is invalid"
