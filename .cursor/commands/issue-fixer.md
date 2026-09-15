---
name: "/issue-fixer"
id: "issue-fixer"
category: "Workflow"
description: "Triage and fix a GitHub issue (OpenSpec for Feature/Refactoring; Task/Bug fast path; draft PR after real commits)"
---

# issue-fixer

Triage and fix a GitHub issue. Explore in-skill when required. **Feature / Refactoring:** issue branch → propose → pause
→ apply → pause → draft PR → archive (last `go`), **except** a clearly docs-only slice (Markdown/comments, no skill file
— Markdown under `openspec/specs/` or `openspec/changes/` is **not** docs-only) which uses the Bug path. **Task / Bug /
cheap Security:** issue branch → implement → pause → draft PR (no OpenSpec unless asked or a skill file is in scope). Do
**not** auto-commit fix commits. Do **not** use empty bootstrap commits; open the draft PR only after real commits exist
ahead of `main`. `/review-fixer` and `/create-issue` do **not** run OpenSpec.

**Input:** Issue number or URL.

**Steps**

1. Read and follow `.agents/skills/issue-fixer/SKILL.md`.
2. When explore is required (`Feature` / `Refactoring`, or unclear Bug/Security/Task / user asks): explore in-skill.
   Wait for lock-in / `go` / `skip explore`. Do **not** invoke `/opsx-explore`.
3. Create `issue-<n>-<slug>` from `main` **before** propose or implement.
4. OpenSpec types: follow `.cursor/skills/openspec-propose/SKILL.md` → pause → on `go` follow
   `.cursor/skills/openspec-apply-change/SKILL.md` → pause. Task/Bug path **or** clearly docs-only Feature/Refactoring
   (Markdown/comments, no skill file; not `openspec/specs/` or `openspec/changes/`): implement in the working tree →
   pause.
5. On continue: ensure **draft** PR (tip already ahead of `main`). No `Made with Cursor` footers.
6. OpenSpec types, last `go`: follow `.cursor/skills/openspec-archive-change/SKILL.md` → pause for the user to commit.
7. Deferred splits via `/create-issue` (`relation: sub-of` / `linked`) — create-issue itself does **not** run OpenSpec.
8. If `GH_TOKEN` is missing and there is no TTY, ask the user to run `source ./scripts/set-dev-tokens.sh` in a terminal
   and wait — do not paste tokens into chat.
