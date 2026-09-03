# Issue fixer

Triage and fix a GitHub issue. You are the **fixer** (precision):
Implement the smallest correct change in this PR (MVP slice), or split the
work into sub-issues when it becomes too large.

You create a branch and a PR. To close the issue automatically on merge,
the PR body must include: `Fixes #<issue_number>`.

Important: do **not** automatically commit or push the fix commits.
You may push an empty head branch to remote before the fix so the PR
already exists. The PR will be filled once the user manually pushes.

## Input

- Issue number or URL (preferred)

## Auth (`gh`)

`gh` is wrapped (`scripts/bin/gh`, on PATH in the Dev Container).
If auth is missing and there is no TTY available, skip GitHub write
actions and work locally; then print title/body drafts.

## Fetch issue & triage

1. Fetch the issue details (body, labels, URL) with `gh`.
2. Determine:
   - org issue type: `Bug|Security|Feature|Task|Discussion|Refactoring`
     (from body `Type:` or if templates/labels are used)
   - triage labels: `severity:*`, `practicality:*`, `cost:*` (if set)
   - problem statement: what is wrong / what is observed
   - affected paths/areas (prefer concrete `path:` sentences)
   - acceptance criteria / “done when”

3. Decision:
   - If missing actionable info: comment with at most 3 questions and
     stop (no code changes).
   - If already resolved / not applicable: comment briefly and stop.
   - Else: plan the MVP slice.

## Branch + PR workflow (without automatic code push)

Assumptions:

- base branch is `main`

### Branch name

Create a branch:

- `issue-<ISSUE_NUMBER>-<short-slug>`

### Create PR (empty head branch)

1. Create the local branch from `main`.
2. Push the branch to remote, but **without** fix commits (it only needs
   to exist so the PR can be created).
   - If your branch already exists locally on `main`: the push is an “empty”
     branch creation.
3. Create the PR with `gh pr create`:
   - `--base main`
   - `--head <branch>`
   - Body must include: `Fixes #<issue_number>`
   - PR body links the issue and names the MVP scope briefly.

### Implement fixes (locally)

After PR creation:

- Implement code changes directly in the working tree on the PR branch.
- Do **not** commit or push the fix commits.
- If the changes are too large: create sub-issues (see below) and implement
  only the MVP slice.

### For the user

At the end, ask the user to review the local commits and then manually
push so the PR shows the actual fixes.

## “Too large” / Split in sub-issues

Split is only useful when the work can be divided into **logically
independent blocks** (e.g., separate modules, separate Refactoring vs
Feature, new abstraction vs. its usage). If there is no meaningful logical
split, a larger PR is allowed.

Check in this order:

1. **Identify logical blocks.** Can you produce ≥ 2 independently,
   mergeable parts? If not → no split, even if the PR is big.
2. **Within a block: ~50 prod lines as a guideline.** If a single block
   would exceed ~50 new production lines, try to split further; if not
   feasible → accept the size.
3. **Additional split signals** (only relevant when logical blocks exist):
   - new abstraction / new interface → its own block
   - spec-contract change → its own block (when possible)
   - separates Refactoring as a prerequisite → its own block

When a split is required:

1. Create sub-issues (max 3-6) with appropriate org issue types:
   - a Bug can turn into **Refactoring** when the real core problem is
     architectural/structural change
   - **Task** is appropriate when the main issue can be broken down into
     smaller implementation/cleanup steps
2. The main PR implements only the portion that clearly satisfies the main
   issue acceptance criteria (or up to the first safe refactor slice).
3. Link sub-issues in the PR body and reference them from the main issue.

## Fix quality

- Follow the same type-narrowing guardrails as the project:
  no wide types (`Any`, `object`, unnecessary `T | None`).
- Update specs only when the real contract changes.
- Quality checks are enforced via IDE/Pre-Commit/CI; do not repeat them
  explicitly unless you need them for debugging.

## Output to user

Provide:

- Issue URL + issue number + selected org issue type
- Branch name
- PR URL (or “skipped PR creation” with a draft, if GitHub writes were not
  possible)
- Created sub-issue URLs (or none)
- A clear reminder that the user must review the commits and manually
  push (so the PR gets filled with the fixes)
