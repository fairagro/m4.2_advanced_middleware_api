# AI Review Policy

How shared m4.2 middleware repositories treat GitHub Copilot code review and Cursor Bugbot findings. This file is the
single policy. Copilot loads it via `.github/copilot-instructions.md`; Bugbot via `.cursor/BUGBOT.md`; the local fixer
via `/review-fixer`.

Two channels:

| Channel                                                  | Re-review                 | Must fix                                      |
| -------------------------------------------------------- | ------------------------- | --------------------------------------------- |
| **Risk** (Blocker/High, practicality not Low)            | stays open every round    | yes, if the finding is correct and in this PR |
| **Nit** (Low, or Medium with expensive/out-of-scope fix) | finders may still comment | only while nit-budget remains                 |

Merge criterion: no open **risk** findings. Dismissed nit threads are not a merge blocker. Do not loop until “0 Copilot
comments”.

**Risk** (merge channel) means the fixer’s private checklist: severity **Blocker or High** **and** practicality **not**
Low/None. Copilot/Bugbot banners (“Needs a closer look”, “Changes recommended”) are **not** risk. Risk is **not**
`severity × practicality`; Medium + High practicality is often a step-5 fix but is **not** risk.

**Fixed non-nit this run** means the count of open-work items in **this** `/review-fixer` invocation with action `fix`
that are **not** nits: Risk (step 4) and step-5 (cheap + High practicality + Medium+) fixes. Nit-budget fixes,
dismissals, and follow-ups do **not** count. The count is per run (not accumulated across the PR).

**Review-cycle abort criterion:** After a `/review-fixer` run reports **Fixed non-nit this run: 0**, **stop the cycle**
— do not request another finder pass or another `/review-fixer` solely because comments remain, Remaining risk is
already 0, or only nits/dismissals happened. If **Fixed non-nit this run ≥ 1**, the cycle may continue (another finder
pass is allowed after the fixes land). Optional exception: **at most one** deliberate nit-only pass while nit-budget
remains even when Fixed non-nit would be 0; after that pass (or if skipped), the same abort applies. Resume when new
open work appears that the fixer would non-nit-fix, or a human explicitly asks.

---

## Roles

1. **Finder** (Copilot on GitHub, Bugbot): high recall. Skip the classes below. Label severity, cite a reachable path,
   do not widen types in suggested patches. Finders do **not** apply nit-budget.
2. **Fixer** (`/review-fixer`): precision and policy. Re-evaluates every thread, then `fix`, `dismiss`, or (rarely)
   `follow-up`.
3. **Human**: samples the fixer’s path sentences and owns the merge.

Every thread is **triaged**. Triage is not the same as implementing. Valid outcomes: fix in this PR, dismiss with a
one-line reason, or one bundled follow-up issue for the whole PR.

---

## Finder instructions (Copilot and Bugbot)

High recall for real bugs. Do **not** apply nit-budget. Do not implement fixes.

**Report**

- Wrong results, data loss/overwrite, broken public API or documented contracts, secrets in logs, races that can clobber
  persisted state
- Swallowed errors, bad idempotency / conflict handling, ownership or authz bypass, resource leaks on hot paths
- New behaviour with no test

Each comment **must** include:

1. **Severity:** `Blocker` | `High` | `Medium` | `Low` (table below; first match; do not upgrade on vibe)
2. **Path sentence:** public route / worker or async task / real default config → function → bad state. No path → do not
   comment
3. A patch only if it **narrows** types or is a local correction

**Do not comment on**

- Ruff, MyPy, Pylint, Bandit, Prettier/markdownlint, hadolint, formatting, import order, naming-only
- `None` guards on Pydantic-validated models or values already excluded by the project's config wrapper
- Extra abstractions, wrappers, or DRY for a single call site
- Drive-by issues in files/hunks this PR did not change, unless Blocker
- Theoretical weaknesses with no reachable path in this service / worker
- Suggested `T | None`, `Any`, `object`, or `if x is None` when the type already excludes `None`
- macOS, Homebrew, Windows, BSD/non-GNU userland differences, host `PATH` layouts, or any failure mode that only appears
  **outside** the Linux Dev Container (and is not GitHub Actions Linux CI) — see
  [`openspec/principles.global.md`](../openspec/principles.global.md) Supported development environment. That includes
  “fix the compatibility fallback” comments when the primary path already works in the Dev Container.
- **Unofficial host checkout docs:** missing `npm install` / “put `pre-commit` on `PATH`” / other host-only prerequisite
  wording when the supported path is the Dev Container (tools already present or loaded via `uv run`).
