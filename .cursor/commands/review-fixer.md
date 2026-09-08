---
name: "/review-fixer"
id: "review-fixer"
category: "Workflow"
description: "Triage Copilot/Bugbot PR review comments: fix, dismiss, or bundle a follow-up"
---

# review-fixer

Triage GitHub Copilot and Cursor Bugbot review comments using the project AI review policy. Fix high-risk findings and
in-budget nits; dismiss the rest; at most one follow-up issue.

When a PR is known, process **open** work only: unresolved AI threads plus findings in the latest Copilot/Bugbot review
body that have no thread (including Copilot “Suppressed comments”). Do not re-triage resolved threads.

**Two phases when anything is `fix`:** (1) local fixes + immediate dismiss/follow-up replies — **no commit**; pause for
your commit. (2) after you commit, `Fixed in <sha>.` + resolve. Dismiss/follow-up-only runs finish in phase 1.

**Input:** PR number or URL, optional review permalink, or pasted comments. After a pause, “continue” / a SHA resumes
phase 2.

**Steps**

1. Read and follow `.agents/skills/review-fixer/SKILL.md`.
2. Use `docs/ai_review_policy.md` as the decision source of truth.
3. If a PR is known: fetch once, triage open work only, reply/resolve as the skill specifies. If `GH_TOKEN` is missing
   and there is no TTY, ask the user to run `source ./scripts/set-dev-tokens.sh` in a terminal and wait — do not paste
   tokens into chat.
4. Do not commit or push. Ask the user to commit fixes; use their SHA only in phase-2 Fixed replies.
