## Why

Devinfra [#58](https://github.com/fairagro/m4.2_middleware_devinfra/issues/58) landed the fleet **bashrc-free** shell
contract (synced `remoteEnv.PATH`, `scripts/bin/{k,d}`, postCreate decrypt of `.env.integration.enc` → `.env` without
auto-source). This product still keeps a deprecated `scripts/load-env.sh` forked blob and stale AGENTS/README guidance,
while `.devcontainer/product.env` (the documented overlay for `MYPYPATH` / `CST_*`) is missing on `main` after the sync
PR that introduced Compose `env_file` closed without merge.

## What Changes

- Add product-owned `.devcontainer/product.env` with `MYPYPATH` and `CST_BAKE_TARGET=api` (overlay; not synced).
- **Delete** `scripts/load-env.sh` (no remaining product delta that belongs in a sourced bashrc blob).
- Update product-local docs (`AGENTS.md`, `README.md`, `docs/python_related.md`, brief comments) to the bashrc-free
  contract — no bashrc / `setup-bashrc-load-env` / postStart load-env wiring.
- Confirm synced pieces already on `main` (no hand-edit): `devcontainer.json` `remoteEnv.PATH`, no `postStartCommand`,
  `scripts/bin/{k,d}`, postCreate decrypt.

**BREAKING** (DX only): interactive shells no longer auto-`source` `.env` or run ggshield prompts via bashrc; use
`.env` file on disk (postCreate) and `scripts/bin` / `set-dev-tokens.sh` for tokens.

## Capabilities

### New Capabilities

_None — `skip_specs: true` (tooling/DX adopt; no domain requirement deltas)._

### Modified Capabilities

_None — `skip_specs: true`._

## Impact

- Dev Container env for hooks (`MYPYPATH`) and pre-push CST (`CST_BAKE_TARGET`) via Compose `env_file`.
- Contributors who still `source scripts/load-env.sh` must switch to the shared contract.
- No runtime API / Helm / CI workflow logic changes beyond env already expected by quality hooks and Bake CST.
- Tracks product issue [#400](https://github.com/fairagro/m4.2_advanced_middleware_api/issues/400); parent Devinfra #58.
