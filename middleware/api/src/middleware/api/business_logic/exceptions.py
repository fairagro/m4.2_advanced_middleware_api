"""Business logic exception hierarchy."""


class BusinessLogicError(Exception):
    """Base exception class for all business logic errors."""


class ResourceNotFoundError(BusinessLogicError):
    """Arises when a requested business resource does not exist."""


class AccessDeniedError(BusinessLogicError):
    """Arises when the caller is not authorized for a resource."""


class ConflictError(BusinessLogicError):
    """Arises when the request conflicts with the current resource state."""


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
