# Path conventions

Shared naming and path conventions for the three m4.2 product repos and this Devinfra repo. Later extracts (tokens
helpers, Dev Container sync, quality scripts) MUST follow these rules.

This document is **documentation only**. It does not rename existing Docker volumes.

Issue: [#3](https://github.com/fairagro/m4.2_middleware_devinfra/issues/3).

## Product slugs

Historical short slugs (docs / older volume names). Shared `devcontainer.json` now derives volume `source=` from
`${localWorkspaceFolderBasename}` (the opened folder name), not these slugs:

| Repository                     | product-slug (legacy)  |
| ------------------------------ | ---------------------- |
| `m4.2_advanced_middleware_api` | `middleware-api`       |
| `m4.2_sql_to_arc`              | `sql-to-arc`           |
| `m4.2_middleware_harvester`    | `middleware-harvester` |
| `m4.2_middleware_devinfra`     | `middleware-devinfra`  |

## Personal tokens

Personal developer tokens (e.g. `GH_TOKEN`, `GITGUARDIAN_API_KEY`) are **per-product Dev Container**, not shared across
containers on the same machine.

| Environment   | Path                         |
| ------------- | ---------------------------- |
| Dev Container | `/commandhistory/tokens.env` |

The path string is the same everywhere; isolation comes from each product's own bashhistory volume. There is **no**
supported host `~/.config/…` token store — personal-token helpers (`dev-tokens.sh`, `set-dev-tokens.sh`,
`scripts/bin/gh`, `scripts/bin/git`) are **Dev Container only**. Other scripts (quality, CST, `load-versions-env`,
`m42-ai`) may run on a host checkout; see [Script environments](quality.md#script-environments). Shell PATH for
`.venv/bin` and `scripts/bin` (including `k`/`d` wrappers) comes from Dev Container `remoteEnv` — see
[`docs/devcontainer.md`](devcontainer.md#bashrc-free-shell-init-no-load-envsh); do **not** patch `~/.bashrc` for tokens
or load-env.

**Store is the sole source:** sourcing `dev-tokens.sh` (including via `scripts/bin/gh`) always applies
`/commandhistory/tokens.env` for `GH_TOKEN` / `GITGUARDIAN_API_KEY`. A non-empty process env value does **not** override
the store (stale agent `GH_TOKEN` cannot shadow a freshly written store). Missing or empty store entries unset the
variable. Set or refresh tokens with `source ./scripts/set-dev-tokens.sh`.

## Docker volumes

Shared `devcontainer.json` (verbatim sync) names volumes:

- `${localWorkspaceFolderBasename}-bashhistory` → `/commandhistory`
- `${localWorkspaceFolderBasename}-gh-config` → `/home/vscode/.config/gh`

Do **not** hardcode another product’s volume prefix into synced JSON. Renaming/migrating data from legacy
`<product-slug>-*` volumes is a one-time local rebuild concern (see [`docs/devcontainer.md`](devcontainer.md)).

In-container workspace path is **`/workspace`** for all middleware repos (Compose bind + `workspaceFolder`).

## Package root

Product application packages live under a repo-relative `middleware/` tree:

```text
middleware/<package>/
```

Shared quality tooling and pre-commit hooks MAY target `middleware/` as a whole. This Devinfra repository has **no**
product `middleware/` packages.
