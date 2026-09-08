---
name: issue-fixer
description: >-
  Triages a GitHub issue, explores Feature/Refactoring decisions with the user,
  implements via OpenSpec cadence, and opens a draft PR only after real commits
  exist — without auto-committing fix commits. Use when the user asks to
  /issue-fixer, fix an issue, or start work from an issue URL/number.
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

3. After they confirm, retry `uv run m42-ai auth-status` (or `gh auth status`). If auth works, continue with fetch /
   branch / PR as usual.
4. Only if they decline or auth still fails: skip GitHub writes, print intended branch/PR drafts, and may still work
   locally when appropriate.

## Fetch issue & triage

1. Prefer the CLI for a stable shape:

   ```bash
   uv run m42-ai issue-view --issue <issue_number>
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

## Explore (when required): `/opsx-explore`

After triage, **before** `/opsx-propose` / branch / commit / PR, decide whether explore runs:

| Type                      | Explore?                                                         |
| ------------------------- | ---------------------------------------------------------------- |
| `Feature`, `Refactoring`  | **Required**                                                     |
| `Discussion`              | Explore is the whole response (no implement by default)          |
| `Bug`, `Security`, `Task` | Only if criteria missing, multiple plausible fixes, or user asks |

When explore **is** required (or the user asked for it): read and follow
[`.cursor/skills/openspec-explore/SKILL.md`](../../../.cursor/skills/openspec-explore/SKILL.md) (same as
`/opsx-explore`). Do **not** substitute a parallel in-skill explore procedure. **Do not** create branches, commits, or
PRs during explore. Wait for user lock-in, `go`, or `skip explore`.

When explore is **not** required, skip `/opsx-explore` and continue to the OpenSpec cadence (propose → …).

**Scope:** OpenSpec (`/opsx-explore`, `/opsx-propose`, `/opsx-apply`, `/opsx-archive`, `/opsx-update`) is **only** for
`/issue-fixer`. `/review-fixer` and `/create-issue` MUST NOT invoke OpenSpec commands.

## OpenSpec cadence (required when implementing)

On every run that will implement, after explore (when it ran) or immediately when explore was skipped:

### 1. Issue branch → `/opsx-propose` → pause

1. **Create the issue branch first** from `main` via CLI when possible:

   ```bash
   uv run m42-ai issue-branch --issue <issue_number> [--slug <slug>]
   ```

   Do **not** commit, push, or open a draft PR yet. If already on the correct issue branch, skip creating it again.

2. Require a local `openspec/` tree. If it is missing, stop and tell the user — do not skip propose and implement
   anyway.
3. Read and follow [`.cursor/skills/openspec-propose/SKILL.md`](../../../.cursor/skills/openspec-propose/SKILL.md) (same
   as invoking `/opsx-propose`): create a change name from the issue, generate proposal / specs / design / tasks on that
   branch.
4. Name the change from the issue (kebab-case slug + issue context). Fold explore lock-ins into design/tasks.
5. **Pause (spec review):** **Stop**. Show the change name/path and branch name; ask the user to review proposal / specs
   / design / tasks and to **commit** (and optionally push) as they wish. Do **not** open a draft PR, run apply, or
   archive until they confirm (e.g. `go`, `approved`, or an `/opsx-update` pass then `go`). If they request changes, run
   `/opsx-update` (or edit artifacts) and pause again.

**`/opsx-propose` is mandatory** before implementation (always after the issue branch exists).

Early exits that never implement (missing info, already resolved, `Discussion` without an explicit implement request)
skip this cadence. Once the user asks to implement a `Discussion`, start at branch + propose.

### 2. On continue: `/opsx-apply` → pause

After the user confirms the propose pause:

1. Read and follow
   [`.cursor/skills/openspec-apply-change/SKILL.md`](../../../.cursor/skills/openspec-apply-change/SKILL.md)
   (`/opsx-apply`) against that change’s `tasks.md`. Implement in the working tree only — do **not** commit or push fix
   commits. Do **not** open a draft PR in this step.
2. **Pause (apply review):** When apply tasks for this slice are done (or blocked on the user), **stop**. Summarize what
   changed, remind them to review / **commit** / **push**, and wait for `go` (or equivalent). Do **not** run
   `/opsx-archive` or open a draft PR during this pause.

### 3. On continue: draft PR (if needed) + `/opsx-archive`

After the user confirms the apply pause:

1. Ensure a **draft** PR exists for the issue branch (next section) **only if** the branch tip already has real commits
   ahead of `main` (`m42-ai branch-ahead` / `issue-start`). Never use `--allow-empty`. If tip still equals `main`, stop
   and ask the user to commit/push first. After create (or if a PR already exists), run
   `m42-ai pr-strip-footer --pr <n>` when a Cursor footer may have been injected.
2. Read and follow
   [`.cursor/skills/openspec-archive-change/SKILL.md`](../../../.cursor/skills/openspec-archive-change/SKILL.md)
   (`/opsx-archive`) for the change. Do **not** archive before that confirmation.

## Branch + draft PR (real commits only)

**Branch early:** create `issue-<issue_number>-<slug>` from `main` **before** `/opsx-propose`, so propose artifacts land
on the issue branch and the user can commit during the spec-review pause. That step does **not** open the PR yet.

**Draft PR late:** after the apply-pause confirmation (before or as part of `/opsx-archive`). Assumptions: base branch
is `main`. Prefer the plumbing CLI when the tree is clean and the tip is already ahead of `main`:

```bash
uv run m42-ai issue-start --issue <issue_number> [--slug <slug>]
```

`issue-start` ensures branch `issue-<issue_number>-<slug>` (checkout/create from `main` if needed), refuses when there
are no commits ahead of the base, pushes, and opens a **draft** PR with `Fixes #<issue_number>`. It does **not** create
empty commits. See [`scripts/ai/README.md`](../../../scripts/ai/README.md).

