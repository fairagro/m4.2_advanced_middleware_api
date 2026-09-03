---
name: "/create-issue"
id: "create-issue"
category: "Workflow"
description: "Create GitHub issues from AI findings with org issue type + triage labels"
---

Create a new GitHub issue from an AI finding or discussion.

This command classifies the issue (org issue type) and attaches triage labels
(`severity:*`, `practicality:*`, `cost:*`) so follow-up work stays easy to
route and prioritize.

**Input:**
- Either: a PR URL/number plus one finding summary (optionally including
  `severity`, `practicality`, `cost`, `type`, and affected path)
- Or: a free-text “please create an issue for …” request

**Steps**

1. Read and follow `.agents/skills/create-issue/SKILL.md`.
2. Use `docs/ai_review_policy.md` for the authoritative definitions of
   `severity`, `practicality`, and `cost` (adapted to issues).
3. Do not commit or push unless the user asks.
