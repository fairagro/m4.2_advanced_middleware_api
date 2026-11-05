# Design

## Context

Issue #570: product-local Python API surface gate (not Devinfra fleet yet). Lock-ins: **1S** (api_client + selected
shared), **Härte Sync** (breaking requires Conventional Commit `!` / `BREAKING CHANGE:`), **3B** (PR CI + local), **4M**
(diff vs `main`). Siblings #651/#652 cover HTTP OpenAPI and CouchDB schemas separately.

Release versioning already uses Conventional Commits / git-cliff; this gate makes **undeclared** breaks fail before
merge.

## Goals / Non-Goals

**Goals:**

- Detect breaking changes on an allowlisted public Python surface vs `main`
- Fail CI/local quality when a break is undeclared; allow declared breaks
- Same script for CI and local invocation

**Non-Goals:**

- HTTP `/v3` OpenAPI diff (#651) or CouchDB document schemas (#652)
- Devinfra shared fragment
- Failing on non-breaking additive API changes
- Requiring a major version bump in the same PR (declaration via CC is enough for this gate)

## Decisions

1. **Tool:** Prefer **griffe** + a small wrapper script (e.g. `scripts/check-api-surface.sh` or `uv run` module) that:
   loads surface for `main` and HEAD (git worktree or checkout of merge-base/`origin/main`), runs a breaking-change
   report, then inspects `git log main..HEAD` for `!:` subject or `BREAKING CHANGE:` footer. Exit non-zero only when
   breaking ∧ undeclared.

2. **Allowlist (1S):**
   - Package `middleware.api_client` (respect package `__all__` / public objects griffe marks as public)
   - `middleware.shared.report` (package `__all__`)
   - `middleware.shared.security` (`UrlStr`, `redact_url_userinfo`)
   - `middleware.shared.config.config_wrapper.ConfigWrapper` (and ConfigBase if exported as part of that contract)
   - Explicit config file (YAML/TOML) listing modules so the allowlist is reviewable without digging the script

3. **Baseline (4M):** Compare against `origin/main` (or `main`) tip of the allowlisted modules at merge-base or by
   checking out that ref into a temp dir. Document shallow-clone needs in CI.

4. **Invocation (3B):** Call from product code-quality path (workflow step or reusable input overlay) and from a
   documented local command / optional pre-commit hook that shells the same script. Path filter: run when allowlisted
   paths change (still OK to always run — surface load is cheap relative to pytest).

5. **Agent docs:** One short note in `docs/quality.md` (+ review policy cross-link if needed): failures are
   toolchain-owned; fix by reverting the break or adding a proper breaking Conventional Commit.

## Risks / Trade-offs

- **False public:** Shared modules without a tight `__all__` may over-report — mitigate with explicit allowlist file.
- **Multi-commit PRs:** Declaration may be on an earlier commit on the branch; scan all commits `main..HEAD`, not only
  the tip subject.
- **main already broken:** Diff vs main only catches PR-introduced breaks relative to current main, not vs last PyPI tag
  (acceptable for 4M; release vs tag is out of scope).
