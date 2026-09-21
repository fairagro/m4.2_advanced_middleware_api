---
description: "First-party critical review of a local branch diff or GitHub PR"
---

# code-review

Produce a first-party critical review of a local branch diff or GitHub pull request.

Follow `.agents/skills/code-review/SKILL.md` to:

- gather context via `uv run --project scripts/ai m42-ai code-review-context`
- apply the judgment checklist (security, correctness, architecture, …) without duplicating quality-toolchain findings
- write `/tmp` via `code-review-report-write`; publish a COMMENT PR Review via `code-review-publish` when a PR is known

Do not triage Copilot/Bugbot threads (`/review-fixer`). Do not commit, push, or auto-approve.
