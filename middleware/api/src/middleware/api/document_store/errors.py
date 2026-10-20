"""Document-store exception types (no client imports — safe for shared use)."""


class DocumentStoreError(Exception):
    """Base exception for document store errors."""


class DocumentStoreUnavailableError(DocumentStoreError):
    """Raised when the store cannot serve requests (missing DB / re-init failed).

    API maps this to HTTP 503. Distinct from document-not-found.
    """
