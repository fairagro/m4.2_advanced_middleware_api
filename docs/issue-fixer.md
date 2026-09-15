# Issue-fixer conventions

Shared `/issue-fixer` triages a GitHub issue, explores when needed, and implements on `issue-<n>-<slug>`. **Feature /
Refactoring** use OpenSpec (propose → apply → draft PR → archive as last `go`), except a **clearly docs-only** slice
(Markdown/MDC and/or code comments — **not** if a skill file is touched). **Task**, **Bug**, and cheap **Security** stay
on the fast path (no OpenSpec unless asked, or a skill file is in scope). No auto-commit of fix commits; draft PR only
after real commits exist. Canonical skill:
[`.agents/skills/issue-fixer/SKILL.md`](../.agents/skills/issue-fixer/SKILL.md). Devinfra is source of truth — products
must not fork the skill (sync allowlist).

Issue: [#15](https://github.com/fairagro/m4.2_middleware_devinfra/issues/15),
[#54](https://github.com/fairagro/m4.2_middleware_devinfra/issues/54),
[#125](https://github.com/fairagro/m4.2_middleware_devinfra/issues/125).

`/review-fixer` and `/create-issue` do **not** run `/opsx-*`. `/issue-fixer` **embeds** propose / apply / archive by
following those skills in the same run for OpenSpec types. Standalone OpenSpec slash commands remain available when
invoked explicitly.

## Workflow (summary)

1. Fetch + triage (type, labels, done-when).
2. When explore is required (`Feature` / `Refactoring`, or Bug/Security/Task when criteria are unclear / user asks):
   explore **in-skill** (no `/opsx-explore`). Wait for lock-in / `go` / `skip explore`.
3. Create the issue branch **before** propose or implement.
4. **OpenSpec types (Feature / Refactoring):** follow openspec-propose → **pause** → on `go` apply → **pause** → on `go`
   draft PR (`uv run --project scripts/ai m42-ai issue-start` when the tip is ahead of `main`) → on `go` (last) follow
   openspec-archive → **pause** to commit. Never empty bootstrap commits. Same path if a skill file is in scope (even
   for Task) or the user said `use opsx`.
5. **Task / Bug / cheap Security**, and **docs-only** Feature/Refactoring with no skill file: implement in the working
   tree → **pause** → on continue: draft PR when ahead of `main`. If a Task clearly changes `openspec/specs/`, pause
   once (retype Feature or `use opsx`) — do not silently invent a change folder.
6. **`skip_specs`:** when OpenSpec **is** used, real delta spec if a capability contract changes; `skip_specs: true`
   only for tooling with **no** spec-level behavior change (do not invent a requirement to pass validation). Docs-only
   Feature/Refactoring without a skill file skips OpenSpec entirely rather than using `skip_specs`.
7. No `Made with Cursor` (or similar) footers in PR bodies — strip if injected.
8. For `scripts/` (shared Devinfra + agent plumbing): implement only the documented Dev Container / CI happy path — no
   exotic edges (worktrees, host brew, legacy parsers, …) unless done-when says so; see skill **Surface quality bar**
   and [`surface-quality-bar.global.md`](surface-quality-bar.global.md).
9. Split only on logical blocks; deferred work via [`/create-issue`](create-issue.md) with relation:
   - **sub-of** — still part of this issue’s acceptance criteria (GitHub native sub-issue)
   - **linked** — distinct follow-up problem

## Auth

Same personal-token helpers as `/review-fixer` — see root README **Personal tokens** and `scripts/bin/gh`.
