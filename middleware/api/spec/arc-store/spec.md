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
- [ ] Keep the Git repository path (slug) equal to `arc_id` so clone URLs remain
      stable regardless of display metadata.
- [ ] When the remote backend is GitLab via `GitRepo`, set the project title from
      the parsed ARC's ``Identifier`` (stripped), matching the normalization used
      by ``calculate_arc_id``.
- [ ] When the remote backend is GitLab via `GitRepo`, set the project description
      from the RO-Crate root dataset `name` and `description` when present. Do
      not repeat `identifier`, `rdi`, or `arc_id` in the description — those are
      already visible as the project title, topic tag, and repository path
      respectively.
- [ ] When the remote backend is GitLab via `GitRepo`, set a project topic (tag)
      to the originating `rdi` name so operators can filter repositories by RDI
      (RDI allowlisting is enforced by the API; see `arc-upload/` and
      `harvest-arc-upload/`).
- [ ] When a GitLab project already exists for an `arc_id` (via `GitRepo`), update
      its title, description, and RDI topic on the next sync if they differ from
      the values derived from the current ARC payload.

## Edge Cases

Transient network error → raise retryable error; caller decides whether to retry.

Permanent backend error (auth failure, forbidden) → raise permanent error; no retry.

ARC identifier missing or malformed → raise permanent error before any Git operation.

RO-Crate root dataset has no `name` → pass `display_name=""`; the GitLab project
description omits the name line but may still include the RO-Crate `description`.

Unknown or disallowed `rdi` → rejected by the API before Git sync (see
`arc-upload/` and `harvest-arc-upload/`). The Git store only receives
already-validated `rdi` values.
