# Adopt Devinfra Wave A — Proposal

## Why

Shared Devinfra Wave A (AI review / agent stack) is extracted and closed upstream
([fairagro/m4.2_middleware_devinfra](https://github.com/fairagro/m4.2_middleware_devinfra)
issues #4–#6, #14–#16, plus [#32](https://github.com/fairagro/m4.2_middleware_devinfra/issues/32)
surface-bar split and [#35](https://github.com/fairagro/m4.2_middleware_devinfra/issues/35)
canonical arctrl skill). This repo still carries drifted local forks of the same
paths and lacks `scripts/ai` / `m42-ai`, `openspec/principles.global.md`, and
`docs/surface-quality-bar.global.md`. Issue
[#366](https://github.com/fairagro/m4.2_advanced_middleware_api/issues/366)
asks to adopt the shared stack without local drift on synced paths, as the
fleet pilot before sql_to_arc / harvester. Wave A prereqs on Devinfra are
**done** (2026-09-08); sync automation (#13) remains optional.

## What Changes

- Replace/align synced AI-stack paths with Devinfra `main` at a **pinned SHA**:
  policy, `docs/surface-quality-bar.global.md`, Bugbot/Copilot entries,
  `/review-fixer` + `/create-issue` + `/issue-fixer` skills/commands/prompts,
  thin fixer docs, first-party `.agents/skills/arctrl/`, vendor skills
  `{gh,docker,hadolint,uv}`, `scripts/ai/` / `m42-ai`,
  `openspec/principles.global.md`.
- Add product-local `docs/surface-quality-bar.md` overlay for product path rows
  / typical entries (do **not** put those rows in the synced `.global.md`).
- **Thin Auth-B** (same PR): sync `scripts/bin/gh`, `scripts/dev-tokens.sh`,
  `scripts/set-dev-tokens.sh` so skill auth docs match runtime.
- **P3 principles**: add `.global` verbatim; rewrite local
  `openspec/principles.md` as a modernized product overlay (do not weaken
  Type Safety / Supported environment). Finder/surface path examples live in
  `docs/surface-quality-bar.md`, not in principles.
- Remove `.agents/skills/scan-secrets/` and related AGENTS/exclude refs
  (vendor set is `{gh,docker,hadolint,uv}`). Replace local arctrl tree with
  the shared first-party skill from Devinfra.
- Minimal lint-exclude updates for new vendor skills; thin `AGENTS.md` pointers.
- Smoke-test `/review-fixer` (and briefly create/issue-fixer entrypoints).

### Non-goals

- Full Wave B (git wrapper, quality/pre-commit skeleton, Dev Container) or Wave C (CI `uses:`).
- Root `pyproject.toml` uv workspace membership for `m42-ai` (use
  `uv run --project scripts/ai …`).
- Forking product examples back into synced `docs/ai_review_policy.md` or
  `docs/surface-quality-bar.global.md`.
- Blocking on Devinfra sync automation (#13).
- Adopting sibling repos in this change (fleet F1: pilot only).

## Capabilities

### New Capabilities

- _none — `skip_specs: true`._ Shared agent/tooling behaviour is owned by
  Devinfra specs; this change does not alter product domain requirements under
  `openspec/specs/` (`arc-*`, `harvest-*`, admission-control, ci-cd, …).

### Modified Capabilities

- _none._

## Impact

- **Docs / agent stack:** synced paths under `docs/` (incl. surface-bar
  `.global`), `.cursor/`, `.github/`, `.agents/skills/` (incl. `arctrl`),
  `scripts/ai/`, `openspec/principles.global.md`.
- **Local docs:** `openspec/principles.md`, `docs/surface-quality-bar.md`,
  `AGENTS.md`.
- **Auth helpers:** `scripts/bin/gh`, `scripts/dev-tokens.sh`,
  `scripts/set-dev-tokens.sh` (may require one `source ./scripts/set-dev-tokens.sh`
  for legacy non-`b64:` token store lines).
- **Removed:** `.agents/skills/scan-secrets/`; prior local-only arctrl content
  replaced by shared skill.
- **Unchanged:** `middleware/**`, product OpenSpec specs/changes (except this
  change folder), full Wave B/C surfaces.
- **Fleet:** decision matrix on #366 (and stubs on sql_to_arc#93 /
  harvester#167); refresh after #32/#35 (see issue follow-up).
