---
description: "Triage and fix a GitHub issue (branch→propose→pause → apply→pause → draft PR + archive; no auto fix commits)"
---

# issue-fixer

Triage and fix a GitHub issue following `.agents/skills/issue-fixer/SKILL.md`:

- When explore is required: **`/opsx-explore`** (no parallel in-skill explore)
- OpenSpec cadence: **create issue branch → `/opsx-propose` → pause → `/opsx-apply` → pause → draft PR +
  `/opsx-archive`**
- Create the branch **before** `/opsx-propose` so propose artifacts land on the issue branch and the user can commit
- OpenSpec is **only** for `/issue-fixer` — not `/review-fixer` or `/create-issue`
- Draft PR only after apply confirmation, when the tip has **real** commits ahead of `main` — never empty bootstrap
- Implement only in the working tree — do **not** auto-commit or auto-push fix commits
- Split deferred work via create-issue (`sub-of` vs `linked`)

Do not mark the PR ready.
