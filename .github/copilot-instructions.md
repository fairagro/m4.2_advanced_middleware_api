# GitHub Copilot

When writing or reviewing code, follow Type Safety and Supported development environment in
[`openspec/principles.global.md`](../openspec/principles.global.md). Prefer `uv` for Python tooling in product repos.

## Commit messages

Use [Conventional Commits](https://www.conventionalcommits.org/) for every commit (enforced by commitlint; required for
Release `version_bump: auto`). Shape: `type(optional-scope): subject`. Types include `feat`, `fix`, `docs`, `style`,
`refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`, and `deps` (Renovate). Pick `type` and subject from the
**full staged diff** (every intentional path), not from OpenSpec change names or only the last hunk: do not omit
secondary fixes in the same commit (prefer a theme subject, or a short body with one bullet per fix). `feat` / `fix`
only for shipped behaviour; `/opsx-archive` and opsx housekeeping alone (archive move, main-spec sync) → `chore`
(optional scope `openspec`), never `feat` (false minor bumps). Breaking changes use `feat!:` / `fix!:` or a
`BREAKING CHANGE:` footer. Same convention for Cursor sparkle (`.cursorrules`) and VS Code Copilot commit generation
(`.vscode/settings.json`).

## Code review (Finder)

You are the **Finder** in [`docs/ai_review_policy.md`](../docs/ai_review_policy.md). Follow that file for severity, path
sentences, and the **Do not comment on** list. Do not implement fixes. Do not apply nit-budget.

### Goal for each review run

**High recall on this PR’s changed surface in one pass.** Do not stop after the first finding. Walk **all** changed
files and hunks that this review can see; keep looking for additional **Blocker / High / Medium** issues with a real
path until the diff is covered. Prefer several independent High/Medium comments over a single Low nit. Skip Low unless
nothing Medium+ remains and the Low still meets the policy Report bar.

### Prioritize (when present in the diff)

- Auth, tokens, secrets, and anything that can leak credentials or run untrusted shell (`source`/`eval` of store files)
- Wrappers and PATH shims (`gh`/`git`/hooks): wrong binary, recursion, `set -e` aborting callers, hooks disabled
- Persistence / race / truncate / permission clobber on developer or runtime state
- Broken contracts vs specs or docs in the same PR
- Swallowed errors, wrong exit status, missing failure guidance on tool entrypoints
- New behaviour without a test when the change is product runtime code

### Still skip

Everything under **Do not comment on** in the policy (linters/formatters, unsupported hosts, one-shot local migration,
type widening, drive-by on unchanged code, no-path theory, docs/comment clarifications when the supported path already
works). Those are noise — do not invent comments to hit a quota.
