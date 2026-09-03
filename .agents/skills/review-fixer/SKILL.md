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

- A PR number or URL
- Pasted review comments / a review conversation
- “Fix the Copilot/Bugbot comments on this PR”

If a PR is identifiable, fetch unresolved AI threads with `gh` (below). If
the user only pasted text, triage that text and **do not** reply on GitHub
unless they also gave a PR.

Do **not** commit unless the user asks. Do **not** push.

## Fetch threads (when a PR is known)

```bash
gh api graphql -f query='
query($owner:String!,$name:String!,$n:Int!) {
  repository(owner:$owner, name:$name) {
    pullRequest(number:$n) {
      url
      reviews(first: 50) {
        nodes { author { login } submittedAt state }
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

Keep threads that are **unresolved** and whose first comment author is
Copilot or Bugbot (`copilot-pull-request-reviewer`, `copilot[bot]`,
`cursor[bot]`, `bugbot`, or similar). Skip human threads unless the user
asked to include them.

**Round** = count of Copilot + Bugbot **review submissions** (not comment
count). Round 1 vs 2+ drives nit-budget.

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

Reply, then resolve. Do not resolve without a reply.

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

If `gh` fails (auth, permissions), print the reply text for the user to
paste. Still apply local code fixes.

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
