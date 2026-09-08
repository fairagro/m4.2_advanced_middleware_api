---
name: create-issue
description: >-
  Creates a GitHub issue with one org issue type and triage labels (severity,
  optional practicality, cost), optionally as a GitHub sub-issue. Use when the
  user asks to /create-issue, open a follow-up from review-fixer, or split work
  from issue-fixer — not for implementing fixes.
---

# Create issue

Create (and only create) GitHub issues for deferred work or AI-driven discussion requests.

You are a **creator** (not fixer). Do not implement code changes. Do **not** re-run `/review-fixer` triage on PR review
threads. `/review-fixer` and `/issue-fixer` **may** invoke this skill with pre-filled triage — treat those as normal
creates.

## Input

Accept any of:

1. A PR number or URL plus a finding summary. The user may include triage fields in plain text:
   - `type: Bug|Security|Feature|Task|Discussion|Refactoring`
   - `severity: Blocker|High|Medium|Low`
   - `practicality: High|Medium|Low|None|seen-in-the-wild` (optional — see below)
   - `cost: cheap|medium|expensive`
   - affected `path:` sentences
   - `relation: sub-of #<issue_number> | linked` (optional; default `linked`)
2. Free text: “please create an issue for …” (no structured triage).
3. An invocation from `/review-fixer` with deferred Medium+ items (title usually
   `Follow-up from PR #<pr_number> AI review`).
4. An invocation from `/issue-fixer` for a split slice (title/body from the deferred block; typically
   `relation: sub-of #<issue_number>`).

If a PR is identifiable, you may fetch minimal context (e.g. changed files), but do not re-run full review-fixer triage
or issue-fixer explore. Prefer what the user or caller provided.

Do **not** commit or push unless the user asks.

## Auth (`gh`)

`gh` is wrapped (`scripts/bin/gh`, on `PATH` in the Dev Container via `remoteEnv`). Missing `GH_TOKEN` prompts on
`/dev/tty` and is saved to `/commandhistory/tokens.env` (Linux Dev Container only — see `docs/conventions.md`). The
wrapper sources `scripts/dev-tokens.sh` on each invoke (no `.bashrc` patch). Do not read tokens from the git worktree;
do not invent them. Never ask the user to paste a PAT into chat.

**Agent / no TTY:** `/dev/tty` is unavailable in chat, so the wrapper cannot prompt. Before skipping GitHub writes:

1. Tell the user `GH_TOKEN` is missing and that the agent cannot open an interactive prompt here.
2. Ask them to run in a **Dev Container / IDE terminal** (not chat):

   ```bash
   source ./scripts/set-dev-tokens.sh
   ```

   Then reply here when done (or decline).

3. After they confirm, retry `uv run m42-ai auth-status` (or `gh auth status`). If auth works, continue with label
   ensure + issue create.
4. Only if they decline or auth still fails: skip GitHub writes, print the draft title/body/type/labels, and stop.

Label create and issue create need a token that can write issues and labels on the target repo. If label create fails
with a permissions error, say so and suggest creating the allowlisted labels once in the GitHub UI (or broadening the
PAT).

## Decision inputs

Use [`docs/ai_review_policy.md`](../../../docs/ai_review_policy.md) for the core definitions of **severity**,
**practicality**, and **cost**. Do **not** copy review-fixer defaults blindly onto every new issue.

### Org issue type (exactly one)

GitHub **Issue Types** (not `kind:*` labels):

| Type          | When                                                                                                       |
| ------------- | ---------------------------------------------------------------------------------------------------------- |
| `Security`    | Credential/secret/PII leakage, unsafe authn/authz, or exploitable security weakness                        |
| `Bug`         | Wrong domain result, data loss/silent overwrite, broken API/HTTP contract, ownership/idempotency bypass    |
| `Feature`     | Intended new behaviour / capability                                                                        |
| `Task`        | Bounded follow-up: tech-debt, cleanup, docs, or a small actionable slice that is not a structural redesign |
| `Refactoring` | Multi-module or structural restructure (new abstractions, contract-preserving architecture change)         |
| `Discussion`  | Question, proposal, or ambiguous trade-off without a clear actionable change                               |

Do **not** use `Task` for major structural work — that is `Refactoring`.

### Severity (always attach exactly one)

Pick from the policy table (first match). **Anti-default:** never choose `severity:medium` merely because the work
“matters” or is a shared-tooling improvement.

| Org type                                       | Default when the user did not give severity                                                                                                                                           |
| ---------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `Feature`, `Task`, `Discussion`, `Refactoring` | **`severity:low`** — upgrade to **medium** only for a clear operator/CI break, broken documented cadence, or user-stated urgency; **high/blocker** only when the policy table matches |
| `Bug`, `Security`                              | Use the real policy severity — **do not** default to low or medium                                                                                                                    |

Parity gaps, missing CI gates, docs debt, and “nice to close” follow-ups are usually **low**, not medium.

### Practicality (attach only when there is a defect path)

In review policy, **practicality** answers: “How realistic is the path to the **bad state**?” It is **not** “can we
implement this issue?” Almost every Feature/Task is implementable — that must **not** become `practicality:high`.

| Situation                                                                                           | Action                                                                             |
| --------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| `Bug` / `Security`, or any item with a concrete path sentence to a bad outcome                      | Attach a `practicality:*` label; cite the path (or `seen-in-the-wild`)             |
| `Feature` / `Task` / `Discussion` / `Refactoring` with **no** defect path (improvement / work item) | **Omit** the practicality label; body triage: `practicality: n/a (no defect path)` |
| `/review-fixer` Medium+ follow-up                                                                   | Keep practicality from the deferred checklists (defect findings)                   |

