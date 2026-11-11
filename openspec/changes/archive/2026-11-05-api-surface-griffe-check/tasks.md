# Tasks

## 1. Tooling

- [x] 1.1 Add griffe (or chosen inspector) as a dev dependency and an allowlist config for `api_client` + selected
      `shared` modules (`report`, `security`, ConfigWrapper)
- [x] 1.2 Implement a script that diffs allowlisted surface vs `main`, detects breaking changes, scans `main..HEAD` for
      Conventional Commit breaking markers, and exits non-zero only on undeclared breaks
- [x] 1.3 Wire the script into PR code-quality CI and document/local quality entry (hook or `scripts/` command) with the
      same behaviour

## 2. Docs and verification

- [x] 2.1 Document the gate in product-local `docs/api-surface-check.md` (+ surface-quality-bar pointer; synced
      `docs/quality.md` must not be hand-edited): toolchain-owned; declare break or revert
- [x] 2.2 Verify with a fixture or dry-run: undeclared break fails; declared break / additive-only passes (regex unit
      checks + live run vs `main`)
