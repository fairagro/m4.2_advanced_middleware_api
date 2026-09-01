# UrlStr Redacting Type — Proposal

## Why

Authenticated Git HTTPS remotes embed oauth2 tokens in the URL userinfo. Call-site
`redact_url_userinfo(...)` and exception `__str__` hooks grew ad hoc and are easy
to miss when a URL is interpolated into logs, traces, or CouchDB events. A typed
value (like Pydantic `SecretStr`, but only masking userinfo) makes the safe path
the default: `str(url)` is redacted; the raw credential URL requires an explicit
accessor.

## What Changes

- Add `UrlStr` in `middleware.shared.security`: `str()` / `repr` redact userinfo;
  `unredacted()` returns the full URL for Git CLI / GitPython only.
- Prefer `UrlStr` over `SecretStr` for **authenticated** remote URLs (so ops still
  see host and path); keep `SecretStr` for tokens and passwords.
- Migrate producers (`authenticated_repo_url`, `get_repo_url(authenticated=True)`,
  `GitContextConfig.repo_url`, catalog remote helpers) to return / store `UrlStr`.
- Keep `redact_url_userinfo` as defense-in-depth for free-form text (Git stderr,
  logging formatter, persisted harvest/ARC event messages) — `UrlStr` does not
  replace that layer.
- Document the pattern in principles / AGENTS mapping; no HTTP API or config YAML
  shape change for operators (**not BREAKING** for deploy configs).

## Capabilities

### New Capabilities

- `url-str`: Shared `UrlStr` type and contract for credential-bearing URLs
  (redacting stringification vs explicit `unredacted()`).

### Modified Capabilities

- `arc-store`: Authenticated Git remotes MUST be carried as `UrlStr` (or equivalent
  redacting type); plain `str` authenticated remotes MUST NOT be the default
  hand-off into logging/tracing surfaces.

## Impact

- `middleware/shared/security/` (new type + tests)
- `git_cli_settings.py`, `remote_git_provider.py`, `git_repo.py`,
  `consolidated_git.py` / config, related unit tests
- Exception / event redaction call sites may shrink where the value is already
  `UrlStr`, but regex redaction on exception text and logging remains required
- No change to CouchDB schemas, Celery payloads, or public REST contracts
