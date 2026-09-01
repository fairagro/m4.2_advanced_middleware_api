"""Business logic exception hierarchy."""

from middleware.shared.security.url_redact import redact_url_userinfo


class BusinessLogicError(Exception):
    """Base exception class for all business logic errors."""

    def __str__(self) -> str:
        """Hide URL userinfo (e.g. oauth2 tokens) in messages and events."""
        return redact_url_userinfo(super().__str__())


class ResourceNotFoundError(BusinessLogicError):
    """Arises when a requested business resource does not exist."""


class AccessDeniedError(BusinessLogicError):
    """Arises when the caller is not authorized for a resource."""


class ConflictError(BusinessLogicError):
    """Arises when the request conflicts with the current resource state."""


class DuplicateArcInHarvestError(ConflictError):
    """Arises when the same ARC is submitted more than once within a harvest run."""


class InvalidRequestError(BusinessLogicError):
    """Arises when request parameters or headers are invalid for this operation.

    For example, an empty ``Idempotency-Key`` or a keyed create without an
    authenticated client. Distinct from :class:`InvalidJsonSemanticError`, which
    covers ARC JSON that is syntactically valid but semantically incorrect.
    """


class InvalidJsonSemanticError(BusinessLogicError):
    """Arises when the ARC JSON syntax is valid but semantically incorrect.

    For example, missing required fields or invalid values.
    """


class SetupError(BusinessLogicError):
    """Arises when the business logic setup fails."""


class TransientError(BusinessLogicError):
    """Arises when a transient error occurs that may be resolved by retrying.

    Examples: Server unreachable, maintenance mode, temporary network issues.
    """
