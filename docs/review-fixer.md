# Review-fixer conventions

Shared `/review-fixer` triages Copilot and Bugbot PR review comments using the AI review policy: fix high-risk and
in-budget nits, dismiss the rest, at most one Medium+ follow-up. Canonical skill:
[`.agents/skills/review-fixer/SKILL.md`](../.agents/skills/review-fixer/SKILL.md). Policy:
[`ai_review_policy.md`](ai_review_policy.md). Synced path allowlist (never patch these in product checkouts):
[`synced-paths.global.md`](synced-paths.global.md).

Issue: [#5](https://github.com/fairagro/m4.2_middleware_devinfra/issues/5).

## Workflow (summary)

- Process **open** AI work only — start with `uv run m42-ai review-open --pr <n>` (not raw GraphQL). Triage unresolved
  threads **and** `summary_only_findings` from every AI review (not only the latest).
- Two phases when anything is `fix`: local fixes + dismiss/follow-up replies first (**no commit**); `Fixed in <sha>`
  only after the user commits.
- In **product** repos: do not `fix` paths on [`synced-paths.global.md`](synced-paths.global.md); `follow-up` to
  Devinfra or `dismiss` (synced — upstream) instead.
- Follow-ups open via [`/create-issue`](create-issue.md): **linked** by default; `relation: sub-of #<issue_number>` only
  when the PR has `Fixes #<issue_number>` and the deferred item is remaining acceptance criteria of that issue.

## Auth

Same personal-token helpers — see root README **Personal tokens** and `scripts/bin/gh`.