If a draft PR already exists, skip create. Always prefer `m42-ai pr-strip-footer --pr <n>` after create (or when a
footer may have been injected) instead of hand-editing with ad-hoc `gh` regexes.

**PR body hygiene:** Do **not** append tool marketing footers (e.g. `Made with Cursor`, `Made with [Cursor](…)`). Body
is Summary + `Fixes #<issue_number>` (+ deferred issue links when needed). If a footer appears after create, remove it
immediately with:

```bash
uv run m42-ai pr-strip-footer --pr <pr_number>
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

Covered by **`/opsx-apply`** in the OpenSpec cadence above (after the propose pause). Same rules:

- Implement in the working tree on the issue branch.
- Do **not** commit or push fix commits.
- If too large: split (below) and implement only the MVP slice here.
- When the consumer has product `middleware/` packages: run focused `uv run pytest` on affected packages and
  `uv run ruff format --config pyproject.toml` / `ruff check` on touched files (same bar as `/review-fixer`). This
  Devinfra repo has no product `middleware/` tree — skip those commands here.

After apply: **pause** for the user (see OpenSpec cadence §2). After their next `go`: draft PR (if needed) +
**`/opsx-archive`** (§3).

## Split / deferred work (via create-issue)

Split only when ≥2 **logically independent**, independently mergeable blocks exist. Within a block, ~50 new production
lines is a **guideline**, not a hard cap. Extra signals only when blocks exist: new abstraction, spec-contract change,
prerequisite refactor.

Open deferred slices by reading and following [`.agents/skills/create-issue/SKILL.md`](../create-issue/SKILL.md) (one
invocation per issue, max 3–6). Do **not** call `gh issue create` with an issue-fixer-only inline template.

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
- Update specs only when the real contract changes.

## Surface quality bar (`scripts/` — implement / propose)

Match the **rules** in [`docs/ai_review_policy.md`](../../../docs/ai_review_policy.md#surface-quality-bar-fixer-triage)
and the **path map** in [`docs/surface-quality-bar.global.md`](../../../docs/surface-quality-bar.global.md) (plus
optional product [`docs/surface-quality-bar.md`](../../../docs/surface-quality-bar.md)), and the supported environment
in [`openspec/principles.global.md`](../../../openspec/principles.global.md). This applies to explore lock-ins, OpenSpec
design/tasks, and `/opsx-apply` — not only to review triage.

**Hard rule:** for shared Devinfra `scripts/` (except `scripts/ai/`) and agent plumbing, prefer the **simplest**
happy-path contract. Do not expand design/tasks with “also support worktrees / host X / legacy Y”. If that work is real
but out of done-when, split via `/create-issue` (`relation: linked`) — do not sneak it into the MVP slice.

## Output to the user

Provide:

- Issue URL + number + org issue type
- Whether `/opsx-explore` ran and what was locked
- OpenSpec change name / path; which cadence pause is next (`propose` / `apply` / `archive` done or pending)
- Branch name
- Draft PR URL when opened (or “PR deferred until real commits” / “skipped PR creation”)
- Created sub-issue / linked-issue URLs (or none)
- Reminder: user commits, pushes, and marks the PR ready; agent does not auto-commit fix commits
