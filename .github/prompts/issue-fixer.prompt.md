---
description: "Triage and fix a GitHub issue (branch → implement → pause → draft PR; no OpenSpec; no auto fix commits)"
---

# issue-fixer

Triage and fix a GitHub issue following `.agents/skills/issue-fixer/SKILL.md`:

- When explore is required: explore **in-skill** (no `/opsx-explore`)
- Cadence: **create issue branch → implement → pause → draft PR**
- Do **not** run OpenSpec (`/opsx-*`) as part of `/issue-fixer` (same for `/review-fixer` / `/create-issue`)
- Draft PR only after implement confirmation, when the tip has **real** commits ahead of `main` — never empty bootstrap
- Implement only in the working tree — do **not** auto-commit or auto-push fix commits
- Split deferred work via create-issue (`sub-of` vs `linked`)

Do not mark the PR ready.
