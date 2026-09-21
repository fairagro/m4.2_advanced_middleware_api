---
name: code-review
description: >-
  Produces a first-party critical review of a local branch diff (vs base) or a
  GitHub pull request. Use when the user asks to /code-review, review this
  branch/PR, or run a structured code review — not for triaging Copilot/Bugbot
  threads (that is /review-fixer).
---

# Code review

You are a **first-party reviewer** (judgment). Quality tools and CI are the gate for style/types/secrets scanners.
`/review-fixer` consumes **external** Copilot/Bugbot threads **and** this skill’s marked COMMENT summaries — do **not**
triage those here.

Do **not** commit, push, or auto-approve. Do **not** auto-LGTM. **One** publish per run (no silent re-post loops).

## Input

Accept any of:

1. Local review: optional `--base` (default `main`); review merge-base(base, HEAD)...HEAD
2. PR review: PR number or URL
3. “Review this branch / this PR”

Same checklist for local and PR.

## Auth (`gh`)

Prefer `uv run --project scripts/ai m42-ai …` (works in Devinfra and product checkouts). Bare `uv run m42-ai` is only OK
when `scripts/ai` is a root workspace member (Devinfra).

`gh` is wrapped (`scripts/bin/gh`, on `PATH` in the Dev Container). Never invent or paste PATs into chat.

**Agent / no TTY (PR publish only):** If auth is missing:

1. Ask the user to run `source ./scripts/set-dev-tokens.sh` in a real terminal and wait.
2. Retry `uv run --project scripts/ai m42-ai auth-status`.
3. If they decline or auth still fails: keep the `/tmp` report and **skip** GitHub writes.

Local-only reviews never require GitHub auth.

## Mechanical steps (`m42-ai`)

1. **Context**

   ```bash
   uv run --project scripts/ai m42-ai code-review-context --base main
   # or
   uv run --project scripts/ai m42-ai code-review-context --pr <n>
   ```

   Use `paths` / `stats` from JSON. Full patch is omitted — open files as needed.

2. **Review** (agent judgment — see Goals). Produce structured Markdown (summary + findings table).

3. **Write report**

   ```bash
   uv run --project scripts/ai m42-ai code-review-report-write --slug <branch-or-pr> --body-file - <<'EOF'
   …report…
   EOF
   ```

4. **Publish**

   - No PR: stop after report write (`code-review-publish` without `--pr` is a GitHub no-op).
   - With PR + auth:

     ```bash
     uv run --project scripts/ai m42-ai code-review-publish --pr <n> --body-file <path-from-step-3>
     ```

     Prefer channel `pull_request_review` (COMMENT via `gh pr review --comment`). Fallback `conversation_comment` only
     if review submit fails. Do not approve or request-changes.

## Goals (skip when N/A)

1. Security (logic/auth/secrets-in-diff intent — not Bandit/CodeQL noise replay)
2. Correctness / missing edge cases (inputs, network, config)
3. Concurrency & races (when async/shared state)
4. Architecture & simplicity (YAGNI)
5. Import graph / cycles — **judgment-only** for what import-linter does not encode (Import policy in
   [`openspec/principles.global.md`](../../../openspec/principles.global.md)); mechanical cycle/layer/forbidden →
   import-linter
6. Defensive bloat vs real edges
7. Resource frugality
8. Dead / unused code (judgment beyond what vulture already gates; mechanical unused definitions are toolchain-owned)
9. OpenSpec↔code drift — **only** where specs exist and the diff touches that surface
10. Docs↔code drift (weaker severity than spec drift)
11. Test adequacy for new risks (not coverage-% nagging)

Severity / cost language: [`docs/ai_review_policy.md`](../../../docs/ai_review_policy.md). Medium+ MAY offer
`/create-issue` — do **not** auto-create unless the user asks.

## Anti-duplication (hard rule)

Do **not** restate findings owned by: Ruff, mypy, pylint, Bandit, markdownlint, Prettier, ggshield, CodeQL, Trivy,
**vulture**, and **import-linter**. Out of scope: format, import sort, line-length, type noise CI already fails. Do not
re-report mechanical unused-definition hits that the fleet vulture gate (`--min-confidence 100`) would catch, or
cycle/layer/forbidden hits that import-linter would catch. Judgment MAY still cover Import-policy rules outside the
linter (module-level placement, relative imports, `sys.path` mutation, lazy imports used only to break cycles).

## Output shape

Published / `/tmp` reports **MUST** start with the stable HTML comment marker so `/review-fixer` can triage them (even
when the GitHub author is a human login):

```markdown
<!-- m42-ai:code-review -->
```

Suggested Markdown after the marker:

- Short verdict (risks / open questions — not LGTM)
- Findings table with columns **path**, **goal**, **severity**, **cost**, **note** (header row required; empty findings
  → table omitted or a single “none” row is fine — without a `path` column, review-fixer ignores the body)
- Optional: “defer via `/create-issue`” for Medium+

## Relationship

| Skill           | Role                                                                |
| --------------- | ------------------------------------------------------------------- |
| `/code-review`  | Produce first-party review of a diff / PR (marker + findings table) |
| `/review-fixer` | Triage Copilot/Bugbot **and** `/code-review` summary findings       |
| `/create-issue` | Open deferred issues (optional hand-off)                            |
