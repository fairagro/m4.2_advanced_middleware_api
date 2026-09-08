# Surface quality bar — path map (global)

Default **path→surface** map for Finder/Fixer triage. Synced from Devinfra into product repos (**do not hand-edit**
after sync).

**Rules** (how the bar affects step 5, nits, dismiss) live in
[`docs/ai_review_policy.md`](ai_review_policy.md#surface-quality-bar-fixer-triage). This file is only the map. Paths
consumers must not hand-edit after sync: [`docs/synced-paths.global.md`](synced-paths.global.md).

**Product overlay:** add extra rows in local [`docs/surface-quality-bar.md`](surface-quality-bar.md) (create when
needed). Sync of this `.global.md` file MUST NOT overwrite that product file. Do not edit `docs/ai_review_policy.md`
solely to add a path row.

| Surface                           | Typical paths                                                                                                                         | Bar (what must work)                                                                                                  | Default for exotic edge cases                                                                |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| **Product / domain**              | `middleware/*/src/`, public APIs, workers, persisted state                                                                            | Full: real callers, contracts, security, data integrity                                                               | Fix when correct + in PR                                                                     |
| **Shared Devinfra scripts**       | `scripts/` except `scripts/ai/` (quality, CST, tokens, Dev Container helpers); reusable workflow glue that only sources those scripts | Documented Dev Container + contributor/CI path with **contracted** shared files (e.g. complete synced `versions.env`) | `dismiss` (practicality Low): host-only, speculative incomplete-config, “caller forgot sync” |
| **Agent plumbing**                | `scripts/ai/`, skill/CLI wiring used by `/issue-fixer` etc.                                                                           | Happy path in the Linux Dev Container with normal skill/CLI args                                                      | `dismiss` (practicality Low)                                                                 |
| **Docs / OpenSpec / entrypoints** | `docs/`, `openspec/`, `.cursor/commands`, prompts                                                                                     | Supported cadence runnable as written; fail bars match reality                                                        | **Low**/dismiss unless cadence breaks                                                        |
| **Vendor skills**                 | `.agents/skills/{gh,docker,hadolint,uv}`                                                                                              | Do not hand-edit; pin/update via install                                                                              | `dismiss` drive-by edits                                                                     |

When classifying a path: use this global table first, then any additional rows in the product-local overlay.
