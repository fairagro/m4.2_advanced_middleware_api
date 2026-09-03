---
name: "/issue-fixer"
id: "issue-fixer"
category: "Workflow"
description: "Triage and fix GitHub Issues (Branch + PR, optional Split in sub-issues)"
---

Triage and fix GitHub Issues with local implementation.

1. Triage the issue based on its Type/labels (including `Security` and
   `Refactoring`).
2. Create a branch (`issue-<number>-...`).
3. Create a PR (including `Fixes #<issue_number>` in the PR body), without
   automatically pushing code changes (empty head branch + PR first, then
   local changes, then user-push).
4. If the changes become too large, create sub-issues and implement only
   the MVP slice in the PR.

**Input:** Issue number or Issue URL.

**Steps**
1. Read and follow `.agents/skills/issue-fixer/SKILL.md`.
2. Do not commit or push the fixing code unless the user asks; pushing an
   empty head branch for the PR is allowed.
