---
description: "Create a GitHub issue from an AI finding with org issue type + triage labels"
---

Create a new GitHub issue from an AI finding or discussion request.

Follow `.agents/skills/create-issue/SKILL.md` to:
- choose exactly one org issue type (`Bug`, `Security`, `Feature`, `Task`, `Discussion`)
- attach triage labels (`severity:*`, `practicality:*`, `cost:*`)

Use `docs/ai_review_policy.md` as the authoritative definitions for
`severity`, `practicality`, and `cost`.

Do not commit or push unless the user asks.
