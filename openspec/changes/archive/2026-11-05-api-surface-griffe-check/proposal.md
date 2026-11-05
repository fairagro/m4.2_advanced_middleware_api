# Proposal

## Why

Consumers depend on the published Python surfaces of `fairagro-middleware-api-client` and selected `shared` modules.
Silent breaking signature/export changes slip through when Conventional Commits omit `!` / `BREAKING CHANGE:`. A
griffe-based surface diff vs `main` should fail the PR unless the commit history correctly declares the break.

## What Changes

- Add a product-local griffe (or equivalent) API surface check for an allowlisted set of public Python modules
- Run it in PR code-quality CI and as a local script/hook entry (same rules)
- Compare PR tip vs `main`; classify breaking vs non-breaking
- **Fail** when breaking changes are detected and no commit on the PR declares breaking via Conventional Commits
  (`type!:` or `BREAKING CHANGE:` footer); **pass** when breaking is declared or the diff is non-breaking only
- Document the gate for agents / review policy (toolchain-owned; do not re-triage as review nits)
- Keep Devinfra fleet fragment out of scope until a second product needs the same pattern (#570)

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `ci-cd`: Require a public Python API surface diff gate (allowlisted packages) on code PRs / local quality, synced to
  Conventional Commit breaking markers

## Impact

- CI / pre-commit or `scripts/` quality helper; optional `griffe` (or similar) dev dependency
- Docs: `docs/quality.md` and/or AI review policy note that surface-diff failures are toolchain-owned
- Issue: #570; siblings #651 (HTTP) / #652 (CouchDB) remain separate
- Allowlist (lock-in 1S): `middleware.api_client` public exports plus selected `middleware.shared` public modules
  (`report`, `security`, `config` / ConfigWrapper — exact module list in design)
