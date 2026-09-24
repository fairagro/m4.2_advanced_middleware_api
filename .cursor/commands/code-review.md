---
name: "/code-review"
id: "code-review"
category: "Workflow"
description: "First-party critical review of a local branch diff or GitHub PR"
---

# code-review

Produce a first-party critical review of a local `base...HEAD` diff (default base `main`) or a GitHub pull request.

**Output:** write a report under `/tmp` via `m42-ai` (body starts with `<!-- m42-ai:code-review -->`, numbered findings

- Findings index table); for a PR, publish a formal COMMENT Pull Request Review when auth works. Do not triage
  Copilot/Bugbot threads (use `/review-fixer`). Do not commit, push, or auto-approve.

**Input:** optional base ref, and/or PR number/URL.

**Steps**

1. Read and follow `.agents/skills/code-review/SKILL.md`.
2. Use `docs/ai_review_policy.md` for severity language; do not duplicate Ruff/mypy/Bandit/etc. findings.
3. Prefer `uv run --project scripts/ai m42-ai code-review-context|code-review-report-write|code-review-publish`.
4. If publishing to a PR and `GH_TOKEN` is missing with no TTY, ask the user to `source ./scripts/set-dev-tokens.sh` and
   wait — keep the `/tmp` report if auth fails.
