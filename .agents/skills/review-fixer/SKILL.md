---
name: review-fixer
description: >-
  Triages GitHub Copilot and Cursor Bugbot pull-request review comments using
  the project AI review policy: re-evaluates correctness, severity, practicality,
  and fix cost; implements high-risk or in-budget nits; dismisses the rest with a
  reply; optionally opens one follow-up issue. Use when the user pastes
  Copilot/Bugbot reviews, asks to fix AI review comments, run /review-fixer, or
  process PR review threads.
---

# Review fixer

Implement policy. Do not re-litigate it. Read [`docs/ai_review_policy.md`](../../../docs/ai_review_policy.md) if
anything here is ambiguous.

You are the **fixer** (precision). Copilot and Bugbot are finders (recall). Do not loop until comments are gone.

**Abort criterion:** When this run’s output shows **Fixed non-nit this run: 0**, the review cycle **stops**. Do not ask
for another Copilot/Bugbot pass or another `/review-fixer` just because threads/comments remain, Remaining risk is
already 0, or you only dismissed / fixed nits. **Fixed non-nit this run** = count of this run’s `fix` actions that are
not nits (Risk step 4, or step-5 cheap + High practicality + Medium+). Risk (merge) still = Blocker/High **and**
practicality not Low/None — report it, but it does **not** drive the abort. If Fixed non-nit ≥ 1, do **not** claim the
cycle should stop. Optional: **at most one** deliberate nit-only pass while nit-budget remains even when Fixed non-nit
would be 0; after that pass, stop. Resume only for new non-nit-fixable open work or an explicit human request.

## Input

Accept any of:

- A PR number or URL (default: process **open** work only — see below)
- A review URL (`/pull/N#pullrequestreview-ID` or a discussion permalink)
- Pasted review comments / a review conversation
- “Fix the Copilot/Bugbot comments on this PR”

If the user gives a **review URL**, triage **that submission only** (inline threads from that review + its summary body,
including Copilot “Suppressed comments”). Do not re-triage older reviews.

If they give only a **PR number/URL**, discover open work yourself. Do **not** re-read or reply on already-resolved
threads.

If they only pasted text, triage that text and **do not** reply on GitHub unless they also gave a PR.

Do **not** commit. Do **not** push. Never create a git commit to obtain a SHA for replies.

## Two phases (when any thread is `fix`)

**Phase 1 — triage and local work**

1. Fetch open work, fill checklists, decide `fix` / `dismiss` / `follow-up`.
2. Apply all `fix` changes locally only (working tree / index — no commit).
3. Immediately reply + resolve for **`dismiss`** and **`follow-up`** (and open the follow-up issue if needed). These
   need no commit SHA.
4. **Stop** before any `Fixed in …` reply. Show the user table, files changed, suggested commit message, and ask them to
   commit (and push if the PR should see it). Wait for confirmation or a SHA.

**Phase 2 — after the user commits**

1. Take the commit SHA the user created (they paste it, or you read it from `git log` / the PR once they confirm).
2. Reply `Fixed in <sha>.` (+ what/why if different; + `nit-lines this run: N` on nit fixes) on each pending `fix`
   thread, then resolve.
3. If there were no `fix` items, Phase 2 is skipped.

If the user declines to commit, leave fixes in the working tree, do **not** post `Fixed in …`, and say so. Do not invent
a SHA.

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

3. After they confirm, retry `uv run m42-ai auth-status` (or `gh auth status` / the GraphQL fetch). If auth works,
   continue with fetch / replies / resolves as usual.
4. Only if they decline or auth still fails: skip GitHub writes, print the intended replies/resolves, and stop that
   part. Still apply local code fixes when triage says `fix`.

## Fetch open work (when a PR is known)

**Start from the CLI** (do not dump raw GraphQL into context):

```bash
uv run m42-ai review-open --pr PR
# optional, when the user gave /pull/N#pullrequestreview-ID:
uv run m42-ai review-open --pr PR --review-id ID
```

The JSON already filters to unresolved AI threads and **summary-only findings from every AI review body**
(`summary_only_findings` / each entry in `ai_reviews`), not only the latest submission — Copilot “Suppressed comments”
often have no thread and would be missed if a later Bugbot/Cursor review became “latest”. Optional `--review-id` scopes
review bodies when the user gave a `/pull/N#pullrequestreview-ID` permalink. Docs:
[`scripts/ai/README.md`](../../../scripts/ai/README.md).

