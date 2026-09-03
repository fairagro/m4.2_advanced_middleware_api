# AI Review Policy

How this repository treats GitHub Copilot code review and Cursor Bugbot
findings. This file is the single policy. Copilot loads it via
`.github/copilot-instructions.md`; Bugbot via `.cursor/BUGBOT.md`; the
local fixer via `/review-fixer`.

Two channels:

| Channel | Re-review | Must fix |
| ------- | --------- | -------- |
| **Risk** (Blocker/High, practicality not Low) | stays open every round | yes, if the finding is correct and in this PR |
| **Nit** (Low, or Medium with expensive/out-of-scope fix) | finders may still comment | only while nit-budget remains |

Merge criterion: no open **risk** findings. Dismissed nit threads are not a
merge blocker. Do not loop until “0 Copilot comments”.

---

## Roles

1. **Finder** (Copilot on GitHub, Bugbot): high recall. Skip the classes below.
   Label severity, cite a reachable path, do not widen types in suggested
   patches. Finders do **not** apply nit-budget.
2. **Fixer** (`/review-fixer`): precision and policy. Re-evaluates every thread,
   then `fix`, `dismiss`, or (rarely) `follow-up`.
3. **Human**: samples the fixer’s path sentences and owns the merge.

Every thread is **triaged**. Triage is not the same as implementing. Valid
outcomes: fix in this PR, dismiss with a one-line reason, or one bundled
follow-up issue for the whole PR.

---

## Finder instructions (Copilot and Bugbot)

High recall for real bugs. Do **not** apply nit-budget. Do not implement
fixes.

**Report**

- Wrong results, data loss/overwrite, broken `/v3` contracts, secrets in
  logs, races on CouchDB documents
- Swallowed errors, bad idempotency/409, ownership bypass, leaks on Git or
  Couch hot paths
- New behaviour with no test

Each comment **must** include:

1. **Severity:** `Blocker` | `High` | `Medium` | `Low` (table below; first
   match; do not upgrade on vibe)
2. **Path sentence:** public route / Celery task / real config → function →
   bad state. No path → do not comment
3. A patch only if it **narrows** types or is a local correction

**Do not comment on**

- Ruff, MyPy, Pylint, Bandit, formatting, import order, naming-only
- `None` guards on Pydantic-validated models or `ConfigWrapper` values
- Extra abstractions, wrappers, or DRY for a single call site
- Drive-by issues in files/hunks this PR did not change, unless Blocker
- Theoretical weaknesses with no reachable path in this API/worker
- Suggested `T | None`, `Any`, or `if x is None` when the type already
  excludes `None`

If nothing in **Report** applies, leave no comment. Prefer fewer,
higher-severity comments.

---

## Decision order (fixer)

Stop at the first matching step.

1. **Correct?** If the diagnosis is wrong, already covered by types/Pydantic/
   `ConfigWrapper`/a spec invariant, or Ruff/MyPy/Pylint/Bandit already gate
   it → `dismiss`.
2. **This PR?** If it is drive-by on unchanged code, another module, or
   speculative hardening the change does not need → `dismiss` or `follow-up`
   (only if Medium+).
