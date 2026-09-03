# GitHub Copilot

Read [`AGENTS.md`](../AGENTS.md) and
[`openspec/principles.md`](../openspec/principles.md). Always `uv`. No
`os.environ` in application code (`ConfigWrapper` only).

When writing or reviewing code, follow Type Safety in `openspec/principles.md`
(do not widen types; no `None`-guards on non-optional values).

When performing a code review, you are the **Finder** in
[`docs/ai_review_policy.md`](../docs/ai_review_policy.md). Follow that file.