**Open work** (this is the only set you triage unless the user pasted a specific review URL):

1. **Unresolved** AI threads from `unresolved_ai_threads` (Copilot / Bugbot / Cursor). Skip human threads unless the
   user asked.
2. **`summary_only_findings`** — open summary-only / suppressed items from **at most one** AI review
   (`open_summary_review_id`): the latest suppressed AI review that is not yet answered. Older suppressed reviews are
   treated as closed when a triage reply exists after them (PR conversation comment or non-AI review body starting with
   `Fixed in` / `Dismissed.` / `Follow-up:`, ideally including `#pullrequestreview-<id>`). These findings have **no**
   resolve button — **never** call `review-resolve` on them; reply with `m42-ai review-reply --pr PR --conversation` and
   include `#pullrequestreview-<id>` in the body so later `review-open` marks that review answered.

Ignore resolved threads completely (do not reply on them again).

If `open_work_empty` is true (no unresolved AI threads and no summary-only findings), say so in one sentence and stop.

**Nit-budget (soft PR lifetime):** Before fixing nits, sum prior `nit-lines this run: N` from fixer replies already on
this PR (thread replies + PR conversation). Cap is **~15** for `prior + this run`. Not reset per `/review-fixer`
invocation; not gated by Copilot/Bugbot review round. Risk and step-5 fixes do not consume the budget. Every nit `fix`
reply must include `nit-lines this run: N`. See `docs/ai_review_policy.md`.

## Per-thread procedure

Copy this checklist and fill it. Do not implement until it is filled.

```text
id / path:
correct: yes/no
this PR: yes/no
chosen fix: (narrower type / invariant / local / finder's patch / none)
severity: Blocker|High|Medium|Low
practicality: High|Medium|Low|None — path or invariant:
cost: cheap|expensive — prod lines ~N, new abstraction yes/no, type wider yes/no
risk: high|not
action: fix|dismiss|follow-up
reason: (optional — required when synced path: "synced → Devinfra" / overlay)
budget: nit-in-budget|nit-regression|nit-exhausted|n/a-risk
```

**Synced paths (product consumers):** Before any `fix`, match the finding’s primary path against
[`docs/synced-paths.yaml`](../../../docs/synced-paths.yaml). In a **product** checkout, **never** modify
allowlisted / synced trees. Prefer detecting Devinfra via `git remote` matching `fairagro/m4.2_middleware_devinfra`; if
unsure, treat as consumer (safer). In **this Devinfra repo**, allowlisted paths are local SoT and MAY be `fix`ed.

Decision order (stop at first match) — same as the policy:

