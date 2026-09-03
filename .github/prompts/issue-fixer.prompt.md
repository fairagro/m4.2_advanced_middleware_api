---
description: "Triage and fix GitHub Issues (Branch + PR + optional sub-issues)"
---

Triage and fix GitHub Issues following the Policy in the Issue-Fixer Skill:

- Create a branch with the issue number in the name
- Push an empty head branch and open a PR (PR body includes `Fixes #<n>`)
- Local fix changes only in the working tree (do not automatically push)
- For large changes, create sub-issues and implement only the MVP slice in the PR

Do not commit or push unless the user asks.
