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

Implement policy. Do not re-litigate it. Read
[`docs/ai_review_policy.md`](../../../docs/ai_review_policy.md) if anything
here is ambiguous.

You are the **fixer** (precision). Copilot and Bugbot are finders (recall).
Do not loop until comments are gone. Stop when no **risk** finding remains.

## Input

Accept any of:

- A PR number or URL (default: process **open** work only — see below)
- A review URL (`/pull/N#pullrequestreview-ID` or a discussion permalink)
- Pasted review comments / a review conversation
- “Fix the Copilot/Bugbot comments on this PR”

If the user gives a **review URL**, triage **that submission only**
(inline threads from that review + its summary body, including Copilot
“Suppressed comments”). Do not re-triage older reviews.

If they give only a **PR number/URL**, discover open work yourself. Do
**not** re-read or reply on already-resolved threads.

If they only pasted text, triage that text and **do not** reply on GitHub
unless they also gave a PR.

Do **not** commit unless the user asks. Do **not** push.

## Auth (`gh`)

`gh` is wrapped (`scripts/bin/gh`, on `PATH` in the Dev Container). Missing
`GH_TOKEN` prompts on `/dev/tty` and is saved to
`/commandhistory/tokens.env` (Dev Container volume `middleware-api-bashhistory`;
survives rebuilds) or `~/.config/middleware-api/tokens.env` on a local clone.
Do not read tokens from the git worktree; do not invent them. If there is no
TTY, skip GitHub writes, print the intended replies, and tell the user to
open a terminal or run `./scripts/set-dev-tokens.sh`.

## Fetch open work (when a PR is known)

Be fast. One GraphQL query. Then **filter in memory**.

```bash
gh api graphql -f query='
query($owner:String!,$name:String!,$n:Int!) {
  repository(owner:$owner, name:$name) {
    pullRequest(number:$n) {
      url
      reviews(first: 50) {
        nodes { databaseId author { login } submittedAt state body }
      }
      reviewThreads(first: 100) {
        nodes {
          id
          isResolved
          comments(first: 20) {
            nodes { databaseId author { login } body path originalPosition }
          }
        }
      }
    }
  }
}' -F owner=OWNER -F name=REPO -F n=PR
```

**Open work** (this is the only set you triage unless the user pasted a
specific review URL):

1. **Unresolved** review threads whose first comment author is Copilot or
   Bugbot (`copilot-pull-request-reviewer`, `copilot[bot]`, `cursor[bot]`,
   `bugbot`, or similar). Skip human threads unless the user asked.
2. The **latest** Copilot or Bugbot **review submission** `body`, if it
   contains findings that are **not** already an unresolved thread.
   Copilot Lite often puts “Needs a closer look” and **Suppressed
   comments** only in that summary. Suppressed comments have **no**
   resolve button and **no** thread id — still triage them; reply on the
   PR conversation (`issues/PR/comments`), not via `resolveReviewThread`.

Ignore resolved threads completely (do not reply on them again).

If open work is empty, say so in one sentence and stop.

**Round** = count of Copilot + Bugbot **review submissions** on the PR
(not comment count). Round 1 vs 2+ drives nit-budget. You still need
that count even when you only triage the latest open items.

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
budget: nit-round1|nit-round2-regression|nit-exhausted|n/a-risk
```

Decision order (stop at first match) — same as the policy:

1. Incorrect / already gated / no path → `dismiss`
2. Not this PR → `dismiss`, or `follow-up` if Medium+
3. Choose the **cheapest correct** fix. Widening a type is forbidden.
   `if x is None` is forbidden when the type already excludes `None`.
4. High risk (Blocker/High **and** practicality not Low/None) → `fix`
   (or split/`follow-up` if the fix is its own feature)
5. Else nit:
   - Round 1 + cheap + running nit prod-line growth still ≤ ~25 and **no**
     new abstraction → `fix`
   - Round 2+ **and** the nit is on code the previous fixer pass introduced
     → `fix` if cheap
   - Else → `dismiss` (Low) or `follow-up` (Medium+)

Running nit growth is the sum of production lines you add for nits **this
run**, not the whole PR.

## Implement fixes

- Batch all `fix` threads, then run focused `uv run pytest` on affected
  packages and `uv run ruff format --config pyproject.toml` / `ruff check`
  on touched files.
- Prefer narrowing types over guards. Do not add tests that only assert
  impossible `None` states.
- Specs: update only when the code’s real contract changed.

## GitHub replies (PR known)

Required for **open work only**, when `gh` can write. Do not finish after
local code changes alone. Do not reply on resolved threads.

**Unresolved threads** (`fix`, `dismiss`, `follow-up`):

1. Reply on the first review comment (`in_reply_to`).
2. Then resolve the thread if the mutation succeeds.
3. Do **not** resolve without a reply.

**Summary-only / suppressed comments** (no thread, no resolve button):
post one PR conversation comment covering those items. Do not invent a
thread resolve.

If `gh` lacks auth or `resolveReviewThread` fails (permissions), leave
the reply if you posted one, print the remaining reply/resolve text for
the user, and still apply local code fixes.

```text
fix | dismiss | follow-up
correct: …
severity: …
practicality: … (path or invariant)
cost: cheap|expensive
reason: …
```

If the fix differs from the suggestion, state the alternative (“narrowed
`Foo.bar` return type instead of a None-guard”).

Reply via `gh api` on the pull-review comment, then resolve the thread:

```bash
# reply (REST in_reply_to)
gh api "repos/OWNER/REPO/pulls/PR/comments" \
  -f body='...' -F in_reply_to=COMMENT_DATABASE_ID

# resolve
gh api graphql -f query='
mutation($id:ID!) {
  resolveReviewThread(input:{threadId:$id}) { thread { isResolved } }
}' -F id=THREAD_NODE_ID
```

## Follow-up issue

At most **one** per PR, and only if at least one `follow-up` item is
Medium+. Low nits never become issues.

```bash
gh issue create --title "Follow-up from PR #<n> AI review" --body "..."
```

Body: bullets with path, severity, practicality, why not this PR. Link the
PR.

## Output to the user

A table, one row per thread:

| Thread | Severity | Practicality | Cost | Action | Reason |
| ------ | -------- | ------------ | ---- | ------ | ------ |

Then: files changed, tests run, whether GitHub replies/resolves succeeded,
follow-up issue URL or “none”, remaining **risk** count (should be 0).

If risk findings remain because you need a product decision, list them
explicitly and do not claim the PR is ready.
