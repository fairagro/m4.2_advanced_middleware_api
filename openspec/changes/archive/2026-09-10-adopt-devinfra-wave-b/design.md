# Adopt Devinfra Wave B — Design

## Context

See `proposal.md` for motivation (#367, Devinfra Wave B). Wave A is already on
`main` (AI review / thin Auth-B). This change aligns Dev DX: quality fragments,
hooks, Dev Container image, `versions.env`, and the YAML synced-path allowlist.
Product domain specs under `openspec/specs/` are unchanged (`skip_specs: true`).

Pilot lock-ins from harvester Wave B apply unless this repo documents an
exception ([#367 comment](https://github.com/fairagro/m4.2_advanced_middleware_api/issues/367)).

**Golden rule:** (1) Devinfra file generic enough for verbatim product use →
(2) else `.global` + product-local split → (3) only then documented local drift
on a shared path. Never silently re-patch allowlisted blobs after sync
([devinfra#57](https://github.com/fairagro/m4.2_middleware_devinfra/issues/57)).

## Goals / Non-Goals

**Goals:**

- Wave B allowlisted paths match Devinfra at the pinned SHA (no intentional drift).
- Quality gates (IDE where shared, hooks, CI) use the same fragments
  (`ruff.toml`, `mypy.ini`, `.pylintrc`, `.bandit`).
- Product overlays stay in YAML `exclude` / documented ownership gaps only.
- No Git LFS in this product’s Dev DX.
- Fleet stub approach (`stubs/` + `pyrightconfig.json`) until Devinfra syncs
  them (#67 / #64).

**Non-Goals:**

- Wave C Bake / product-app image last-stage / CST bake targets.
- Implementing Devinfra #56 (`uv sync --dev --all-packages` in shared post-create),
  #58 (shared load-env), #63 (pre-commit generic/split) inside this product PR.
- Changing HTTP/Celery/CouchDB behaviour or domain OpenSpec requirements.
- Waiting for first automated sync PR from Devinfra #13.

## Decisions

### D1: Verbatim sync from pinned Devinfra SHA

Copy allowlisted Wave B (+ refreshed Wave A policy/skills) from
`fairagro/m4.2_middleware_devinfra` at `a9740d119d0fbe96a813650121db2fab7b2e6136`.
Record the SHA in the PR description.

**Reason:** Same as Wave A / harvester pilot — single SoT.
**Alternatives:** Wait for #13; cherry-pick with local edits (forbidden).

### D2: Allowlisted pre-commit and VS Code settings stay verbatim

Do **not** maintain a product fork of `.pre-commit-config.yaml` or
`.vscode/settings.json` after sync. Path overlays (`MYPYPATH`, pylint
`--source-roots`) live in product CI env/args and docs until #63 / #57 land a
fleet contract. Stub discovery: `MYPYPATH=stubs:…` in CI/`AGENTS`, not in the
synced pre-commit YAML (#63 option A).

**Reason:** Files are on `docs/synced-paths.yaml` `allow:`; post-sync hand-edits
are the anti-pattern #63 describes.
**Alternatives:** Hybrid YAML (harvester emergency) — rejected here.

### D3: Thin product overlays only

| Path | Role |
| ---- | ---- |
| `.devcontainer/devcontainer.json` | name, workspaceFolder, volumes, PATH, postStart → bashrc helper (#65) |
| `.devcontainer/docker-compose.yml` | bind mount path (YAML exclude) |
| `AGENTS.md` | product agent notes |
| `.github/workflows/reusable-*.yml` | product CI (YAML exclude); set `MYPYPATH` / pylint roots |
| `scripts/load-env.sh`, `setup-bashrc-load-env.sh`, `install-dev-hooks.sh` | until #58 / hook repair |
| `scripts/update-apk-dependencies.sh` | until #68; default `docker/Dockerfile.api` |
| `stubs/`, `pyrightconfig.json` | until #67 / #64 |

`postCreateCommand` calls synced `scripts/devcontainer-post-create.sh` only (no
product wrapper that re-implements or patches sync).

### D4: No Git LFS

Remove product LFS setup/hooks and `*.sql` LFS rules from `.gitattributes`.
Shared Wave B already dropped LFS (#39).

### D5: Quality config fragments replace pyproject tool tables

Delete root `[tool.ruff]` / `[tool.mypy]` / `[tool.pylint.*]`. Keep `[project]`,
uv workspace, pytest, coverage, `[tool.pyright]` extraPaths as needed.

### D6: Manual adopt now, then accept sync

Same as harvester lock-in #20 — do not block on Devinfra #13.

## Risks / Trade-offs

| Risk | Mitigation |
| ---- | ---------- |
| Shared post-create still runs plain `uv sync` (#56) | Document; repair via `install-dev-hooks.sh` / manual `uv sync --dev --all-packages` until upstream |
| Verbatim pre-commit lacks product `MYPYPATH` | CI exports `MYPYPATH`; agents/docs document the same; #63 retires the gap |
| Verbatim `check-yaml` lacks Helm template exclude | Product path `helmchart/…/templates/`; keep verbatim YAML; #63 option A must add a fleet-safe exclude (harvester used `helm/`). Local smoke: `SKIP=check-yaml` until upstream |
| Markdownlint hits OpenSpec-managed trees | Do not patch synced `.markdownlint*`; wait for [#59](https://github.com/fairagro/m4.2_middleware_devinfra/issues/59). Local smoke: `SKIP=markdownlint` until rebuild + #59 |
| Verbatim VS Code `pytestArgs: ["scripts/ai/tests"]` | Known #57; do not locally “fix” discovery onto product tests only |
| Stale agent `GH_TOKEN` shadows store (#69) | `env -u GH_TOKEN …` workaround |
| Stub trees drift until #67 | Copy from harvester fleet set; drop import-untyped on covered imports |

## Migration Plan

1. Sync allowlisted files from pinned SHA; delete obsolete
   `docs/synced-paths.global.md` (SoT is `synced-paths.yaml`).
2. Apply product overlays (D3); strip pyproject tool tables (D5); drop LFS (D4).
3. Add stubs + pyrightconfig; update CI `MYPYPATH`.
4. Rebuild Dev Container; smoke `quality-check` / focused pytest / mypy with
   `MYPYPATH=stubs:…`.
5. Open draft PR with `Fixes #367` and pinned SHA.

## Open Questions

_None blocking adopt — open work is upstream (#56, #57, #58, #63, #64, #65, #67, #68)._
