# Code-review conventions

Shared `/code-review` produces a first-party critical review of a local branch diff (default base `main`) or a GitHub
pull request. Canonical skill: [`.agents/skills/code-review/SKILL.md`](../.agents/skills/code-review/SKILL.md). Policy
language: [`ai_review_policy.md`](ai_review_policy.md).

Issue: [#171](https://github.com/fairagro/m4.2_middleware_devinfra/issues/171) (Discussion
[#140](https://github.com/fairagro/m4.2_middleware_devinfra/issues/140)).

## Relationship

| Skill           | Role                                                                       |
| --------------- | -------------------------------------------------------------------------- |
| `/code-review`  | **Produce** a first-party review (numbered findings with **Path** bullets) |
| `/review-fixer` | **Consume** Copilot/Bugbot threads **and** `/code-review` summaries        |
| `/create-issue` | Optional hand-off for Medium+ deferrals                                    |

## Inputs / outputs

- **Local:** `m42-ai code-review-context --base main` → review → `code-review-report-write` → `/tmp/code-review-*.md`
  (no GitHub write). Report body MUST start with `<!-- m42-ai:code-review -->` and use **numbered finding blocks** with
  a **Path** bullet each (no Findings index table). `/review-fixer` extracts from those Path bullets; legacy table-only
  bodies remain readable by the extractor.
- **PR:** same checklist; `code-review-publish --pr N` submits a formal COMMENT Pull Request Review
  (`gh pr review --comment`). Falls back to a conversation comment only if review submit fails.

## Anti-duplication

Do not restate findings owned by Ruff, mypy, pylint, Bandit, markdownlint, Prettier, ggshield, CodeQL, Trivy,
**vulture**, or **import-linter**. Mechanical unused definitions are vulture’s; mechanical cycle/layer/forbidden
violations are import-linter’s. Keep judgment-only notes for Import-policy rules outside the linter (module-level
imports, relative imports, `sys.path` mutation, lazy imports used only to break cycles) — see
[`openspec/principles.global.md`](../openspec/principles.global.md) **Import policy**.

## Auth

Same personal-token helpers — see root README **Personal tokens** and `scripts/bin/gh`. Prefer
`uv run --project scripts/ai m42-ai …`.
