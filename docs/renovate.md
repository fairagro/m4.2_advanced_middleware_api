# Renovate (shared dependency updates)

Canonical Renovate config and GitHub workflow live in this Devinfra repo and are intended for sync into the three m4.2
product repos ([#13](https://github.com/fairagro/m4.2_middleware_devinfra/issues/13) / [`docs/sync.md`](sync.md)).

| Artifact                                                              | Role                              |
| --------------------------------------------------------------------- | --------------------------------- |
| [`renovate.json`](../renovate.json)                                   | Shared Renovate config (SoT)      |
| [`.github/workflows/renovate.yml`](../.github/workflows/renovate.yml) | Per-repo self-hosted Renovate job |

**Do not** hand-edit these after sync in product checkouts — see [`docs/synced-paths.yaml`](synced-paths.yaml).

## GitHub Actions secret: `DEVINFRA_BOT_TOKEN`

The workflow does **not** use SOPS and does **not** rely on `GITHUB_TOKEN` alone.

Use **one** bot
[fine-grained personal access token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens#creating-a-fine-grained-personal-access-token)
for **both** Renovate and [product sync](sync.md), stored as repository Actions secret **`DEVINFRA_BOT_TOKEN`**
(Devinfra + each product after adoption).

### Repository access

Grant the token access to these repositories (same PAT, multi-repo resource owner selection in the PAT UI):

- `fairagro/m4.2_middleware_devinfra`
- `fairagro/m4.2_advanced_middleware_api`
- `fairagro/m4.2_sql_to_arc`
- `fairagro/m4.2_middleware_harvester`

### Repository permissions (GUI vs API)

Fine-grained PAT **GUI** labels differ from the **REST/API** permission keys used when creating tokens via the API
([permissions reference](https://docs.github.com/en/rest/authentication/permissions-required-for-fine-grained-personal-access-tokens)).
Use this mapping:

| GUI label (Create fine-grained PAT) | API permission key | Access                         | Needed for                                     |
| ----------------------------------- | ------------------ | ------------------------------ | ---------------------------------------------- |
| Metadata                            | `metadata`         | Read-only (often auto-granted) | Repo identity / baseline                       |
| Contents                            | `contents`         | Read and write                 | Clone, branches, commits (Renovate + sync)     |
| Pull requests                       | `pull_requests`    | Read and write                 | Open/update PRs (Renovate + sync)              |
| Workflows                           | `workflows`        | Read and write                 | Push changes under `.github/workflows/` (sync) |
| Issues                              | `issues`           | Read and write                 | Renovate (issue/PR comment APIs, dashboard)    |

**Do not confuse** GUI **Workflows** (`workflows`) with **Actions** (`actions`). **Workflows** is required to create or
modify workflow _files_; **Actions** covers workflow _runs_/logs and is not required for the current Renovate/sync
setup.

Example API fragment (repository permissions object):

```json
{
  "metadata": "read",
  "contents": "write",
  "pull_requests": "write",
  "workflows": "write",
  "issues": "write"
}
```

Until the secret exists, scheduled Renovate runs fail; after setting it, use **Actions → Renovate → Run workflow**. Sync
dry-run: **Actions → Sync products → Run workflow** (`dry_run=true` by default).

## Local CLI dry-run

The Dev Container pins the **Renovate npm CLI** via `RENOVATE_VERSION` in [`versions.env`](../versions.env) (`renovate`
on `PATH`). That pin is for local dry-runs only. CI runs
[`renovatebot/github-action`](../.github/workflows/renovate.yml) at its own Action version (currently `v46.2.6`) — keep
the Action major aware of the CLI major when bumping either pin; they are not the same artifact.

From the repo root (no PR creation):

```bash
renovate --version
# Config / dependency discovery only (adjust flags to your Renovate major as needed):
LOG_LEVEL=debug renovate --platform=local --dry-run=full
```

Use a GitHub token in the environment when the dry-run must query GitHub datasources (`GITHUB_COM_TOKEN` /
`DEVINFRA_BOT_TOKEN`). Prefer the personal-token helpers for interactive `gh` work (`GH_TOKEN`); the automation bot PAT
is separate from developer `GH_TOKEN`.

## Dependabot migration (products)

| Keep                                                                                    | Drop / avoid                                                                            |
| --------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| **Dependabot alerts** (Security tab) — Renovate can read vulnerability alerts on GitHub | **Dependabot version updates** (`.github/dependabot.yml`)                               |
| Prefer **Renovate** for dependency update PRs                                           | Running Dependabot version updates **and** Renovate as general updaters (duplicate PRs) |

Optional: turn off Dependabot **security update** PRs if Renovate owns security updates, so only one bot opens fix PRs.
Keep alerts enabled.

## Adoption / sync (#13)

1. Land config + workflow here; set `DEVINFRA_BOT_TOKEN` on Devinfra; smoke-test Renovate and Sync products with
   `workflow_dispatch`.
2. Sync `renovate.json`, `.github/workflows/renovate.yml`, and other allowlisted paths into API / sql-to-arc / harvester
   via [`docs/sync.md`](sync.md).
3. Set `DEVINFRA_BOT_TOKEN` per product repo for Renovate; remove Dependabot version-update config; converge API onto
   the shared config (drop divergent local rules unless documented as a thin overlay / `extends`).

Reusable `reusable-renovate.yml` is **out of scope** for now — the thin workflow is expected to stay identical across
repos via sync.
