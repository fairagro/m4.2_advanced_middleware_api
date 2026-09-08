# Create-issue conventions

Shared `/create-issue` classifies new GitHub issues for the m4.2 product repos and this Devinfra repo. Canonical skill:
[`.agents/skills/create-issue/SKILL.md`](../.agents/skills/create-issue/SKILL.md). `/review-fixer` and `/issue-fixer`
use the same skill for deferred work (follow-ups and splits).

Issue: [#14](https://github.com/fairagro/m4.2_middleware_devinfra/issues/14).

## Org issue types

Use GitHub **Issue Types** (org-configured), not `kind:*` labels. Pick exactly one:

| Type          | Use for                                                                 |
| ------------- | ----------------------------------------------------------------------- |
| `Bug`         | Wrong results, data loss, broken contracts                              |
| `Security`    | Secrets/PII leakage, authz/authn weakness                               |
| `Feature`     | New intended capability                                                 |
| `Task`        | Bounded follow-up (tech-debt, cleanup, docs) — not major structure work |
| `Refactoring` | Multi-module / structural restructure                                   |
| `Discussion`  | Open question or trade-off without a clear change                       |

Provisioning the types in the GitHub org is out of band (org admin).

## Triage labels

Allowlisted families (created on demand by `/create-issue` if missing — one-shot per repo):

- `severity:blocker|high|medium|low` — **required**
- `cost:cheap|medium|expensive` — **required**
- `practicality:high|medium|low|none|seen-in-the-wild` — **only** when there is a concrete path to a **bad outcome**
  (typical for `Bug` / `Security`, or review-fixer deferrals). Omit for Feature/Task/Discussion/Refactoring work items
  with no defect path; do **not** set `practicality:high` just because the work is implementable.

Core meanings come from [`ai_review_policy.md`](ai_review_policy.md). Issue-only extensions and defaults (see the
skill):

- `Feature` / `Task` / `Discussion` / `Refactoring` default **`severity:low`** unless there is a clear operator/CI break
  or the user sets urgency — never default to medium “because it matters”
- `practicality:seen-in-the-wild`, `cost:medium`

Do **not** invent other triage label names in the skill. Free-text labels are forbidden.

Prefer `uv run m42-ai issue-create …` (see [`scripts/ai/README.md`](../scripts/ai/README.md)); `--practicality` is
optional.

## Relation: sub-of vs linked

Callers pass a relation when opening deferred work:

| Relation                 | When                                                                                                              | Effect                                               |
| ------------------------ | ----------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------- |
| `sub-of #<issue_number>` | New work is still part of parent `#<issue_number>` acceptance criteria / done-when (typical `/issue-fixer` split) | GitHub native sub-issue (`gh issue create --parent`) |
| `linked`                 | Distinct follow-up problem (typical `/review-fixer` deferral; “discovered while …”)                               | Standalone issue; Links in the body only             |

Unclear → prefer **linked**. If `--parent` fails **and no issue was created**, fall back to one linked create and report
the error. If an issue URL already exists and a later step fails, do **not** create a second issue.

## Auth

Same personal-token helpers as `/review-fixer` — see root README **Personal tokens** and `scripts/bin/gh`.
