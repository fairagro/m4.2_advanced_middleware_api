# Tasks

## 1. Config

- [x] 1.1 Add nested API rate-limiting config (enabled flag, harvest-create/arc-submit per-minute ints, Retry-After
      bound) with issue defaults and ConfigWrapper-friendly fields
- [x] 1.2 Wire the nested model into root `Config` (`extra="forbid"` intact) and document keys for operators (dev config
      / README snippet as appropriate)

## 2. Middleware

- [x] 2.1 Implement process-local per-client limiter (in-memory; key = CN or `anonymous`; classes harvest-create vs
      arc-submit)
- [x] 2.2 Match only the four scoped POST paths; return `429` + `Retry-After` without running route handlers when over
      limit
- [x] 2.3 Register middleware in `fastapi_app` when enabled; prefer ordering before admission control

## 3. Tests & docs mapping

- [x] 3.1 Unit tests: under limit allowed; over limit `429` + `Retry-After`; disabled = no limiter `429`; anonymous
      shared key; class defaults / non-positive unlimited
- [x] 3.2 Update Spec-to-Code Mapping in `AGENTS.md` for `openspec/specs/rate-limiting/` (and design note if added at
      archive time)
- [x] 3.3 Run focused `uv run pytest` on new/affected unit tests and `ruff format/check` on touched files
