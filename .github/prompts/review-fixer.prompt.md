---
description: "Triage Copilot/Bugbot PR review comments: fix, dismiss, or bundle a follow-up"
---

# review-fixer

Triage GitHub Copilot and Cursor Bugbot review comments using the project AI review policy. Fix high-risk findings and
in-budget nits; dismiss the rest; at most one follow-up issue.

When a PR is known, process **open** work only: unresolved AI threads plus findings in the latest Copilot/Bugbot review
body that have no thread (including Copilot “Suppressed comments”). Do not re-triage resolved threads.

**Input:** PR number or URL, optional review permalink, or pasted comments.

Read and follow `.agents/skills/review-fixer/SKILL.md`. Use `docs/ai_review_policy.md` as the decision source of truth.
Do not commit or push. When fixes need a SHA, pause for the user to commit, then post `Fixed in <sha>.` replies.
