---
name: issue-fixer
description: >-
  Triages a GitHub issue, explores when required, then either the Bug fast path
  or OpenSpec (Task/Feature/Refactoring: propose → apply → draft PR → archive).
  No auto-commit of fix commits. Use when the user asks to /issue-fixer, fix an
  issue, or start work from an issue URL/number.
---

# Issue fixer

Triage and fix a GitHub issue. You are the **fixer** (precision): implement the smallest correct MVP slice in this PR,
or split deferred work via `/create-issue` when it becomes too large.

You may create a branch and later a **draft** PR (only after the branch tip has real commits ahead of `main`). To close
the issue automatically on merge, the PR body must include: `Fixes #<issue_number>`.

**Do not** auto-commit or auto-push **fix** commits. **Do not** create empty bootstrap commits. The user commits and
pushes; the agent opens the draft PR only when the tip already differs from `main` with that real history.

## Input

- Issue number or URL (preferred)

## Auth (`gh`)

Prefer `uv run --project scripts/ai m42-ai …` (works in Devinfra and product checkouts). Bare `uv run m42-ai` is only OK
when `scripts/ai` is a root workspace member (Devinfra).

`gh` is wrapped (`scripts/bin/gh`, on `PATH` in the Dev Container via `remoteEnv`). Missing `GH_TOKEN` prompts on
`/dev/tty` and is saved to `/commandhistory/tokens.env` (Linux Dev Container only — see `docs/conventions.md`). The
wrapper sources `scripts/dev-tokens.sh` on each invoke (no `.bashrc` patch). Do not read tokens from the git worktree;
do not invent them. Never ask the user to paste a PAT into chat.

**Agent / no TTY:** `/dev/tty` is unavailable in chat, so the wrapper cannot prompt. Before skipping GitHub writes:

1. Tell the user `GH_TOKEN` is missing and that the agent cannot open an interactive prompt here.
2. Ask them to run in a **Dev Container / IDE terminal** (not chat):

   ```bash
   source ./scripts/set-dev-tokens.sh
   ```

   Then reply here when done (or decline).

3. After they confirm, retry `uv run --project scripts/ai m42-ai auth-status` (or `gh auth status`). If auth works,
   continue with fetch / branch / PR as usual.
4. Only if they decline or auth still fails: skip GitHub writes, print intended branch/PR drafts, and may still work
   locally when appropriate.

## Fetch issue & triage

1. Prefer the CLI for a stable shape:

   ```bash
   uv run --project scripts/ai m42-ai issue-view --issue <issue_number>
   ```

   Use `issue_type`, `labels`, `triage`, `body`, and `url` from that JSON (fall back to `gh issue view` only if the CLI
   is unavailable).

2. Determine:
   - org issue type: `Bug|Security|Feature|Task|Discussion|Refactoring` (from `issue_type` when set)
   - triage labels: `severity:*`, `practicality:*`, `cost:*` (from `triage` / `labels` when set)
   - problem statement; affected paths; acceptance criteria / “done when”

3. Early exits:
   - Missing actionable info → comment with at most 3 questions and stop (no code / no PR).
   - Already resolved / not applicable → comment briefly and stop.
   - Type `Discussion` → do **not** create branch/PR by default; ask for a decision or retype. Proceed only if the user
     explicitly requests a concrete implementation.
   - Type `Security` → may implement, but require clear acceptance criteria and a realistic path; prefer the smallest
     correct fix; no speculative hardening with no path.

## Explore (when required)

After triage, **before** branch / propose / implement / PR, decide whether explore runs:

| Type                      | Explore?                                                         |
| ------------------------- | ---------------------------------------------------------------- |
| `Feature`, `Refactoring`  | **Required**                                                     |
| `Discussion`              | Explore is the whole response (no implement by default)          |
| `Bug`, `Security`, `Task` | Only if criteria missing, multiple plausible fixes, or user asks |

When explore **is** required (or the user asked for it): explore **in this skill** — clarify scope, compare options,
surface risks, and wait for user lock-in, `go`, or `skip explore`. **Do not** invoke `/opsx-explore`. **Do not** create
branches, commits, PRs, or OpenSpec changes during explore.

When explore is **not** required, skip it and continue to the type-routed next step.

## OpenSpec routing (by issue type)

