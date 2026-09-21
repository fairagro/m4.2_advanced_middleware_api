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
| Issues                              | `issues`           | Read and write                 | Renovate + sync `SYNC-FOLLOWUP` product issues |

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

### `gitAuthor` (avoid Mend default)

Self-hosted Renovate without `gitAuthor` falls back to Mend’s `renovate@whitesourcesoftware.com`, which logs a WARN and
can mark commits **Unverified** under Vigilant Mode
([renovate discussion #39309](https://github.com/renovatebot/renovate/discussions/39309)).

Shared [`renovate.json`](../renovate.json) sets `gitAuthor` to the GitHub user that owns `DEVINFRA_BOT_TOKEN`, using
that user’s noreply address (`Name <id+login@users.noreply.github.com>`). Today that is
`Carsten Scharfenberg <138563220+Zalfsten@users.noreply.github.com>`. If the PAT owner changes, update `gitAuthor` to
match (or set `RENOVATE_GIT_AUTHOR` in the workflow instead).

## Local CLI dry-run

The Dev Container pins the **Renovate npm CLI** via `RENOVATE_VERSION` in [`versions.env`](../versions.env) (`renovate`
on `PATH`). That pin is for local dry-runs only. CI runs
[`renovatebot/github-action`](../.github/workflows/renovate.yml) at its own Action version (currently `v46.2.6`) — keep
the Action major aware of the CLI major when bumping either pin; they are not the same artifact.

The **npm CLI** itself is pinned as `NPM_VERSION` in `versions.env` (regex custom manager, `datasourceTemplate: npm`,
grouped under **npm toolchain** with Prettier / markdownlint-cli2 / OpenSpec / Renovate CLI). It is independent of
`NODE_VERSION` (Node tarball). Bump npm in Devinfra via Renovate; do not hand-edit the pin in product checkouts.

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

**Hard requirement after Renovate enablement:** product repos MUST **not** ship `.github/dependabot.yml` (or any
version-update schedule). Alerts are configured in the repo Security tab — they do **not** need that file. Leaving
`package-ecosystem: uv` / `devcontainers` / `docker` version updates enabled reopens weekly PRs that fight Renovate and
Devinfra sync SoT (seen on harvester / sql-to-arc). Spot-check: delete the file in every product that still has it;
close open Dependabot version-update PRs that only touch shared or Renovate-owned surfaces.

## Adoption / sync (#13)

1. Land config + workflow here; set `DEVINFRA_BOT_TOKEN` on Devinfra; smoke-test Renovate and Sync products with
   `workflow_dispatch`.
2. Sync `renovate.json`, `.github/workflows/renovate.yml`, and other allowlisted paths into API / sql-to-arc / harvester
   via [`docs/sync.md`](sync.md).
3. Set `DEVINFRA_BOT_TOKEN` per product repo for Renovate; **delete** `.github/dependabot.yml` if present (version
   updates off; alerts stay); converge API onto the shared config (drop divergent local rules unless documented as a
   thin overlay / `extends`).

### What product Renovate must not bump

Shared `renovate.json` disables updates in the three product repos for **Devinfra-owned** pins/files (SoT stays here;
products get them via sync):

| Disabled in products                                              | Why                                                                        |
| ----------------------------------------------------------------- | -------------------------------------------------------------------------- |
| `versions.env`, `.python-version`                                 | Toolchain SoT — bump in Devinfra only                                      |
| `package.json`, `package-lock.json`                               | Synced npm toolchain SoT (Prettier / markdownlint-cli2, …)                 |
| `docker/Dockerfile.product-app.base`                              | Synced base image                                                          |
| `.devcontainer/Dockerfile`                                        | Synced Dev Container image                                                 |
| `.devcontainer/devcontainer.json`                                 | Synced Dev Container config (including feature pins)                       |
| `.devcontainer/devcontainer-lock.json`                            | Feature lock — bump/generate in Devinfra if committed; not SoT in products |
| `.devcontainer/docker-compose.yml`, `.devcontainer/starship.toml` | Synced Dev Container compose / prompt                                      |
| `renovate.json`, `.github/workflows/renovate.yml`                 | Shared Renovate SoT                                                        |
| `.github/workflows/codeql.yml`                                    | Shared CodeQL SoT — toolchain pins stay in `versions.env`                  |
| Package `docker/dockerfile` (`# syntax=…`)                        | Frontend pin tracked in Devinfra; avoid duplicate product PRs              |

**Dev Container features / locks:** bump `ghcr.io/devcontainers/features/…` (and any `devcontainer-lock.json`) in
**Devinfra**, then sync. Products must not merge Dependabot or Renovate PRs that only retarget shared `.devcontainer/*`
SoT. Devinfra does not currently commit `devcontainer-lock.json`; do not treat a product-only lock edit as the SoT.

Product Renovate **still** updates product-local deps (e.g. `middleware/` pep621, product last-stage `FROM` images,
product-only workflows other than synced CodeQL/Renovate). Close any open product PRs that only touch the disabled paths
after this config is synced.

### Manual Dockerfile pins (not Renovate)

Shared Renovate does **not** bump Alpine `apk add pkg=X.Y.Z-rN` pins from APKINDEX, nor ad-hoc inline `name==…` pip pins
inside product Dockerfiles. For those, run the synced helper:

```bash
./scripts/update-dockerfile-pins.sh
./scripts/update-dockerfile-pins.sh docker/Dockerfile.<component>
```

With no path, it updates every `docker/Dockerfile.*` except `Dockerfile.product-app.base`. Pass a path to limit to one
file. It does **not** write `*.bak` sidecars — use git to roll back. It refreshes apk pins (APKINDEX main + community)
and Dockerfile `name==` pins from PyPI. It does **not** edit `versions.env` (Devinfra Renovate + sync). After sync,
remove divergent local copies (`update-apk-dependencies.sh`, `update-docker-pins.sh`, etc.).

Reusable `reusable-renovate.yml` is **out of scope** for now — the thin workflow is expected to stay identical across
repos via sync.
