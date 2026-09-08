---
name: "/issue-fixer"
id: "issue-fixer"
category: "Workflow"
description: "Triage and fix a GitHub issue (branch → implement → pause → draft PR; no OpenSpec)"
---

# issue-fixer

Triage and fix a GitHub issue: **create issue branch → implement → pause → draft PR**. Explore in-skill when required.
Do **not** run OpenSpec (`/opsx-*`) as part of this skill. Do **not** auto-commit or auto-push fix commits. Do **not**
use empty bootstrap commits; open the draft PR only after real commits exist ahead of `main`.

**Input:** Issue number or URL.

**Steps**

1. Read and follow `.agents/skills/issue-fixer/SKILL.md`.
2. When explore is required (`Feature` / `Refactoring`, or unclear Bug/Security/Task / user asks): explore in-skill.
   Wait for lock-in / `go` / `skip explore`. Do **not** invoke `/opsx-explore`.
3. Create `issue-<n>-<slug>` from `main`, implement in the working tree, then **pause** for the user to
   review/commit/push. Do **not** open a draft PR here.
4. On continue: ensure **draft** PR (tip already ahead of `main`). No `Made with Cursor` footers.
5. Deferred splits via `/create-issue` (`relation: sub-of` / `linked`) — create-issue itself does **not** run OpenSpec.
6. If `GH_TOKEN` is missing and there is no TTY, ask the user to run `source ./scripts/set-dev-tokens.sh` in a terminal
   and wait — do not paste tokens into chat.
