# Tasks

## 1. Tooling

- [ ] 1.1 Add griffe (or chosen inspector) as a dev dependency and an allowlist config for `api_client` + selected
      `shared` modules (`report`, `security`, ConfigWrapper)
- [ ] 1.2 Implement a script that diffs allowlisted surface vs `main`, detects breaking changes, scans `main..HEAD` for
      Conventional Commit breaking markers, and exits non-zero only on undeclared breaks
- [ ] 1.3 Wire the script into PR code-quality CI and document/local quality entry (hook or `scripts/` command) with the
      same behaviour

## 2. Docs and verification

- [ ] 2.1 Document the gate in `docs/quality.md` (and a one-line review-policy pointer if needed): toolchain-owned;
      declare break or revert
- [ ] 2.2 Verify with a fixture or dry-run: undeclared break fails; declared break / additive-only passes
