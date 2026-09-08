# Issue-fixer conventions

Shared `/issue-fixer` triages a GitHub issue, explores when needed, then runs the OpenSpec cadence and opens a draft PR
only after real commits exist — without auto-committing fix commits. Canonical skill:
[`.agents/skills/issue-fixer/SKILL.md`](../.agents/skills/issue-fixer/SKILL.md).

Issue: [#15](https://github.com/fairagro/m4.2_middleware_devinfra/issues/15).

OpenSpec (`/opsx-*`) is **only** for `/issue-fixer` — not `/review-fixer` or `/create-issue`.

## Workflow (summary)

1. Fetch + triage (type, labels, done-when).
2. When explore is required (`Feature` / `Refactoring`, or Bug/Security/Task when criteria are unclear / user asks):
   **`/opsx-explore`** (no parallel in-skill explore). Wait for lock-in / `go` / `skip explore`.
3. **OpenSpec cadence** (mandatory when this run will implement):
   1. Create issue branch → `/opsx-propose` → **pause** (review specs; you may commit on that branch)
   2. On continue: `/opsx-apply` → **pause** (review / commit / push) — no draft PR yet
   3. On continue: draft PR (`m42-ai issue-start` / `gh pr create --draft` when tip is ahead of `main`) +
      `/opsx-archive` — never empty bootstrap commits
4. No `Made with Cursor` (or similar) footers in PR bodies — strip if injected.
5. For `scripts/` (shared Devinfra + agent plumbing): implement only the documented Dev Container / CI happy path — no
   exotic edges (worktrees, host brew, legacy parsers, …) unless done-when says so; see skill **Surface quality bar**
   and [`surface-quality-bar.global.md`](surface-quality-bar.global.md).
6. Split only on logical blocks; deferred work via [`/create-issue`](create-issue.md) with relation:
   - **sub-of** — still part of this issue’s acceptance criteria (GitHub native sub-issue)
   - **linked** — distinct follow-up problem

## Auth

Same personal-token helpers as `/review-fixer` — see root README **Personal tokens** and `scripts/bin/gh`.
