# ARC Store

**Scope:** The `ArcStore` abstraction and its implementations. `ArcStore` is the
Git-backend persistence layer: it accepts a parsed ARC object and creates or
updates the corresponding Git repository. It knows nothing about Celery, CouchDB,
or HTTP — it is a pure Git storage interface.

The caller (see `arc-manager/`) is responsible for parsing the ARC from JSON,
recording CouchDB events, and handling retry logic.

## Requirements

- [ ] Accept a parsed ARC object and a unique ARC identifier; create the Git
      repository if it does not exist, or update it if it does.
- [ ] Raise a retryable error for transient failures (network timeouts, rate
      limits, temporary backend unavailability) so that callers can retry.
- [ ] Raise a permanent error for non-retryable failures (invalid credentials,
      missing permissions, corrupt ARC data).
- [ ] Support arbitrary Git servers — the backend must not be tied to GitLab
      specifically.

## Edge Cases

Transient network error → raise retryable error; caller decides whether to retry.

Permanent backend error (auth failure, forbidden) → raise permanent error; no retry.

ARC identifier missing or malformed → raise permanent error before any Git operation.
