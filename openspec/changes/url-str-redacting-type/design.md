# UrlStr Redacting Type — Design

## Context

See `proposal.md` for motivation. Today `GitContextConfig.repo_url` is
`SecretStr` (fully opaque on `str()`), while producers such as
`authenticated_repo_url` and `get_repo_url(authenticated=True)` still return
plain `str`. Git stderr and exception text remain plain strings, so
`redact_url_userinfo` plus exception `__str__` hooks and the logging filter stay
necessary. `UrlStr` sits in `middleware.shared` (api and shared may use it;
shared must not depend on api).

## Goals / Non-Goals

**Goals:**

- Typed default-safe stringification for authenticated remotes (host/path visible).
- Migrate Git remote producers/holders to `UrlStr`; call `.unredacted()` only at
  Git invocation boundaries.
- Keep defense-in-depth regex redaction for free-form text (Git stderr, logs,
  CouchDB event messages).

**Non-Goals:**

- Replacing `SecretStr` for tokens/passwords.
- Removing the logging redaction filter or exception `__str__` redaction.
- Changing operator YAML / REST / CouchDB document schemas.
- Wrapping every possible string that might contain a URL (only values we own).

## Decisions

### 1. `UrlStr` API shaped like `SecretStr`, partial redaction

Implement a small immutable wrapper in `middleware.shared.security`:

- `__str__` / `__repr__` → `redact_url_userinfo(raw)`
- `unredacted() -> str` → raw URL (name preferred over `get_secret_value` to
  emphasize partial, not full, secrecy)
- Equality / hashing on the raw URL
- Optional Pydantic core schema so it can appear on models (same role as
  `SecretStr` on `GitContextConfig.repo_url`)

**Alternative considered:** Keep `SecretStr` for remotes — rejected because ops
lose host/path in logs. **Alternative:** Only regex at sinks — rejected as the
source of the ad-hoc call-site sprawl.

### 2. Return type of authentication helpers is `UrlStr`

- `GitCliSettings.authenticated_repo_url` → `UrlStr`
- `RemoteGitProvider.get_repo_url(..., authenticated=True)` → `UrlStr` (or
  `UrlStr | str` only if unauthenticated path stays `str`; prefer always
  `UrlStr` when authenticated flag is True)
- `ConsolidatedGitConfig.catalog_repo_url` → `UrlStr`
- `GitContextConfig.repo_url: UrlStr` replacing `SecretStr`

Config fields that store **non-authenticated** base URLs (`url`, `repo_url`
without token) remain `str` until authentication is applied.

### 3. Defense-in-depth layers stay

```text
UrlStr (owned values)
    +
redact_url_userinfo on free text (Git stderr, exceptions, logging, CouchDB events)
```

Do not delete existing sink redaction in this change unless a call site becomes
provably redundant and tests still cover the sink.

### 4. Principles / AGENTS

Extend Type Safety in `openspec/principles.md`: credential-bearing URLs use
`UrlStr`; tokens/passwords stay `SecretStr`. Add `url-str` to AGENTS
Spec-to-Code Mapping.

## Risks / Trade-offs

- [Git still embeds raw URL in stderr] → Keep regex redaction; document that
  `UrlStr` does not cover third-party exception text.
- [Callers forget `.unredacted()` and Git auth fails] → Type checkers + focused
  unit tests at clone/ls-remote/push boundaries; fail loud in tests.
- [Pydantic / serialization surprises] → Mirror SecretStr patterns for dump;
  never serialize unredacted into logs or API responses.
- [Wider return-type churn in tests] → Prefer updating helpers once; adjust
  asserts to compare `.unredacted()` or `str(url)`.

## Migration Plan

1. Land `UrlStr` + unit tests in shared.
2. Switch producers and `GitContextConfig`, then call sites that pass URLs to Git.
3. Update arc-store / business-logic tests for string forms.
4. Principles + AGENTS mapping.
5. No deploy-time migration; rollback is revert of the change.

## Open Questions

None — accessor name `unredacted()` and keeping sink redaction are fixed by the
proposal discussion.
