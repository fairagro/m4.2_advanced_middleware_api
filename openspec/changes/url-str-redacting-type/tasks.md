# UrlStr Redacting Type — Tasks

## 1. Shared UrlStr type

- [x] 1.1 Add `UrlStr` in `middleware/shared/security` (`__str__`/`__repr__`
      redact via `redact_url_userinfo`, `unredacted()` returns raw; equality on
      raw)
- [x] 1.2 Export from `middleware.shared.security` and add unit tests for
      redacted vs unredacted forms
- [x] 1.3 Add Pydantic support so `UrlStr` can replace `SecretStr` on model
      fields (accept `str` / `UrlStr` on validate)

## 2. Arc-store migration

- [x] 2.1 Change `GitCliSettings.authenticated_repo_url` to return `UrlStr`;
      update `git_context_config` to store `UrlStr` on
      `GitContextConfig.repo_url`
- [x] 2.2 Change authenticated `RemoteGitProvider.get_repo_url` /
      `catalog_repo_url` to return `UrlStr`
- [x] 2.3 At Git CLI / GitPython call sites, pass `.unredacted()`; use
      `str(url)` (or leave as UrlStr) for logs/span attributes
- [x] 2.4 Update unit tests (`test_git_repo`, remote provider, consolidated
      git) for `UrlStr` return types

## 3. Docs and verification

- [x] 3.1 Extend `openspec/principles.md` Type Safety: credential-bearing URLs
      → `UrlStr`; tokens/passwords stay `SecretStr`
- [x] 3.2 Add `url-str` to AGENTS.md Spec-to-Code Mapping
- [x] 3.3 Run relevant unit tests and `ruff`/`mypy` on touched packages
