# Product repo sync (allowlist push)

Automation that opens pull requests in the three m4.2 product repos, copying only paths listed in
[`docs/synced-paths.yaml`](synced-paths.yaml).

**v1 scope:** sync **adds/updates** allowlisted files only. It does **not** delete paths in product repos (even if a
file was removed in Devinfra or dropped from the allowlist). Propagating deletions would be a separate follow-up if
needed.

**Sole path SoT:** [`docs/synced-paths.yaml`](synced-paths.yaml) is the only place that defines _what_ is synced
(`allow`) and the hard denylist (`exclude`). The workflow does **not** maintain a second path list (no `paths:` filter).

Tracks [#13](https://github.com/fairagro/m4.2_middleware_devinfra/issues/13).

| Artifact                                                                        | Role                                                                 |
| ------------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| [`docs/synced-paths.yaml`](synced-paths.yaml)                                   | **Sole** path SoT (`allow` / `exclude` / `overlays`)                 |
| [`scripts/sync-products.py`](../scripts/sync-products.py)                       | Read YAML, copy, open/update PRs (**Devinfra-only** — not synced)    |
| [`.github/workflows/sync-products.yml`](../.github/workflows/sync-products.yml) | When to run (`main` push / dispatch) — **Devinfra-only**, not synced |

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

Dry-run reports resolved files and targets without cloning or opening PRs. Skip flags omit a consumer. Actions dry-run
(`workflow_dispatch` with `dry_run=true`) does **not** require `DEVINFRA_BOT_TOKEN`; live sync does.

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
4. Merge sync PRs in each product; keep consumer overlays product-owned.