3. **Cheapest correct fix?** Prefer a narrower type, a cited invariant, or an
   existing helper over the finder’s patch. Widening a type is not a fix
   (see [Types](#types)).
4. **Risk.** Severity Blocker/High **and** practicality not Low → `fix`.
   Nit-budget does not apply. If the fix itself is a separate feature, split
   or `follow-up` instead of bloating this PR.
5. **Nit.** Otherwise treat as a nit:
   - cost **cheap** and nit-budget remaining → `fix`
   - else → `dismiss` (Low) or `follow-up` (Medium+ only)

If the cheaper fix is unclear, default to `dismiss` rather than adding a
layer.

---

## Severity (pick the first match; do not upgrade on vibe)

| Level | When (any one) |
| ----- | -------------- |
| **Blocker** | Wrong domain result; data loss or silent overwrite; broken HTTP/API contract; secret/credential in logs or persistence; documented race that can clobber a document |
| **High** | Error swallowed (empty `except`, success status on failure); idempotency/409 wrong; authz/ownership bypass; resource leak on a hot path (Git cache, Couch session) |
| **Medium** | New behaviour with no test; error path that misleads operators; duplication that will diverge |
| **Low** | Naming, comments, extra abstraction, defensive check inside already-validated data, micro-DRY |

If nothing matches Blocker/High/Medium → **Low**.

---

## Practicality (requires a path sentence)

Practicality is not “we have seen this in prod”. It is “a realistic path
exists in *this* system”.

| Level | Rule |
| ----- | ---- |
| **High** | Cite entry → function → bad state. Entry is a public route (`/v3/...`), a Celery task, or a config field set by default / `dev_environment/config.yaml`. |
| **Medium** | Only with non-default config, an internal caller, or admin. |
| **Low** | State is excluded by Pydantic, `ConfigWrapper`, annotations, or a spec invariant — **quote the invariant**. |
| **None** | False positive; the alleged path does not exist. |

If the fixer cannot write a path sentence, practicality is **Low**, not High.

Risk is high only when severity is Blocker/High **and** practicality is not
Low/None.

---

## Cost (estimate *before* coding, on the chosen fix)

Do not use `git diff --stat` of a patch that does not exist yet. Estimate the
fix you would actually apply, not the finder’s suggested patch.

| Signal | Cheap | Expensive |
| ------ | ----- | --------- |
| New production lines | 0 or &lt;15 | 15–50 (grey) / &gt;50 |
| New abstraction | no | new class, helper, or module |
| Types | same or **narrower** | wider (`T \| None`, `Any`, untyped dict) |
| Scope | one function, one file | multiple modules / extra responsibility |

**Expensive** if any of: new abstraction, wider type, multiple modules, &gt;50
prod lines. A new helper with no second call site is expensive even at 20
lines.

### What counts as production size

- **Counts:** runtime code under `middleware/*/src/`.
- **Does not count:** tests that lock **real** behaviour (regression for a
  real bug, endpoint contract). Tests that encode a hypothetical state the
  types already forbid **do** count as bloat — do not add them.
- **Specs:** may grow when they record a contract the code now actually has.
  Do not add spec text for a theoretical weakness. Spec growth is not the
  production size budget; still apply risk vs cost.

---

## Nit-budget

A **nit** is a correct (or plausible) finding that is **not** high risk.

Budget (fixer only):

1. **Round 1** (first Copilot/Bugbot review on this PR): cheap nits may be
   fixed until **~25 new production lines** from nit-fixes, and **never** a
   new abstraction.
2. **Round 2+**: nits only on surface **introduced by the previous fixer
   pass** (regression of those fixes). Nits on already-reviewed surface →
   `dismiss` (`nit-budget`).
3. Risk findings are **never** budgeted. A Blocker/High with a real path in
   round 3 is still a must-fix.

Round count = number of Copilot and/or Bugbot review submissions on the PR,
not “how many comments”.

---

## Types

These rules apply to writing code and to reviewing it
(`openspec/principles.md` Type Safety).

- Do **not** widen a type to silence a finding (`T` → `T | None`, `Any`,
  `dict[str, Any]`). That is a new defect, not a fix.
- Do **not** add `if x is None` / `x or default` when the annotation,
  Pydantic model, or `ConfigWrapper` already excludes `None`.
- If `None` is genuinely required, make the **source** optional and update
  every caller. Do not insert a local guard in the middle of the pipeline.
- Prefer a narrower type, an existing helper, or a quoted invariant over a
  new wrapper or retry layer.

---

## Follow-up issues

- At most **one** follow-up issue per PR.
- Include only deferred items that are **Medium or higher**.
- Low nits that miss the budget get a dismissal reply, not an issue.
- Title: `Follow-up from PR #<n> AI review`. Body: bullet list of deferred
  findings with path, severity, practicality, and why they are out of this
  PR.

---

## Fixer reply format

Reply on the thread, then resolve:

```text
fix | dismiss | follow-up
correct: yes/no
severity: …
practicality: … (path or invariant)
cost: cheap|expensive (chosen fix, not the suggestion)
reason: …
```

If the chosen fix differs from the suggestion, say what you did instead
(e.g. “narrowed return type of `Foo.bar` instead of adding a None-guard”).