`/review-fixer` and `/create-issue` MUST NOT run OpenSpec. Standalone `/opsx-*` remain available when the user invokes
them explicitly outside these skills.

Default by org issue type (user override wins: “use opsx” on a Bug, or “skip openspec” on a Task):

| Type                             | OpenSpec?                                                        |
| -------------------------------- | ---------------------------------------------------------------- |
| `Task`, `Feature`, `Refactoring` | **Required** — unless the slice is clearly **docs-only** (below) |
| `Bug`, cheap `Security`          | **No** unless the user asks                                      |
| `Discussion`                     | No implement by default                                          |

**Docs-only (no OpenSpec):** it is clear the slice only changes Markdown/MDC and/or code comments. **Exception:** if a
skill file is in scope (`SKILL.md` under `.agents/skills/` or `.cursor/skills/`), OpenSpec stays required. Markdown
under `openspec/specs/` or `openspec/changes/` is not docs-only. If unclear, keep OpenSpec for Task/Feature/Refactoring.

**Embed (do not copy skill steps into this file):**

- Propose: read and follow
  [`.cursor/skills/openspec-propose/SKILL.md`](../../../.cursor/skills/openspec-propose/SKILL.md)
- Apply: read and follow
  [`.cursor/skills/openspec-apply-change/SKILL.md`](../../../.cursor/skills/openspec-apply-change/SKILL.md)
- Archive: read and follow
  [`.cursor/skills/openspec-archive-change/SKILL.md`](../../../.cursor/skills/openspec-archive-change/SKILL.md)

**`skip_specs` vs delta specs:** write a real delta spec when a capability contract changes. Set `skip_specs: true` only
for docs/tooling with **no** spec-level behavior change. Do not invent a requirement solely to pass `openspec validate`.

This skill is Devinfra source of truth (synced allowlist). Products MUST NOT fork it.

## Implement cadence

On every run that will implement, after explore (when it ran) or immediately when explore was skipped:

1. **Create the issue branch** from `main` via CLI when possible (**before** OpenSpec artifacts or product code):

   ```bash
   uv run --project scripts/ai m42-ai issue-branch --issue <issue_number> [--slug <slug>]
   ```

   Do **not** commit, push, or open a draft PR yet. If already on the correct issue branch, skip creating it again.

2. **Task / Feature / Refactoring** (OpenSpec path), unless docs-only with no skill file:

   1. Follow openspec-propose → **pause** (user reviews proposal / specs / design / tasks).
   2. On `go`: follow openspec-apply → **pause** (user reviews working tree; they commit/push).
   3. On `go`: ensure a **draft** PR when the tip is ahead of `main` (next section).
   4. On `go` (**last**): follow openspec-archive → **pause** so the user can commit archive results.

3. **Bug / cheap Security**, and **docs-only** Task/Feature/Refactoring that do not touch a skill file: implement in the
   working tree → **pause** → on `go`: draft PR when ahead of `main`. Do **not** create an OpenSpec change for process.

Early exits that never implement skip this cadence. Once the user asks to implement a `Discussion`, start at branch +
the type-routed path (OpenSpec if they retyped it as Task/Feature/Refactoring).

## Branch + draft PR (real commits only)

**Branch early:** create `issue-<issue_number>-<slug>` from `main` **before** propose or implement. That step does
**not** open the PR yet.

**Draft PR:** after the implement/apply-pause confirmation. Assumptions: base branch is `main`. Prefer the plumbing CLI
when the tree is clean and the tip is already ahead of `main` (`git log main..HEAD` non-empty — uncommitted work does
not count):

```bash
uv run --project scripts/ai m42-ai issue-start --issue <issue_number> [--slug <slug>]
```

`issue-start` ensures branch `issue-<issue_number>-<slug>` (checkout/create from `main` if needed), refuses when there
are no commits ahead of the base, pushes, and opens a **draft** PR with `Fixes #<issue_number>`. It does **not** create
empty commits. See [`scripts/ai/README.md`](../../../scripts/ai/README.md).

If a draft PR already exists, skip create. Always prefer `m42-ai pr-strip-footer --pr <n>` after create (or when a
footer may have been injected) instead of hand-editing with ad-hoc `gh` regexes.

