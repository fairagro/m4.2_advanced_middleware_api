---
name: "/review-fixer"
id: "review-fixer"
category: "Workflow"
description: "Triage Copilot/Bugbot PR review comments: fix, dismiss, or bundle a follow-up"
---

Triage GitHub Copilot and Cursor Bugbot review comments using the project
AI review policy. Fix high-risk findings and in-budget nits; dismiss the
rest; at most one follow-up issue.

**Input:** PR number or URL, or pasted review comments.

**Steps**

1. Read and follow `.agents/skills/review-fixer/SKILL.md`.
2. Use `docs/ai_review_policy.md` as the decision source of truth.
3. Do not commit or push unless the user asks.
