---
name: "/create-issue"
id: "create-issue"
category: "Workflow"
description: "Create GitHub issues from AI findings with org issue type + triage labels"
---

# create-issue

Create a new GitHub issue from an AI finding or discussion request.

This command classifies the issue (org issue type: `Bug`, `Security`, `Feature`, `Task`, `Discussion`, `Refactoring`)
and attaches triage labels (`severity:*` + `cost:*` required; `practicality:*` only when there is a defect path).
Missing allowlisted labels are created on demand. It does **not** re-run `/review-fixer` triage.

**Input:**

- A PR URL/number plus one finding summary (optional `severity`, `practicality`, `cost`, `type`, path), or
- Free-text “please create an issue for …”

**Steps**

1. Read and follow `.agents/skills/create-issue/SKILL.md`.
2. Use `docs/ai_review_policy.md` for severity / practicality / cost core definitions (see skill for issue extensions).
3. If `GH_TOKEN` is missing and there is no TTY, ask the user to run `source ./scripts/set-dev-tokens.sh` in a terminal
   and wait — do not paste tokens into chat.
4. Do not commit or push unless the user asks.