- **Config / YAML style-only** on shared Devinfra hooks (e.g. pre-commit `entry` vs `args` split, table path-prefix
  consistency) when the documented Dev Container or CI command still works.
- **Docs / comment clarification** when the supported path and fail bar already work (e.g. explaining that CI logs LOW
  while hooks use `-ll`, or aligning a comment with existing CI behaviour). Prefer silence unless the written command or
  config path is wrong.
- **Re-hardening an intentional happy-path simplification** (e.g. postCreate `bashrc` marker edge cases after the repo
  deliberately dropped exotic repair branches) — do not ask to restore speculative hardening.
- **One-shot local migration / ephemeral developer state:** a format or file that exists only on one machine or volume
  during a brief cutover (e.g. pre-`b64:` lines in a personal `tokens.env` that the author can re-prompt once), is not a
  shipped lasting contract, and is not the default path for new writes. Do not ask for compatibility parsers,
  deny-lists, or migration branches for that.

If nothing in **Report** applies, leave no comment. Prefer fewer, higher-severity comments.

---

## Decision order (fixer)

Stop at the first matching step.

1. **Correct? / supported environment? / one-shot local state?** If the diagnosis is wrong, already covered by types /
   Pydantic / the config wrapper / a spec invariant, or Ruff/MyPy/Pylint/Bandit/Prettier/markdownlint/hadolint already
   gate it → `dismiss`. **Also `dismiss` (practicality None)** when the only realistic bad path is outside the supported
   environment — quote [`openspec/principles.global.md`](../openspec/principles.global.md) “Supported development
   environment”. Apply this even if the finding is locally “correct” on that unsupported path, the suggested fix is
   cheap, or the code already has a defensive fallback for it. Examples: macOS / Windows / Homebrew; BSD vs GNU flag
   differences (e.g. `base64` without `-w0`); host `PATH` layouts the Dev Container does not use; unofficial
   bare-Linux-without-container runs; **host-only prerequisite docs** (`npm`/`PATH` for tools the Dev Container already
   provides). Do **not** take step 5 merely because a host-only hardening is one line. GitHub Actions Linux CI **is** in
   scope — do not dismiss solely as “host” when the path is Actions. **Also `dismiss` (practicality None)** when the
   finding only targets a **one-shot local migration** or ephemeral developer state: an old on-disk format that is not
   the current write path, is not a shipped consumer contract, and is fixed by the developer re-running a documented
   setup command once (e.g. legacy personal `tokens.env` lines before `b64:`). Do not add compatibility parsers, `eval`
   deny-lists, or migration branches for that — tell the author to re-prompt / recreate the file instead. **Also
   `dismiss`** requests to **re-harden** shared Devinfra / agent plumbing after an **intentional happy-path
   simplification** in this PR (marker repair, exotic `bashrc` branches, dual host token stores, etc.) unless the
   documented Dev Container path is actually broken.