Issue-oriented extensions:

- `practicality:seen-in-the-wild` — user provides evidence it already happens in real usage (logs, incidents, reports)
- `cost:medium` — between cheap and expensive for issue planning (review-fixer cost table is only `cheap|expensive`)

### Cost (always attach exactly one)

Estimate implementation/planning cost: `cheap` | `medium` | `expensive`.

## Triage label allowlist (create-if-missing)

Attach **only** labels from this allowlist. Before `gh issue create`, ensure each label you will attach exists. If
missing, create it with the fixed color/description below (`gh label create`). Never create free-text or off-allowlist
labels.

Required on every issue: one `severity:*` and one `cost:*`. `practicality:*` only when the Decision inputs say so.

| Label                           | Color     | Description                                |
| ------------------------------- | --------- | ------------------------------------------ |
| `severity:blocker`              | `#B60205` | Blocks merge / data loss / broken contract |
| `severity:high`                 | `#D93F0B` | Serious defect with a real path            |
| `severity:medium`               | `#FBCA04` | Important but not high-risk                |
| `severity:low`                  | `#0E8A16` | Nit / low urgency                          |
| `practicality:high`             | `#1D76DB` | Realistic path in this system              |
| `practicality:medium`           | `#5319E7` | Non-default / internal / admin path        |
| `practicality:low`              | `#C5DEF5` | Mostly excluded by types/invariants        |
| `practicality:none`             | `#EDEDED` | No real path / unsupported environment     |
| `practicality:seen-in-the-wild` | `#BFDADC` | Observed in real usage                     |
| `cost:cheap`                    | `#C2E0C6` | Small local fix                            |
| `cost:medium`                   | `#FEF2C0` | Moderate issue-planning cost               |
| `cost:expensive`                | `#F9D0C4` | Large or cross-cutting work                |

## Create via CLI

Prefer the plumbing CLI (still uses `gh` on `PATH` / `GH_TOKEN`):

```bash
# Improvement / Task with no defect path — omit --practicality
uv run m42-ai issue-create \
  --title "..." \
  --type Task \
  --severity severity:low \
  --cost cost:medium \
  --body-file /tmp/issue.md \
  [--parent 42]

# Bug / Security (or Task that closes a real failure mode) — include --practicality
uv run m42-ai issue-create \
  --title "..." \
  --type Bug \
  --severity severity:high \
  --practicality practicality:high \
  --cost cost:cheap \
  --body-file /tmp/issue.md
```

See [`scripts/ai/README.md`](../../../scripts/ai/README.md). Fall back to raw `gh` only if the CLI is unavailable in the
checkout.

### Relation: sub-of vs linked

Callers (or the user) may pass `relation`:

| Relation                                 | Meaning                                                                | Create behavior                                                                                    |
| ---------------------------------------- | ---------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| `sub-of #<issue_number>`                 | Still part of parent `#<issue_number>` acceptance criteria / done-when | `gh issue create ... --parent <issue_number>` (native sub-issue); also link parent under **Links** |
| `linked` (default if omitted or unclear) | Distinct follow-up                                                     | Standalone issue; put source issue/PR under **Links** only — do **not** set `--parent`             |

If native sub-issue attachment fails **before** any issue is created (unsupported `gh`, permissions, or API error that
left no issue URL), fall back to **one** linked create (body Links), report the failure clearly, and do **not** invent a
second create path outside this skill. If `gh issue create` (with or without `--parent`) already printed an issue URL /
number and a later step fails (labels, `--type`, parent mutation, network), **do not** create again — report the partial
failure and return the existing issue URL.

Example ensure + create pattern:

```bash
# For each allowlisted label NAME you will attach:
gh label list --json name --jq '.[].name' | grep -Fxq "$NAME" \
  || gh label create "$NAME" --color "${COLOR#\#}" --description "$DESC"

# Linked Task (no practicality):
gh issue create --title "..." --body-file /tmp/issue.md --label "severity:low" --label "cost:medium" --type Task

# Bug with defect path:
gh issue create --title "..." --body-file /tmp/issue.md --label "severity:high" --label "practicality:high" --label "cost:cheap" --type Bug

# Sub-issue of parent 42:
gh issue create --title "..." --body-file /tmp/issue.md --label "severity:low" --label "cost:cheap" --type Task --parent 42
```

(`--type` requires org Issue Types configured; if it fails, report clearly — provisioning types is out of skill scope.)

Use the current repo from context, or ask if the target repo is unclear.

## Issue body template

Body **must** be GitHub Markdown:

```markdown
## Type

Bug | Security | Feature | Task | Discussion | Refactoring

## Triage

- **severity:** …
- **practicality:** … (path / seen-in-the-wild evidence) **or** `n/a (no defect path)`
- **cost:** … (cheap | medium | expensive)

## Problem

<what is wrong / what we observed>

## Why not now?

<what prevents this from being handled in the original PR/dialogue>

## Acceptance criteria (suggested)

- <what “done” looks like>

## Links

- PR: …
- Parent / related issue: …
```

## Output to the user

Return:

- the created issue URL (or “skipped GitHub writes” plus the draft title/body)
- the selected org issue type
- the attached labels (note when practicality was omitted)
- the relation applied (`sub-of #<issue_number>` or `linked`), and whether `--parent` fell back to linked

## Guardrails

- Do not commit or push unless asked.
- Never rewrite/patch code; only create an issue (and allowlisted labels if missing).
- Do not default every issue to `severity:medium` + `practicality:high`.
- If correctness is unclear or the user provided no actionable content, ask a single follow-up question instead of
  creating a low-quality issue.
- If label create fails due to permissions, stop attaching that label path, explain, and still offer the draft.
