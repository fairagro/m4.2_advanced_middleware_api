---
description: "Triage Copilot/Bugbot/code-review PR comments: fix, dismiss, or bundle a follow-up"
---

# review-fixer

Triage GitHub Copilot, Cursor Bugbot, and first-party `/code-review` comments using the project AI review policy. Fix
high-risk findings and in-budget nits; dismiss the rest; at most one follow-up issue.

When a PR is known, process **open** work only: unresolved review threads (**any** author) plus summary-only /
suppressed findings (Copilot “Suppressed comments” **and** `/code-review` marked COMMENT bodies — no inline thread). Do
not re-triage resolved threads.

**Input:** PR number or URL, optional review permalink, or pasted comments.

Read and follow `.agents/skills/review-fixer/SKILL.md`. Use `docs/ai_review_policy.md` as the decision source of truth.
Do not commit or push. When fixes need a SHA, pause for the user to commit, then post `Fixed in <sha>.` replies.