2. **This PR?** If it is drive-by on unchanged code, another module, or speculative hardening the change does not need →
   `dismiss` or `follow-up` (only if Medium+). **Synced path (product consumers) — before steps 3–5:** If the finding’s
   primary path is on [`docs/synced-paths.yaml`](synced-paths.yaml) (or a matching glob) **and** the checkout is a product
   consumer (not Devinfra), **sync source of truth overrides** cheap/`fix` in this PR. Do **not** patch the synced tree.
   Use `follow-up` to Devinfra when the finding is correct for shared content and severity is Medium+, or Risk, or
   seen-in-the-wild; otherwise `dismiss` (“synced path — edit upstream in Devinfra / wait for sync”); or `fix` only a
   **documented product-local overlay** from that allowlist. See [Synced paths](#synced-paths-sync-source-of-truth).
3. **Cheapest correct fix?** Prefer a narrower type, a cited invariant, or an existing helper over the finder’s patch.
   Widening a type is not a fix (see [Types](#types)).
4. **Risk.** Severity Blocker/High **and** practicality not Low → `fix`. Nit-budget does not apply. If the fix itself is
   a separate feature, split or `follow-up` instead of bloating this PR.
5. **Cheap + high practicality + Medium+.** Cost **cheap**, practicality **High**, severity **Medium or higher**, and
   **no** new abstraction → `fix`. Nit-budget does not defer these (any review round). Apply the
   [surface quality bar](#surface-quality-bar-fixer-triage) **before** claiming High practicality — agent-plumbing and
   shared-Devinfra-script exotic / host-only / wording nits are Low, not step 5. **Docs / comment-only** findings are
   **Low** (see [Severity](#severity-pick-the-first-match-do-not-upgrade-on-vibe)) unless the wrong text breaks the
   supported cadence — they never become step 5 via “misleads operators”. Synced paths in consumers are already handled
   by the synced-path gate after step 2 — do not take this step against allowlisted synced files.
6. **Nit.** Otherwise treat as a nit:
   - Cheap + **PR nit total** (prior soft spend + this run) still ≤ ~15 and **no** new abstraction → `fix`
   - Or the nit is on code the **previous fixer pass** introduced → `fix` if cheap (still counts toward the PR total)
   - Else → `dismiss` (Low) or `follow-up` (Medium+ only, typically when expensive or practicality is not High)

If the cheaper fix is unclear, default to `dismiss` rather than adding a layer.

---

## Synced paths (sync source of truth)

For paths listed in [`docs/synced-paths.yaml`](synced-paths.yaml), **sync source of truth** overrides the usual “cheap +
High practicality + Medium+ → `fix` in this PR” rule when `/review-fixer` runs in a **product** checkout. Fixers MUST
NOT treat a correct cheap patch on a synced path as an in-PR `fix` of that synced file; they MUST `follow-up` to
Devinfra or `dismiss` (synced — edit upstream), or `fix` only a documented product-local overlay. In the Devinfra
repository itself, those paths are the local source of truth and MAY be fixed like any other in-repo file.

---

## Severity (pick the first match; do not upgrade on vibe)

| Level       | When (any one)                                                                                                                                                                                                                                                                |
| ----------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Blocker** | Wrong domain result; data loss or silent overwrite; broken HTTP/API or documented contract; secret/credential in logs or persistence; documented race that can clobber a document or equivalent state                                                                         |
| **High**    | Error swallowed (empty `except`, success status on failure); idempotency / conflict handling wrong; authz/ownership bypass; resource leak on a hot path                                                                                                                       |
| **Medium**  | New behaviour with no test; **runtime** error path that misleads operators (wrong exit status, success-on-failure logs, API/error payload); duplication that will diverge in code                                                                                             |
| **Low**     | Naming, comments, extra abstraction, defensive check inside already-validated data, micro-DRY; **docs / OpenSpec / code-comment prose** that is inaccurate or contradictory but does **not** break the supported Dev Container / CI cadence or change the real pass/fail gate |

If nothing matches Blocker/High/Medium → **Low**.

**Do not upgrade docs to Medium.** “Misleads operators” means a **running system** lies to operators (exit code, log
line, HTTP body) — not that a contributor reading `docs/` or a `#` comment might be confused. Inaccurate quality-doc
wording (e.g. “hooks and CI both use `-ll`” when CI already implements the same fail bar differently) is **Low**. Fixers
MUST NOT take step 5 or inflate **Fixed non-nit** solely for comment / docs clarification.

---

## Practicality (requires a path sentence)

Practicality is not “we have seen this in prod”. It is “a realistic path exists in _this_ system”.

| Level      | Rule                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **High**   | Cite entry → function → bad state. Entry is a public HTTP route, a worker / async task, or a config field set by default / the repo's documented default config.                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| **Medium** | Only with non-default config, an internal caller, or admin.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| **Low**    | State is excluded by Pydantic, the config wrapper, annotations, a **spec / OpenSpec invariant**, or a **shared-file contract** already enforced for supported callers — **quote the invariant** (e.g. synced `versions.env` already defines the required keys; sync docs require that file). A path that is only reachable by deleting or omitting those contracted keys/files is **not** High.                                                                                                                                                                                                             |
| **None**   | False positive; the alleged path does not exist in the **Linux Dev Container** (or GitHub Actions Linux CI); **or** the path is only a one-shot local migration / ephemeral personal file format that is not the current write path and not a shipped contract (re-run setup once). Includes macOS/Windows/Homebrew, BSD/non-GNU tool differences, host-only fallbacks when the Dev Container primary path already works, and unofficial bare-Linux-without-container runs — quote [`openspec/principles.global.md`](../openspec/principles.global.md) Supported development environment when that applies. |

If the fixer cannot write a path sentence, practicality is **Low**, not High.

**Mechanical path ≠ realistic path.** Code that _can_ error when a required shared file is incomplete is not High
practicality if supported callers never ship that incomplete state. Ask: “Under documented sync / default CI / Dev
Container adoption, does this bad state still occur?” If **no** — quote the contract (`versions.env` section, synced
path list, workflow inputs that always inject pins) → practicality **Low** or **None** → usually `dismiss`. **Do not**
add opt-in flags, dual modes, or “REQUIRE_*” shims solely for “caller deleted a contracted pin.” **Cheap does not
override.**

Risk is high only when severity is Blocker/High **and** practicality is not Low/None.

### Surface quality bar (fixer triage)

Not every path has the same bar. Classify the touched surface **before** step 5, and adjust practicality / dismiss
accordingly. Finders may still comment; the fixer must not treat agent plumbing or shared Devinfra scripts like product
middleware.

**Path map:** default rows are in [`docs/surface-quality-bar.global.md`](surface-quality-bar.global.md) (synced — do not
hand-edit). Product repos MAY add rows in local [`docs/surface-quality-bar.md`](surface-quality-bar.md); sync of the
`.global.md` file does not overwrite that overlay. Do not edit this policy file solely to add a path→surface row.
**Synced path ownership** (which trees consumers must not patch) is [`docs/synced-paths.yaml`](synced-paths.yaml) — see
[Synced paths](#synced-paths-sync-source-of-truth).

For **shared Devinfra scripts** (and reusable CI helpers that only orchestrate them), a realistic path is the
**documented default** in the Linux Dev Container or GitHub Actions Linux (e.g. `./scripts/quality-check.sh`,
`pre-commit` commit stage, postCreate token load, `source scripts/load-versions-env.sh` against a **complete** synced
`versions.env`) — not host-only installs, unofficial bare-metal runs, linked git worktrees (`.git` as file), speculative
edge hardening, or **hypothetical incomplete shared config** (missing pin keys, unsynced contracted files, “what if
quality runs without the Product app image section”). Those are practicality **Low** (or **None**). **Do not** take step
5 merely because the patch is cheap. **Do not** spend **nit-budget** on those exotic edges either — `dismiss` them.
Still **fix** when that documented path is wrong **with the contracted files as this repo ships them** (including real
consumer-sync failures such as hook argv-length on `pre-commit run --all-files`, or check scripts that mutate contrary
to their contract).

**Also dismiss** on this surface: pre-commit / shell **style-only** nits (`entry` vs `args`, comment polish) and
**re-adding** exotic repair paths the PR intentionally removed, when the happy path still works.

For **docs**, dismiss wording-only and host-prerequisite nits that do not break the Dev Container cadence. When
instructions are factually wrong but the **supported commands and fail bars still work** (wrong explanation of _how_ CI
logs, intentional Bandit LOW visibility, comment polish in hooks YAML): severity stays **Low** → nit-budget or `dismiss`
— **not** step 5. Escalate only when wrong docs would make the supported path fail (wrong command, wrong config path,
cadence that cannot succeed as written).

For **agent plumbing**, a realistic path is a **default skill invocation** (e.g. `issue-branch` / `issue-start` with
`--base main`, `review-open --pr N`) — not adversarial argparse (`--base --all`), partial flag combinations, or
wording-only error-message polish. Those are practicality **Low** (or **None** if no real agent path). **Do not** take
step 5 merely because the patch is cheap.

Still **fix** agent-plumbing findings when the default Dev Container skill path is wrong (e.g. stale `origin/main` makes
`branch-ahead` lie).

---

## Cost (estimate _before_ coding, on the chosen fix)

Do not use `git diff --stat` of a patch that does not exist yet. Estimate the fix you would actually apply, not the
finder’s suggested patch.

| Signal               | Cheap                  | Expensive                                |
| -------------------- | ---------------------- | ---------------------------------------- |
| New production lines | 0 or <15               | 15–50 (grey) / >50                       |
| New abstraction      | no                     | new class, helper, or module             |
| Types                | same or **narrower**   | wider (`T \| None`, `Any`, untyped dict) |
| Scope                | one function, one file | multiple modules / extra responsibility  |

**Expensive** if any of: new abstraction, wider type, multiple modules, >50 prod lines. A new helper with no second call
site is expensive even at 20 lines.

### What counts as production size

- **Counts:** runtime code under `middleware/*/src/` (see path conventions).
- **Does not count:** tests that lock **real** behaviour (regression for a real bug, endpoint or public contract). Tests
  that encode a hypothetical state the types already forbid **do** count as bloat — do not add them.
- **Specs:** may grow when they record a contract the code now actually has. Do not add spec text for a theoretical
  weakness. Spec growth is not the production size budget; still apply risk vs cost.

---

## Nit-budget

A **nit** is a correct (or plausible) finding that is **not** high risk and does **not** already qualify as step 5
(cheap + High practicality + Medium+).

Exotic edges on shared Devinfra / agent plumbing (surface bar → practicality Low) are **not** eligible nit-fixes —
`dismiss` even when cheap. Nit-budget only applies after the surface bar says the path is in scope.

Budget (fixer only) is a **soft lifetime cap per PR** of **~15 new production lines** from nit-fixes (never a new
abstraction). It is **not** gated on Copilot/Bugbot review round — later rounds often surface Low nits after earlier
Medium/risk findings — and it is **not** reset on each `/review-fixer` run.

**Soft tracking** (good enough; not audit-grade):

1. Before spending on nits, sum every `nit-lines this run: N` (integer N) already posted in fixer replies on this PR
   (review-thread replies and PR conversation comments). That sum is **prior spend**.
2. This run may fix cheap nits while `prior spend + lines added this run for nits` ≤ ~15.
3. Cheap nits on surface **introduced by the previous fixer pass** (regression) may be fixed; they **count toward** the
   same PR total.
4. When the PR total would exceed ~15 → `dismiss` remaining Low nits (or `follow-up` for Medium+ per the decision
   order).
5. Risk findings and step-5 (cheap + High practicality + Medium+) findings are **never** budgeted away and **do not**
   consume nit-line budget.
6. Every nit `fix` reply MUST include `nit-lines this run: N` for the production lines added for nits in **this** run
   (use `0` only if the nit fix truly added no prod lines, e.g. comment-only). Prefer one aggregate line on the last nit
   reply or on a summary PR comment when several nits were fixed in the same run.

---

## Types

These rules apply to writing code and to reviewing it
([`openspec/principles.global.md`](../openspec/principles.global.md) Type Safety).

- Do **not** widen a type to silence a finding (`T` → `T | None`, `Any`, `object`, `dict[str, Any]`). That is a new
  defect, not a fix. Do not hide `Any`/`object` behind a type alias.
- Do **not** add `if x is None` / `x or default` when the annotation, Pydantic model, or config wrapper already excludes
  `None`.
- If `None` is genuinely required, make the **source** optional and update every caller. Do not insert a local guard in
  the middle of the pipeline.
- Prefer a narrower type, an existing helper, or a quoted invariant over a new wrapper or retry layer.

---

## Follow-up issues

- At most **one** follow-up issue per PR.
- Include only deferred items that are **Medium or higher**.
- Low nits that miss the budget get a dismissal reply, not an issue.
- Title: `Follow-up from PR #<pr_number> AI review`.
- Open via `/create-issue` (org type + triage labels + body template in
  [`.agents/skills/create-issue/SKILL.md`](../.agents/skills/create-issue/SKILL.md)); include deferred findings (path,
  severity, practicality, why out of this PR) in that body.

---

## Fixer reply format

Reply on the thread in **normal Markdown** (no fenced/`text` verbatim blocks for the reply body — GitHub will wrap
prose). Then resolve the thread.

Use a short human reply — do **not** restate `correct` / `severity` / `practicality` / `cost` in the comment.

`/review-fixer` runs in **two phases** when any finding is fixed: Phase 1 applies local fixes and posts dismiss /
follow-up replies; the human commits; Phase 2 posts `Fixed in <commit-sha>.` and resolves those threads. The agent MUST
NOT commit to create that SHA.

| Outcome                        | Reply shape                                                                        |
| ------------------------------ | ---------------------------------------------------------------------------------- |
| **Fixed** (same as suggestion) | `Fixed in <commit-sha>.`                                                           |
| **Fixed** (different approach) | `Fixed in <commit-sha>.` plus one or two sentences on what you did instead and why |
| **Dismissed**                  | `Dismissed.` plus a short textual reason                                           |
| **Follow-up**                  | `Follow-up: <issue-URL>.` plus a short textual reason why it is deferred           |

Examples:

- `Fixed in a1b2c3d.`
- `Fixed in a1b2c3d. Narrowed the return type of Foo.bar instead of adding a None-guard.`
- `Dismissed. Unsupported host path — see openspec/principles.global.md Supported development environment.`
- `Follow-up: https://github.com/org/repo/issues/123. Medium finding, expensive fix outside this PR.`

On **nit** fixes only, also append a plain line for budget tracking (still not a code fence): `nit-lines this run: N`.
