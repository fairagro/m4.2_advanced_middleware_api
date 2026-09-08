---
name: "/issue-fixer"
id: "issue-fixer"
category: "Workflow"
description: "Triage and fix a GitHub issue (opsx-explore → branch→propose→pause → apply→pause → draft PR + archive)"
---

# issue-fixer

Triage and fix a GitHub issue. When explore is required, use **`/opsx-explore`**. Then OpenSpec cadence: **create issue
branch → `/opsx-propose` → pause → `/opsx-apply` → pause → draft PR + `/opsx-archive`**. OpenSpec is **only** for this
skill (not `/review-fixer` / `/create-issue`). Do **not** auto-commit or auto-push fix commits. Do **not** use empty
bootstrap commits; open the draft PR only after real commits exist ahead of `main`.

**Input:** Issue number or URL.

**Steps**

1. Read and follow `.agents/skills/issue-fixer/SKILL.md`.
2. When explore is required (`Feature` / `Refactoring`, or unclear Bug/Security/Task / user asks): read and follow
   `.cursor/skills/openspec-explore/SKILL.md` (`/opsx-explore`). Wait for lock-in / `go` / `skip explore`.
3. Create `issue-<n>-<slug>` from `main`, then **`/opsx-propose`**, then **pause** for spec review (user may commit).
   Wait for `go`.
4. On continue: **`/opsx-apply`** → **pause** for the user to review/commit/push. Do **not** open a draft PR here.
5. On continue: ensure **draft** PR (tip already ahead of `main`) + **`/opsx-archive`**. No `Made with Cursor` footers.
6. Deferred splits via `/create-issue` (`relation: sub-of` / `linked`) — create-issue itself does **not** run OpenSpec.
7. If `GH_TOKEN` is missing and there is no TTY, ask the user to run `source ./scripts/set-dev-tokens.sh` in a terminal
   and wait — do not paste tokens into chat.
