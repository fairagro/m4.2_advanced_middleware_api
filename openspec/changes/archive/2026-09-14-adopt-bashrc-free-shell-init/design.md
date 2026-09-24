## Context

See `proposal.md` — Why. On `main` after Devinfra sync: synced `.devcontainer/devcontainer.json` already sets
`remoteEnv.PATH` to `.venv/bin` + `scripts/bin`, has no `postStartCommand`, and Compose optionally loads
`.devcontainer/product.env` (`required: false`). Shared `scripts/devcontainer-post-create.sh` decrypts
`.env.integration.enc` → `.env` (file only). Product still ships `scripts/load-env.sh` (PATH / MYPYPATH / CST aliases /
ggshield nudge / SOPS decrypt+source / `dev-tokens.sh`). `setup-bashrc-load-env.sh` is already gone. Golden rule: do not
hand-edit allowlisted synced blobs; `product.env` and `AGENTS.md` are overlays.

Product domain specs under `openspec/specs/` are unchanged (`skip_specs: true`).

## Goals / Non-Goals

**Goals:**

- One product overlay for hook/CST env: `.devcontainer/product.env`.
- Remove the deprecated load-env forked surface and stale product docs that still describe bashrc/postStart.
- Preserve CI/hooks behavior that already expects `MYPYPATH` / Bake CST via env (not bashrc).

**Non-Goals:**

- Re-adding `postStartCommand` or bashrc mutation.
- Auto-`source` of `.env` into every interactive shell (explicitly out of fleet contract).
- Changing synced `devcontainer.json` / Compose / postCreate / `scripts/bin`.
- Migrating legacy kubectl multi-resource aliases (`kda` / `kga` / `ksn`) into wrappers.

## Decisions

### D1: Delete `load-env.sh` entirely (not shrink)

**Choice:** Remove the file. Product deltas that remain are only `MYPYPATH` and `CST_BAKE_TARGET` → `product.env`.

**Alternatives:** Keep a thin sourced script that only exports those two vars — rejected; duplicates the Compose overlay
and invites bashrc reintroduction.

### D2: Recreate `product.env` on this issue branch

**Choice:** Commit `.devcontainer/product.env` with the same `MYPYPATH` string as former `load-env.sh` / CQ `mypy_path`,
plus `CST_BAKE_TARGET=api` when Bake exists (always on this repo).

**Alternatives:** Rely on developers exporting vars manually — rejected; hooks fail in a fresh Dev Container without
overlay after bashrc removal.

### D3: Docs are product overlays only

**Choice:** Update `AGENTS.md`, `README.md`, `docs/python_related.md`, and short comments that name load-env. Leave
synced `docs/devcontainer.md` (already documents bashrc-free) untouched.

### D4: `.env` consumption

**Choice:** postCreate writes `.env`; pytest/conftest and tools that need secrets read the file themselves. No shell
auto-source. Personal tokens stay on `scripts/bin/gh|git` + `set-dev-tokens.sh`.

## Risks / Trade-offs

| Risk                                              | Mitigation                                                                       |
| ------------------------------------------------- | -------------------------------------------------------------------------------- |
| Fresh container without rebuild misses `env_file` | Document recreate Dev Container after merge; Compose already wires `product.env` |
| Contributors still source deleted `load-env.sh`   | AGENTS/README point at bashrc-free table; delete fails loudly                    |
| Loss of `kda`/`kga`/`ksn` aliases                 | Accept fleet contract (`k`/`d` wrappers only); no product wrapper sprawl         |
| Tests expect env vars already in shell            | Existing conftest / dotenv patterns; postCreate still materializes `.env`        |

## Migration Plan

1. Land overlay + delete + doc edits on `issue-400-*`; draft PR with `Fixes #400`.
2. After merge: rebuild/recreate Dev Container so Compose loads `product.env`.
3. No rollback of synced JSON; restore `load-env.sh` from git history only if a true product delta reappears (prefer
   extending `product.env` instead).

## Open Questions

_None._