1. Incorrect / already gated / no path / **unsupported environment** / **one-shot local migration** / **intentional
   happy-path simplification re-hardening** / **host-only prerequisite docs** / **shared-hook style-only** /
   **mechanical-only path on plumbing** (bad state only if a contracted shared file is incomplete or unsynced contrary
   to docs — quote `versions.env` / sync contract; see
   [Practicality](../../../docs/ai_review_policy.md#practicality-requires-a-path-sentence) “Mechanical path ≠ realistic
   path”) → `dismiss` (practicality **None** or **Low**). For unsupported hosts, quote
   [`openspec/principles.global.md`](../../../openspec/principles.global.md) “Supported development environment”. The
   Linux Dev Container is the bar (GitHub Actions Linux CI counts). Dismiss even when the finding is “correct” only on
   macOS/Windows/Homebrew/BSD userland, unofficial bare Linux, host `PATH` quirks, or a **compatibility fallback** that
   never runs when Dev Container tools work (e.g. GNU `base64 -w0`). **Also dismiss** findings that only harden a
   **one-shot** personal/on-disk format that is not the current write path and not a shipped contract (e.g. pre-`b64:`
   `tokens.env` lines) — tell the author to re-run `source ./scripts/set-dev-tokens.sh` (or equivalent) once; do **not**
   add legacy parsers or `eval` deny-lists. **Also dismiss** requests to restore exotic `bashrc`/marker/host-token
   branches after this PR simplified them, and pre-commit YAML style (`entry` vs `args`) when the hook still works.
   **Also dismiss** (do **not** step-5) findings whose only bad state is “caller violated an already-shipped shared-file
   contract” (incomplete synced `versions.env`, missing contracted pin section, unsynced required path) — quote the
   contract; do **not** add `REQUIRE_*` opt-in shims or dual modes. **Cheap does not override this** — do not take step
   5 for host-only, one-shot-migration, or contract-violator-only hardening.
2. Not this PR → `dismiss`, or `follow-up` if Medium+ **Synced path (product consumers) — before steps 3–5:** Path on
   [`docs/synced-paths.yaml`](../../../docs/synced-paths.yaml) (or matching glob) **and** this checkout is
   **not** Devinfra → **do not** `fix` that synced file. Instead:
   - `follow-up` (create-issue against **Devinfra**, or clear Devinfra-targeted follow-up) when the finding is correct
     for shared content and severity is Medium+, or Risk, or seen-in-the-wild shared bug;
   - else `dismiss` with reason `synced path — edit upstream in Devinfra / wait for sync`;
   - **or** `fix` only a **documented product-local overlay** from that allowlist (e.g. `docs/surface-quality-bar.md`) —
     never by editing `.global` / synced trees. Phase-1 reason MUST name the synced-path rule. Working tree MUST NOT
     gain dirty edits under synced paths from this run. (Actions stay `fix` / `dismiss` / `follow-up` — no separate
     `upstream` action.)
3. Choose the **cheapest correct** fix. Widening a type is forbidden. `if x is None` is forbidden when the type already
   excludes `None`.
4. High risk (Blocker/High **and** practicality not Low/None) → `fix` (or split/`follow-up` if the fix is its own
   feature)
5. Cheap + High practicality + severity Medium or higher, and **no** new abstraction → `fix` (not deferred by
   nit-budget). **Except** agent-plumbing / shared Devinfra scripts / docs / vendor surfaces: apply the **surface
   quality bar** ([rules](../../../docs/ai_review_policy.md#surface-quality-bar-fixer-triage),
   [path map](../../../docs/surface-quality-bar.global.md)) first — exotic CLI/host edges, **contract-violator-only**
   incomplete shared config, and wording nits are practicality Low → not step 5. Re-check **mechanical ≠ realistic**
   before High practicality. **Docs / comment-only** inaccuracies that do not break the supported cadence are severity
   **Low** (never Medium via “misleads operators”) → nit or dismiss, not Fixed non-nit. **Synced paths in consumers are
   already handled by the synced-path gate after step 2** — sync SoT overrides this step for those paths
   ([policy](../../../docs/ai_review_policy.md#synced-paths-sync-source-of-truth)).
6. Else nit:
   - **First:** if the finding is an **exotic edge** on shared Devinfra `scripts/` (except `scripts/ai/`), agent
     plumbing, docs wording, vendor skills, **or** a bad state that only appears when contracted shared files/pins are
     missing contrary to sync docs — `dismiss` (practicality Low). **Nit-budget does not override** the surface quality
     bar (e.g. linked git worktrees, host-only installs, BSD/`base64` quirks, “versions.env without Product app pins”).
     See `docs/ai_review_policy.md` and `docs/surface-quality-bar.global.md`.
   - Cheap + prior PR nit spend + this run’s nit lines still ≤ ~15 and **no** new abstraction → `fix`
   - Or the nit is on code the previous fixer pass introduced → `fix` if cheap (counts toward the PR total)
   - Else → `dismiss` (Low) or `follow-up` (Medium+ only when expensive or practicality is not High)

Sum prior `nit-lines this run: N` from existing fixer replies on the PR, then add lines you introduce for nits **this
run**.

## Implement fixes

- Batch all `fix` threads, then run focused `uv run pytest` on affected packages and
  `uv run ruff format --config pyproject.toml` / `ruff check` on touched files (when the repo has product `middleware/`
  packages).
- Prefer narrowing types over guards. Do not add tests that only assert impossible `None` states.
- Specs: update only when the code’s real contract changed.
- In product consumers: never stage or leave dirty edits under
  [`docs/synced-paths.yaml`](../../../docs/synced-paths.yaml) paths from fixer work.

## GitHub replies (PR known)

Required for **open work only**, when `gh` can write. Do not reply on resolved threads.

**Timing:** `dismiss` / `follow-up` in Phase 1; `Fixed in …` only in Phase 2 after a **user** commit exists. Do not
finish Phase 1 by posting fake or premature Fixed replies.

**Unresolved threads:**

1. Reply on the first review comment (`in_reply_to`).
2. Then resolve the thread if the mutation succeeds.
3. Do **not** resolve without a reply.

**Summary-only / suppressed comments** (no thread, no resolve button): post one PR conversation comment covering those
items. Include `#pullrequestreview-<review_database_id>` so `review-open` can treat that review as answered. Do **not**
invent a thread resolve. Same timing rules (dismiss/follow-up now; fixed after user commit).

If `gh` lacks auth or `resolveReviewThread` fails (permissions), leave the reply if you posted one, print the remaining
reply/resolve text for the user, and still apply local code fixes.

Reply body: **normal Markdown prose** (no fenced verbatim/`text` blocks — those do not wrap on GitHub). Do **not** list
`correct` / `severity` / `practicality` / `cost` in the reply (keep those in your private checklist only).

| Outcome                   | Reply                                          | When                  |
| ------------------------- | ---------------------------------------------- | --------------------- |
| Fixed, matches suggestion | `Fixed in <commit-sha>.`                       | Phase 2 (user commit) |
| Fixed, different approach | `Fixed in <commit-sha>.` + brief what/why      | Phase 2 (user commit) |
| Dismissed                 | `Dismissed.` + short reason                    | Phase 1               |
| Follow-up                 | `Follow-up: <issue-URL>.` + short why deferred | Phase 1               |

On nit fixes only, append a plain line: `nit-lines this run: N` (budget tracking; not a code fence).

Prefer the CLI (auth still via `scripts/bin/gh` / `GH_TOKEN`):

```bash
uv run m42-ai review-reply --pr PR --in-reply-to COMMENT_DATABASE_ID --body-file /tmp/reply.md
uv run m42-ai review-resolve --thread-id THREAD_NODE_ID
# summary-only / suppressed:
uv run m42-ai review-reply --pr PR --conversation --body-file /tmp/reply.md
```

## Follow-up issue

At most **one** per PR, and only if at least one `follow-up` item is Medium+. Low nits never become issues.

Open it by reading and following [`.agents/skills/create-issue/SKILL.md`](../create-issue/SKILL.md) (type, triage
labels, create-if-missing allowlist, Auth, body template, **relation**). Do **not** call `gh issue create` with a
review-fixer-only inline template.

When invoking create-issue from here:

1. Title: `Follow-up from PR #<pr_number> AI review`.
2. Include **every** Medium+ `follow-up` item in the create-issue body (paths, severities, practicality, why deferred)
   under **Problem** / **Why not now?**; link the PR under **Links**.
3. Pick org type + severity/practicality/cost labels from the deferred set (typical: `Task`; use max severity among
   items; cost from why it was deferred). Prefer fields already on your private checklists — do not re-triage the PR.
4. **Relation:** `linked` by default (standalone issue). Use `relation: sub-of #<issue_number>` only when the PR body
   includes `Fixes #<issue_number>` (or equivalent) **and** the deferred item is clearly remaining acceptance criteria
   of that issue. When unclear, prefer `linked`.
5. Use the returned issue URL in each `Follow-up: <url>.` reply.

If create-issue is missing in a consumer checkout, say so and print the intended create-issue inputs (title, body draft,
type, labels, relation) for the user — still do not invent a non-allowlisted create path.

## Output to the user

A table, one row per thread:

| Thread | Severity | Practicality | Cost | Action | Reason |
| ------ | -------- | ------------ | ---- | ------ | ------ |

**End of Phase 1:** files changed, tests run, dismiss/follow-up reply status, follow-up issue URL or “none”, **Fixed
non-nit this run** (integer), and **Remaining risk** (integer, merge channel). If **Fixed non-nit this run: 0**, state
explicitly that the **review cycle should stop** (abort criterion). If Fixed non-nit ≥ 1, do **not** abort — note that
another finder pass is allowed after the fixes land. If any `fix` — “paused for your commit” with a suggested message.
Do not claim Fixed replies are done yet.

**End of Phase 2:** which Fixed replies/resolves succeeded and the SHA used; repeat **Fixed non-nit this run** and
whether the cycle should stop or may continue.

If risk findings remain because you need a product decision, list them explicitly and do not claim the PR is ready.
