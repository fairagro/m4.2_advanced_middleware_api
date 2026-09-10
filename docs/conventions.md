# Path conventions

Shared naming and path conventions for the three m4.2 product repos and this Devinfra repo. Later extracts (tokens
helpers, Dev Container sync, quality scripts) MUST follow these rules.

This document is **documentation only**. It does not rename existing Docker volumes.

Issue: [#3](https://github.com/fairagro/m4.2_middleware_devinfra/issues/3).

## Product slugs

Short slugs identify a product in **Docker volume names**:

| Repository                     | product-slug           |
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
`m42-ai`) may run on a host checkout; see [Script environments](quality.md#script-environments).

## Docker volumes

Named volumes follow:

- `<product-slug>-bashhistory` → mount at `/commandhistory`
- `<product-slug>-gh-config` → mount at `/home/vscode/.config/gh` (when used)

Product `devcontainer.json` overlays own the `source=` names. Shared Devinfra files MUST NOT hardcode another product's
volume name. Renaming existing volumes is out of scope for this conventions doc (migrate later if needed).

## Package root

Product application packages live under a repo-relative `middleware/` tree:

```text
middleware/<package>/
```

Shared quality tooling and pre-commit hooks MAY target `middleware/` as a whole. This Devinfra repository has **no**
product `middleware/` packages.
