# Adopt Devinfra Wave A — Tasks

## 1. Pin and sync Wave A paths

- [x] 1.1 Record Devinfra `main` commit SHA to use for this adopt (document in
      PR description when opening)
- [x] 1.2 Copy verbatim from that SHA: `docs/ai_review_policy.md`,
      `docs/surface-quality-bar.global.md`, `docs/review-fixer.md`,
      `docs/create-issue.md`, `docs/issue-fixer.md`
- [x] 1.3 Copy verbatim: `.cursor/BUGBOT.md`,
      `.cursor/commands/{review,create,issue}-fixer.md`
- [x] 1.4 Copy verbatim: `.github/copilot-instructions.md`,
      `.github/prompts/{review,create,issue}-fixer.prompt.md`
- [x] 1.5 Copy verbatim: `.agents/skills/{review-fixer,create-issue,issue-fixer}/`
- [x] 1.6 Copy verbatim first-party `.agents/skills/arctrl/` from Devinfra
      (replace local tree; note any unique local tips before overwrite)
- [x] 1.7 Install/copy vendor skills `.agents/skills/{gh,docker,hadolint,uv}/`
      per Devinfra README (`gh skill install` or tree copy from SHA)
- [x] 1.8 Copy verbatim: `scripts/ai/` (full tree including tests and lock) and
      `openspec/principles.global.md`

## 2. Thin Auth-B

- [x] 2.1 Copy verbatim: `scripts/bin/gh`, `scripts/dev-tokens.sh`,
      `scripts/set-dev-tokens.sh`
- [x] 2.2 Confirm `scripts/bin/git` and other Wave B paths are untouched

## 3. Local overlay (P3 + surface-bar) and cleanup

- [x] 3.1 Rewrite `openspec/principles.md` as P3 product overlay (extends
      `.global`; product stack/modules/scaling retained and modernized; no
      weakened Type Safety / Supported environment; **no** Finder/surface
      examples section — that belongs in surface-bar overlay)
- [x] 3.2 Create local `docs/surface-quality-bar.md` with product path rows /
      typical entries (`/v3/…`, Celery, CouchDB, `dev_environment/config.yaml`);
      do not edit synced `.global.md` or policy for those rows
- [x] 3.3 Update `AGENTS.md` pointers (`.global` principles; surface-bar
      global + local; vendor set; shared `arctrl`; `m42-ai` / `scripts/ai`;
      drop scan-secrets guidance)
- [x] 3.4 Remove `.agents/skills/scan-secrets/` and related exclude/refs
- [x] 3.5 Extend minimal lint excludes (e.g. `.markdownlintignore`,
      `.prettierignore`, `.pre-commit-config.yaml` exclude patterns only) for
      `docker` / `hadolint` / `uv` — no skeleton rewrite; do not treat
      first-party `arctrl` as a vendor exclude unless Devinfra does

## 4. Verify and smoke

- [x] 4.1 Run `uv run --project scripts/ai m42-ai --help` and
      `uv run --project scripts/ai m42-ai auth-status` (re-prompt tokens via
      `source ./scripts/set-dev-tokens.sh` if needed)
- [x] 4.2 Run `uv run --project scripts/ai pytest` for `scripts/ai` tests
- [x] 4.3 Smoke `/review-fixer` against one real PR; briefly exercise
      `/create-issue` and `/issue-fixer` entrypoints
- [x] 4.4 Diff synced paths against pinned SHA; confirm no intentional local
      edits on synced files (local overlay `docs/surface-quality-bar.md` and
      `openspec/principles.md` excepted)
