# Synced paths allowlist (global)

Canonical paths synced from **Devinfra** into product repos. Consumers MUST **not** hand-edit these after sync — land
shared fixes in [m4.2_middleware_devinfra](https://github.com/fairagro/m4.2_middleware_devinfra) first, then sync
([#13](https://github.com/fairagro/m4.2_middleware_devinfra/issues/13)).

`/review-fixer` uses this list in **product** checkouts: never `fix` these trees locally; see
[`docs/ai_review_policy.md`](ai_review_policy.md#synced-paths-sync-source-of-truth) and
[`.agents/skills/review-fixer/SKILL.md`](../.agents/skills/review-fixer/SKILL.md).

Until sync automation owns the manifest, keep this list aligned with Wave A / sync inventory by hand.

## Allowlist (do not hand-edit in consumers)

| Path / glob                                                           | Notes                                       |
| --------------------------------------------------------------------- | ------------------------------------------- |
| `docs/ai_review_policy.md`                                            | Finder/Fixer policy                         |
| `docs/surface-quality-bar.global.md`                                  | Default path→surface map                    |
| `docs/synced-paths.global.md`                                         | This allowlist                              |
| `docs/review-fixer.md`, `docs/create-issue.md`, `docs/issue-fixer.md` | Thin fixer indexes                          |
| `.cursor/BUGBOT.md`                                                   | Bugbot Finder entry                         |
| `.github/copilot-instructions.md`                                     | Copilot Finder entry                        |
| `.cursor/commands/{review,create,issue}-fixer.md`                     | Cursor slash commands                       |
| `.github/prompts/{review,create,issue}-fixer.prompt.md`               | Copilot prompts                             |
| `.agents/skills/{review,create,issue}-fixer/**`                       | First-party fixer skills                    |
| `.agents/skills/arctrl/**`                                            | First-party arctrl skill                    |
| `.agents/skills/{gh,docker,hadolint,uv}/**`                           | Vendor skills (reinstall via `gh skill`)    |
| `scripts/ai/**`                                                       | `m42-ai` CLI + tests + README               |
| `scripts/dev-tokens.sh`, `scripts/set-dev-tokens.sh`                  | Personal token helpers                      |
| `scripts/bin/gh`, `scripts/bin/git`                                   | Auth PATH wrappers                          |
| `openspec/principles.global.md`                                       | Shared principles base                      |
| `docker/Dockerfile.product-app.base`                                  | Shared product-app image base (when synced) |
| Shared quality / hooks / Dev Container fragments shipped by sync      | As listed in sync PRs / Wave docs           |

Globs match the whole tree under that prefix. Exact files listed above are also covered when sync ships them.

## Product-local overlays (MAY edit in consumers)

| Path                               | Role                                                              |
| ---------------------------------- | ----------------------------------------------------------------- |
| `docs/surface-quality-bar.md`      | Extra path→surface rows (sync of `.global.md` must not overwrite) |
| `openspec/principles.md`           | Repo-local principles extension                                   |
| `AGENTS.md`                        | Product agent notes (outside synced Finder entries)               |
| PR description / product-only docs | Not synced; fix locally when the finding is product-owned         |

Do **not** satisfy a synced-path finding by editing a `.global` / allowlisted file in the consumer. Prefer fixing the
overlay only when the concern is documented as overlay-owned.
