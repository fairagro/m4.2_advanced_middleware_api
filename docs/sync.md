# Product repo sync (allowlist push)

Automation that opens pull requests in the three m4.2 product repos, copying only paths listed in
[`docs/synced-paths.yaml`](synced-paths.yaml).

**v1 scope:** sync **adds/updates** allowlisted files only. It does **not** delete paths in product repos (even if a
file was removed in Devinfra or dropped from the allowlist). Propagating deletions would be a separate follow-up if
needed.

**Sole path SoT:** [`docs/synced-paths.yaml`](synced-paths.yaml) is the only place that defines _what_ is synced
(`allow`) and the hard denylist (`exclude`). The workflow does **not** maintain a second path list (no `paths:` filter).

Tracks [#13](https://github.com/fairagro/m4.2_middleware_devinfra/issues/13).

| Artifact                                                                        | Role                                                                    |
| ------------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| [`docs/synced-paths.yaml`](synced-paths.yaml)                                   | **Sole** path SoT (`allow` / `exclude` / `overlays`)                    |
| [`scripts/sync-products.py`](../scripts/sync-products.py)                       | Read YAML, copy, open **new** sync PRs (**Devinfra-only** — not synced) |
| [`.github/workflows/sync-products.yml`](../.github/workflows/sync-products.yml) | When to run (`main` push / dispatch) — **Devinfra-only**, not synced    |

## Never hand-edit synced files (product checkouts)

In a **product** repo, every path under `allow` in [`synced-paths.yaml`](synced-paths.yaml) is a **verbatim** sync blob
after merge. Do **not**:

- patch that file in an adopt/fix PR “just this once”
- re-apply product overlays after every sync
- invent a second local copy that drifts from Devinfra

**Corrections** → open a Devinfra issue → land the change here → sync
([#13](https://github.com/fairagro/m4.2_middleware_devinfra/issues/13)). **Product-only needs** → a documented overlay /
env / product-owned path that sync does **not** overwrite (see
[Overlays and product-owned surfaces](#overlays-and-product-owned-surfaces) below).

Review-fixer follows the same rule: in products, do not `fix` synced paths — `follow-up` to Devinfra or `dismiss`
(synced — edit upstream). See [`docs/review-fixer.md`](review-fixer.md) and
[`ai_review_policy.md#synced-paths-sync-source-of-truth`](ai_review_policy.md#synced-paths-sync-source-of-truth).

## Allowlist inventory (human-readable)

Machine SoT remains [`synced-paths.yaml`](synced-paths.yaml). This table is a **guide** only — when it disagrees with
the YAML, the YAML wins. Resolve the live set with `uv run python scripts/sync-products.py --list-files`.

| Category                          | Examples on `allow` (non-exhaustive)                                                                                          |
| --------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| Sync / AI policy docs             | `docs/sync.md`, `docs/synced-paths.yaml`, `docs/ai_review_policy.md`, `docs/quality.md`, `docs/devcontainer.md`, …            |
| Agent skills / commands / prompts | `.agents/skills/{issue-fixer,review-fixer,create-issue,arctrl,gh,docker,hadolint,uv}/**`, `.cursor/commands/*`, prompts       |
| `m42-ai` package                  | `scripts/ai/**`, `scripts/bin/{gh,git}`, `scripts/{dev-tokens,set-dev-tokens}.sh`                                             |
| Quality scripts / hooks           | `scripts/quality-{check,fix}.sh`, `scripts/setup-git-hooks.sh`, `scripts/git-hooks/**`, `scripts/devcontainer-post-create.sh` |
| Python quality fragments          | `ruff.toml`, `mypy.ini`, `.pylintrc`, `.bandit`, `.pre-commit-config.yaml`                                                    |
| Markdown / IDE baseline           | `.markdownlint*`, `.prettier*`, `.vscode/settings.json`                                                                       |
| Dev Container / image pins        | `.devcontainer/Dockerfile`, `versions.env`, `.python-version`, `docker/Dockerfile.product-app.base`                           |
| Renovate                          | `renovate.json`, `.github/workflows/renovate.yml`                                                                             |
| Global prose SoT                  | `docs/surface-quality-bar.global.md`, `openspec/principles.global.md`                                                         |

**Hard excludes / never overwrite:** see `exclude` and `overlays` in the YAML (e.g. product `devcontainer.json`,
`docs/surface-quality-bar.md`, `openspec/principles.md`, `AGENTS.md`, reusable workflows, `middleware/**`).

## Overlays and product-owned surfaces

| Pattern                             | When                                                                                     | Examples                                                                                                                                                                                                                                                                                                            |
| ----------------------------------- | ---------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **`*.global` + product overlay**    | Tool or docs support a synced SoT file plus a product-local file sync must not overwrite | `surface-quality-bar.global.md` + `surface-quality-bar.md`; `principles.global.md` + `principles.md`                                                                                                                                                                                                                |
| **Env / CI inputs / wrappers**      | Config file has no merge/`extends` — keep the synced blob generic                        | `MYPYPATH`, reusable `pylint_source_roots`, CST bake env, thin product `devcontainer.json` fields (`name`, volumes)                                                                                                                                                                                                 |
| **Verbatim shared fragment**        | Fleet wants identical policy; product deltas are wrong or go upstream                    | `ruff.toml` (no product `extend` / ignore overlay — see [#60](https://github.com/fairagro/m4.2_middleware_devinfra/issues/60)), `.vscode/settings.json` (empty `pytestArgs`; test roots in each repo’s `pyproject.toml` `testpaths`)                                                                                |
| **Product-owned until split lands** | Synced blob is not yet generic enough; interim = not an overwrite target                 | `.pre-commit-config.yaml` / `devcontainer.json` ownership stories: [#63](https://github.com/fairagro/m4.2_middleware_devinfra/issues/63), [#65](https://github.com/fairagro/m4.2_middleware_devinfra/issues/65); shared `pyrightconfig.json`: [#64](https://github.com/fairagro/m4.2_middleware_devinfra/issues/64) |

Do **not** invent mypy config-merge here — stubs + `MYPYPATH` remain the product path for third-party silence
([`docs/quality.md`](quality.md)).

## Targets

| Key          | Repository                              |
| ------------ | --------------------------------------- |
| `api`        | `fairagro/m4.2_advanced_middleware_api` |
| `sql_to_arc` | `fairagro/m4.2_sql_to_arc`              |
| `harvester`  | `fairagro/m4.2_middleware_harvester`    |

## Triggers

- **Push to `main`**: live sync. The workflow compares the push `before` SHA to `HEAD` against `docs/synced-paths.yaml`
  (via `--list-files`) and skips the sync step when nothing allowlisted changed.
- **`workflow_dispatch`**: inputs `dry_run` (default **true**), `skip_api`, `skip_sql_to_arc`, `skip_harvester`.

Dry-run reports resolved files and targets without cloning or opening/closing PRs. Skip flags omit a consumer. Actions
dry-run (`workflow_dispatch` with `dry_run=true`) does **not** require `DEVINFRA_BOT_TOKEN`; live sync does.

## PR shape (one PR per sync run)

Each live sync that has allowlisted changes opens a **new** PR per product repo:

- Branch: `chore/devinfra-sync-<7-char-Devinfra-sha>` (full allowlist snapshot at that commit)
- Title includes the short SHA; body links the source Devinfra commit
- Sync does **not** force-push a rolling branch or reuse one open PR across runs
- After the new PR is created, other **open** sync PRs whose head is `chore/devinfra-sync` or `chore/devinfra-sync-*`
  get a **Superseded by #N** comment and are **closed** (not merged)
- Sync does **not** auto-merge; humans merge the latest open sync PR when ready

## Bot token (shared with Renovate)

Cross-repo PRs need a bot PAT (not `GITHUB_TOKEN` alone). Use repository Actions secret **`DEVINFRA_BOT_TOKEN`** — the
same secret as Renovate. **Canonical permission table (GUI labels + API keys):**
[`docs/renovate.md`](renovate.md#repository-permissions-gui-vs-api).

Do **not** store this token in SOPS or the repo.

CI sets `DEVINFRA_BOT_TOKEN` (and `GH_TOKEN` to the same value for `gh`) for live sync. Local live sync: export
`DEVINFRA_BOT_TOKEN`, or `GH_TOKEN` for a one-off personal-PAT test.

## Hard excludes (never copied)

Listed under `exclude` in [`docs/synced-paths.yaml`](synced-paths.yaml) (and enforced in the script even if also under
`allow`), including:

- `middleware/**`
- `openspec/specs/**`, `openspec/changes/**`
- `.github/workflows/reusable-*.yml` (products keep `uses:`)
- Product overlays and product-local Dev Container files (`overlays` / matching `exclude` entries)

## Local dry-run

From the Devinfra repo root (after `uv sync`; PyYAML comes from the project lock):

```bash
uv run python scripts/sync-products.py --list-files
uv run python scripts/sync-products.py --dry-run
uv run python scripts/sync-products.py --dry-run --skip-harvester
```

Live local sync (opens PRs) requires a bot token in the environment and `gh` auth. Always use `uv run` — not bare
`python3`.

## Adoption

1. **Actions → Sync products → Run workflow** with `dry_run=true` (no bot secret required).
2. Set `DEVINFRA_BOT_TOKEN` on Devinfra (see Renovate docs for scopes).
3. Re-run with `dry_run=false` or merge a `main` commit that touches allowlisted paths.
4. Merge the latest sync PR in each product (older ones are superseded/closed); keep consumer overlays product-owned.