If the tip still equals `main`, do **not** open a PR and do **not** create an empty commit — ask the user to commit
first. For OpenSpec types, archive is still the last `go` after this step (working-tree archive, then pause for commit).

**PR body hygiene:** Do **not** append tool marketing footers (e.g. `Made with Cursor`, `Made with [Cursor](…)`). Body
is Summary + `Fixes #<issue_number>` (+ deferred issue links when needed). If a footer appears after create, remove it
immediately with:

```bash
uv run --project scripts/ai m42-ai pr-strip-footer --pr <pr_number>
```

Manual equivalent if the CLI is unavailable:

1. Be on `issue-<issue_number>-<slug>` with **at least one real commit** ahead of `main` (never
   `git commit --allow-empty`).
2. Push the branch and create a **draft** PR:

   ```bash
   gh pr create --draft --base main --title "..." --body "$(cat <<'EOF'
   ## Summary
   - MVP scope: …

   Fixes #<issue_number>
   EOF
   )"
   ```

3. Do **not** mark the PR ready for review. Remind the user to mark ready when they want review.

## Implement fixes (locally)

- Implement in the working tree on the issue branch (via apply on the OpenSpec path).
- Do **not** commit or push fix commits.
- If too large: split (below) and implement only the MVP slice here.
- When the consumer has product `middleware/` packages: run focused `uv run pytest` on affected packages and
  `uv run ruff format --config pyproject.toml` / `ruff check` on touched files (same bar as `/review-fixer`). This
  Devinfra repo has no product `middleware/` tree — skip those commands here.

## Split / deferred work (via create-issue)

Split only when ≥2 **logically independent**, independently mergeable blocks exist. Within a block, ~50 new production
lines is a **guideline**, not a hard cap. Extra signals only when blocks exist: new abstraction, spec-contract change,
prerequisite refactor.

Open deferred slices by reading and following [`.agents/skills/create-issue/SKILL.md`](../create-issue/SKILL.md) (one
invocation per issue, max 3–6). Do **not** call `gh issue create` with an issue-fixer-only inline template.
`/create-issue` itself does **not** run OpenSpec.

**Relation (lock-in G):**

- Still part of this issue’s acceptance criteria / done-when → `relation: sub-of #<issue_number>` (GitHub native
  sub-issue).
- Distinct follow-up problem (not in done-when) → `relation: linked`.
- Unclear → ask once; default `linked`.

Types for slices: `Refactoring` when structural; `Task` when the parent is only subdivided; keep Bug/Feature/Security
when the slice retains that nature.

Link deferred issue URLs from the PR body. If create-issue is missing in a consumer checkout, say so and print intended
create-issue inputs — do not invent an off-allowlist create path.

## Fix quality

- Follow Type Safety in [`openspec/principles.global.md`](../../../openspec/principles.global.md): no wide types (`Any`,
  `object`, unnecessary `T | None`).
- Update specs only when the real contract changes (OpenSpec delta on the Task/Feature/Refactoring path; archive folds
  into main specs).

## Surface quality bar (`scripts/` — implement)

Match the **rules** in [`docs/ai_review_policy.md`](../../../docs/ai_review_policy.md#surface-quality-bar-fixer-triage)
and the **path map** in [`docs/surface-quality-bar.global.md`](../../../docs/surface-quality-bar.global.md) (plus
optional product [`docs/surface-quality-bar.md`](../../../docs/surface-quality-bar.md)), and the supported environment
in [`openspec/principles.global.md`](../../../openspec/principles.global.md). This applies to explore lock-ins and
implementation — not only to review triage.

**Hard rule:** for shared Devinfra `scripts/` (except `scripts/ai/`) and agent plumbing, prefer the **simplest**
happy-path contract. Do not expand the MVP with “also support worktrees / host X / legacy Y”. If that work is real but
out of done-when, split via `/create-issue` (`relation: linked`) — do not sneak it into the MVP slice.

## Output to the user

Provide:

- Issue URL + number + org issue type
- Whether explore ran and what was locked
- Whether OpenSpec ran (change name) or the Bug fast path
- Branch name
- Draft PR URL when opened (or “PR deferred until real commits” / “skipped PR creation”)
- Created sub-issue / linked-issue URLs (or none)
- Reminder: user commits, pushes, and marks the PR ready; agent does not auto-commit fix commits
