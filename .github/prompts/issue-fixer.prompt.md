---
description: "Triage and fix a GitHub issue (OpenSpec for Feature/Refactoring; Task/Bug fast path; no auto fix commits)"
---

# issue-fixer

Triage and fix a GitHub issue following `.agents/skills/issue-fixer/SKILL.md`:

- When explore is required: explore **in-skill** (no `/opsx-explore`)
- **Feature / Refactoring:** issue branch → follow openspec-propose → pause → apply → pause → draft PR → archive (last
  `go`). **Docs-only** (Markdown/comments only, no skill file): same as Bug path — no OpenSpec. Markdown under
  `openspec/specs/` or `openspec/changes/` is **not** docs-only
- **Task / Bug / cheap Security:** issue branch → implement → pause → draft PR (no OpenSpec unless the user asks or a
  skill file is in scope)
- Misfiled Task that clearly changes `openspec/specs/`: pause once (retype Feature or `use opsx`)
- `/review-fixer` and `/create-issue` do **not** run `/opsx-*`
- Real delta specs when a capability contract changes; `skip_specs: true` only for docs/tooling with no spec delta
- Draft PR only when the tip has **real** commits ahead of `main` — never empty bootstrap
- Implement only in the working tree — do **not** auto-commit or auto-push fix commits
- Split deferred work via create-issue (`sub-of` vs `linked`)

Do not mark the PR ready.
