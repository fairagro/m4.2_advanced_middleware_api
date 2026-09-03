# Create issue

Create (and only create) GitHub issues for deferred work items or AI-driven
discussion requests.

You are a **creator** (not fixer). Do not implement code changes.

## Input

Accept any of:

1. A PR number or URL plus a finding summary.
   The user may additionally include triage fields in plain text:
   - `type: Bug|Security|Feature|Task|Discussion|Refactoring`
   - `severity: Blocker|High|Medium|Low`
   - `practicality: High|Medium|Low|None|Seen in the wild`
   - `cost: cheap|medium|expensive`
   - affected `path:` sentences
2. Free text: “please create an issue for …” (no structured triage).

If a PR is identifiable, you may fetch minimal context (e.g. changed files),
but do not re-run the full review-fixer triage on every comment. Prefer what
the user provided.

## Decision inputs (use as scoring axes)

Use `docs/ai_review_policy.md` for the definitions of:

- `severity`
- `practicality`
- `cost`

### Issue type (org-wide)

Pick exactly one org issue type:

- `Security`: credential/secret/PII leakage, unsafe authn/authz, or exploitable
  security weakness
- `Bug`: wrong domain result, data loss/silent overwrite, broken API/HTTP
  contract, or ownership/idempotency bypass
- `Feature`: intended new behavior / capability addition
- `Task`: refactor/tech-debt/cleanup/docs improvements needed to implement the
  above
- `Refactoring`: major internal architecture/structure change (multiple
  modules, new abstractions, or contract-preserving restructuring)
- `Discussion`: question, proposal, or ambiguous trade-off without a clear
  actionable change

### Practicality for issues (labels)

Convert practicality into a label value:

- `practicality:high` if a realistic path exists in this system (cite the path)
- `practicality:medium|low|none` otherwise
- `practicality:seen-in-the-wild` if the user provides evidence it already
  happens in real usage (logs, incident reports, user reports)

## Labels to attach

Attach these triage label families (create them if missing):

- `severity:blocker|high|medium|low`
- `practicality:high|medium|low|none|seen-in-the-wild`
- `cost:cheap|medium|expensive`

## GitHub auth + creation

`gh` is wrapped (`scripts/bin/gh`, on PATH in the Dev Container). If auth is
missing and there is no TTY, `gh` should skip GitHub writes.

When you create an issue:

- Use the current repo from context (or ask the user if the target repo is
  unclear).
- Title: concise, user-facing.
- Body: include the triage block at the top, then a clear description.

### Issue body template

```text
Type: Bug|Security|Feature|Task|Discussion|Refactoring

Triage
- severity: ...
- practicality: ... (path or “seen-in-the-wild” evidence)
- cost: ... (cheap|medium|expensive)

Problem
<what is wrong / what we observed>

Why not now?
<what prevents this from being handled in the original PR/dialogue>

Acceptance criteria (suggested)
<what “done” looks like>

Links
- PR: ...
```

## Output to the user

Return:

- the created issue URL (or “skipped GitHub writes” plus the draft title/body)
- the selected org issue type
- the attached labels

## Guardrails

- Do not commit or push.
- Never rewrite/patch code; only create an issue.
- If correctness is unclear or the user provided no actionable content,
  ask a single follow-up question instead of creating a low-quality issue.
