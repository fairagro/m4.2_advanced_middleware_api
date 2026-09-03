---
name: "/review-fixer"
id: "review-fixer"
category: "Workflow"
description: "Triage Copilot/Bugbot PR review comments: fix, dismiss, or bundle a follow-up"
---

Triage GitHub Copilot and Cursor Bugbot review comments using the project
AI review policy. Fix high-risk findings and in-budget nits; dismiss the
rest; at most one follow-up issue.

When a PR is known, process **open** work only: unresolved AI threads
plus findings in the latest Copilot/Bugbot review body that have no
thread (including Copilot “Suppressed comments”). Do not re-triage
resolved threads. Reply and resolve threads when `gh` can; for
summary-only items, comment on the PR conversation instead.

**Input:** PR number or URL, optional review permalink, or pasted
comments.

**Steps**

1. Read and follow `.agents/skills/review-fixer/SKILL.md`.
2. Use `docs/ai_review_policy.md` as the decision source of truth.
3. If a PR is known: fetch once, triage open work only, reply/resolve as
   the skill specifies.
4. Do not commit or push unless the user asks.
