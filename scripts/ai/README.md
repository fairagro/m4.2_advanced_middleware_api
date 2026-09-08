# m42-ai — agent GitHub/git plumbing

Small Python CLI for deterministic GitHub/git work used by `/review-fixer`, `/create-issue`, and `/issue-fixer`.

Workspace member of the repo-root [`pyproject.toml`](../../pyproject.toml) (`tool.uv.workspace` → `scripts/ai`). After
`uv sync` at the repo root, `m42_ai` is editable in `.venv` so the IDE can resolve imports when that interpreter is
selected.

## Run

From the **repo root** (preferred):

```bash
uv sync
uv run m42-ai --help
uv run m42-ai review-open --pr 22
```

Equivalent (still supported): `uv run --project scripts/ai m42-ai …`.

Works on a **host** or in the Dev Container. Auth is whatever `gh` on your `PATH` uses (`GH_TOKEN` / `gh auth`) — the
Dev Container token store and `scripts/bin/gh` wrapper are optional and DC-only. GitHub commands need a repo context
(`gh` cwd / remotes), unless you pass `--owner` / `--repo` where the command supports them.

## Commands

| Command                         | Role                                                                                  |
| ------------------------------- | ------------------------------------------------------------------------------------- |
| `auth-status`                   | Probe `gh auth` as JSON; exit `1` when not ok                                         |
| `review-open --pr N`            | One GraphQL fetch; JSON of unresolved AI threads + latest AI review body / suppressed |
| `review-reply`                  | `in_reply_to` on a review comment, or `--conversation` PR comment                     |
| `review-resolve --thread-id ID` | `resolveReviewThread`                                                                 |
| `issue-view --issue N`          | Stable triage JSON (type, labels, body, url, triage:\* extract)                       |
| `issue-create`                  | Type + severity/cost (+ optional `--practicality`, `--parent`)                        |
| `issue-branch --issue N`        | Ensure `issue-N-slug` checked out from base (no commit / push / PR)                   |
| `branch-ahead`                  | JSON ahead count vs `origin/<base>`; exit `1` when tip is not ahead                   |
| `issue-start --issue N`         | Ensure branch, push when ahead of base, draft PR with `Fixes #N` (no empty commit)    |
| `pr-strip-footer --pr N`        | Remove trailing “Made with Cursor” (and similar) footers from a PR body               |

## Tests

From the repo root (pytest configured in root `pyproject.toml`):

```bash
uv run pytest
```

Fixtures only — no live GitHub in CI.
