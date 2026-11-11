# Product repo sync (allowlist push)

Automation that opens pull requests in the m4.2 product repos (and optionally infrastructure), copying only paths listed
in [`docs/synced-paths.yaml`](synced-paths.yaml) for that consumer’s **profiles**.

**Scope:** sync **adds/updates** the current allowlist file set **per target** and **`git rm`s allowlist orphans** —
paths that were in that target’s resolved allowlist set at the comparison base (`github.event.before` on push) but not
at source `HEAD`. There is **no** `retire:` list; dropping a path from the relevant profile `allow` (or deleting it
upstream so it leaves the resolved set) is enough. Paths that were **never** on that target’s allowlist (consumer-only
extras) are **not** deleted.

**`SYNC-FOLLOWUP`:** when a merged Devinfra PR body or comment contains `SYNC-FOLLOWUP: <stable-id>`, live sync opens
(or reuses) a deduplicated Task issue in each **python-product** repo via `m42-ai`. Manual `workflow_dispatch` input
`followup_id` does the same without a trailer. Dry-run creates neither PRs nor issues. Infrastructure is omitted from
follow-up ensure while it is foundation-only.

**Sole path SoT:** [`docs/synced-paths.yaml`](synced-paths.yaml) defines **`profiles`** (`foundation`, `python-product`,
`gitops`, `infra-consumer`), **`targets`** (repo + profile list), and the hard denylist (`exclude` / `overlays`). There
is no top-level flat `allow`. The workflow does **not** maintain a second path list (no `paths:` filter).

**Foundation / Infra:** skills, commands, prompts, skill docs, `scripts/ai/**`, `m42-ai`, token helpers + hook helpers;
Infra pre-commit root via **`infra-consumer`** (`.pre-commit-config.infrastructure.yaml`); with **`gitops`**, also
`scripts/run-helm-lint.sh`; with **`foundation`**, also Renovate artifacts + `versions.env` (#354). Sync does **not**
copy product **`.devcontainer/*`**, `.python-version`, or the python-product `.pre-commit-config.yaml` to Infra. Unused
pins in `versions.env` on Infra do not install tools. Infra **keeps** its fat GitOps Dev Container (argocd / kind /
chart-testing / …) until a dedicated **adoption** issue; sync must never overwrite it with the verbatim product Dev
Container blob ([#352](https://github.com/fairagro/m4.2_middleware_devinfra/issues/352)). Live Infra sync stays skipped
by default until the bot checklist in
[`renovate.md`](renovate.md#slice-2-checklist-infra-renovate--sync-m42_infrastructure).

## Dev Container overlay + pin ownership (#352 / #354)

| Surface                                       | Who                                                       | Notes                                                                   |
| --------------------------------------------- | --------------------------------------------------------- | ----------------------------------------------------------------------- |
| Product `.devcontainer/*` + `.python-version` | **`python-product` only** (api / sql_to_arc / harvester)  | Verbatim sync; see [`devcontainer.md`](devcontainer.md)                 |
| Infra GitOps Dev Container                    | **Infra-owned** until adoption                            | Not on `foundation` / `gitops` / `infra-consumer` allow                 |
| Pin file `versions.env`                       | **`foundation`** (products + Infra)                       | One pin SoT; unused keys on Infra are no-ops until something reads them |
| Renovate config + workflow                    | **`foundation`** (products + Infra)                       | `renovate.json`, `.github/workflows/renovate.yml`, `docs/renovate.md`   |
| Shared / foundation-eligible pin _intent_     | Helm, **minikube** (today), git-lfs eligible, shared CLIs | Documented buckets; still one file                                      |
| python-product pin _intent_                   | Python/uv, CST, Trivy, Renovate CLI, git-cliff, …         | Same `versions.env`; product image/hooks consume them                   |
| Infra-owned until adoption                    | **argocd**, **kind**, **ct** (chart-testing)              | Stay on Infra’s image                                                   |

Planned product toolchain swap **minikube → kind** is **not** part of the #352 contract:
[Devinfra #364](https://github.com/fairagro/m4.2_middleware_devinfra/issues/364), API smoke docs
[api#670](https://github.com/fairagro/m4.2_advanced_middleware_api/issues/670).

**Consumer-safe links (synced Markdown):** after sync, relative links only resolve for paths that also ship in the
product checkout. Synced docs MUST NOT use in-repo relative links (`../…`) to targets outside `allow` (minus `exclude`).
Point at Devinfra with absolute GitHub URLs (`…/fairagro/m4.2_middleware_devinfra/blob/main/…`), or keep a plain
non-linked path name. Do **not** “fix” broken links by adding Devinfra-only automation to the product allowlist
([#86](https://github.com/fairagro/m4.2_middleware_devinfra/issues/86)).

Tracks [#13](https://github.com/fairagro/m4.2_middleware_devinfra/issues/13).

| Artifact                                                                                                                                    | Role                                                                    |
| ------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| [`docs/synced-paths.yaml`](synced-paths.yaml)                                                                                               | **Sole** path SoT (`profiles` / `targets` / `exclude` / `overlays`)     |
| [`scripts/sync-products.py`](https://github.com/fairagro/m4.2_middleware_devinfra/blob/main/scripts/sync-products.py)                       | Read YAML, copy, open **new** sync PRs (**Devinfra-only** — not synced) |
| [`.github/workflows/sync-products.yml`](https://github.com/fairagro/m4.2_middleware_devinfra/blob/main/.github/workflows/sync-products.yml) | When to run (`main` push / dispatch) — **Devinfra-only**, not synced    |

## Never hand-edit synced files (product checkouts)

In a **product** repo, every path in the effective allow for that consumer (union of its profiles in
[`synced-paths.yaml`](synced-paths.yaml)) is a **verbatim** sync blob after merge. Do **not**:

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
the YAML, the YAML wins.

- **Product checkout:** open the synced [`synced-paths.yaml`](synced-paths.yaml) in this repo. Do **not** run
  `scripts/sync-products.py` here — that script is Devinfra-only and is not present after sync.
- **Devinfra checkout:** optionally resolve the live allowlist with `--list-files` under [Local dry-run](#local-dry-run)
  (same script as in the Artifacts table).

| Category                          | Profile          | Examples (non-exhaustive)                                                                                                                                                                                                                                                                                                                                    |
| --------------------------------- | ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Sync / AI policy + skill docs     | `foundation`     | `docs/sync.md`, `docs/synced-paths.yaml`, `docs/ai_review_policy.md`, skill docs (`review-fixer`, …)                                                                                                                                                                                                                                                         |
| Agent skills / commands / prompts | `foundation`     | `.agents/skills/{issue-fixer,review-fixer,create-issue,code-review,arctrl,gh,docker,hadolint,uv}/**`, `.cursor/commands/*`, prompts                                                                                                                                                                                                                          |
| `m42-ai` + token helpers          | `foundation`     | `scripts/ai/**`, `scripts/bin/{gh,git,m42-ai}`, `scripts/{dev-tokens,set-dev-tokens}.sh`                                                                                                                                                                                                                                                                     |
| Quality / CI / Dev Container docs | split            | `docs/renovate.md` on `foundation`; `docs/quality.md`, `docs/devcontainer.md`, `docs/ci.md`, … on `python-product`                                                                                                                                                                                                                                           |
| Shell wrappers `k`/`d`            | `python-product` | `scripts/bin/{k,d}`                                                                                                                                                                                                                                                                                                                                          |
| Quality scripts / hooks           | `python-product` | `scripts/quality-{check,fix}.sh`, `scripts/setup-git-hooks.sh`, `scripts/git-hooks/**`, `scripts/update-dockerfile-pins.sh`, `scripts/prune-merged-branches.sh`, `scripts/devcontainer-post-create.sh`, `scripts/import-public-gpg-keys.sh`, `scripts/detect-version-bump.sh`, `scripts/generate-release-changelog.sh`, `scripts/install-{git-cliff,cst}.sh` |
| Pre-commit configs                | split            | product `.pre-commit-config.yaml` (`python-product`); Infra `.pre-commit-config.infrastructure.yaml` (`infra-consumer` only); helpers on `foundation` — see `docs/quality.md`                                                                                                                                                                                |
| Python quality fragments          | `python-product` | `ruff.toml`, `mypy.ini`, `.pylintrc`, `.bandit`, `pyrightconfig.json`, product `.pre-commit-config.yaml`, `scripts/run-import-linter.sh`, `scripts/run-quality-cli.sh`, `scripts/load-quality-path-env.sh`, `scripts/quality-tools-pins.txt`, `scripts/run-uv-audit.sh`                                                                                      |
| Helm lint runner                  | `gitops`         | `scripts/run-helm-lint.sh`                                                                                                                                                                                                                                                                                                                                   |
| Kubeconform install + runner      | `foundation`     | `scripts/install-kubeconform.sh`, `scripts/run-kubeconform.sh` (opt-in after `helm template`; not product helm-lint)                                                                                                                                                                                                                                         |
| Markdown / commitlint baseline    | `foundation`     | `.markdownlint*`, `.prettier*`, `package.json`, `package-lock.json`, `commitlint.config.cjs` (IDE: `.vscode/*`, `.cursorrules`, `cliff.toml` stay `python-product`)                                                                                                                                                                                          |
| Fleet ignore baseline             | `python-product` | root `.gitignore` (incl. `.docker/buildx/` + token-seed runtime; product-only paths → nested `.gitignore`; see Overlays)                                                                                                                                                                                                                                     |
| Dev Container / image pins        | split            | `.devcontainer/{Dockerfile,devcontainer.json,docker-compose.yml,starship.toml}`, `.python-version`, `docker/Dockerfile.product-app.base` on `python-product`; `versions.env` on `foundation`                                                                                                                                                                 |
| Renovate                          | `foundation`     | `renovate.json`, `.github/workflows/renovate.yml`, `docs/renovate.md`                                                                                                                                                                                                                                                                                        |
| Global prose SoT                  | `python-product` | `docs/surface-quality-bar.global.md`, `openspec/principles.global.md`                                                                                                                                                                                                                                                                                        |

**Hard excludes / never overwrite:** see `exclude` and `overlays` in the YAML (e.g. `.devcontainer/product.env`,
`docs/surface-quality-bar.md`, `openspec/principles.md`, `AGENTS.md`, `.uv-audit-ignore`, `.importlinter`, reusable
workflows, `middleware/**`).

## Overlays and product-owned surfaces

| Pattern                          | When                                                                                     | Examples                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| -------------------------------- | ---------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **`*.global` + product overlay** | Tool or docs support a synced SoT file plus a product-local file sync must not overwrite | `surface-quality-bar.global.md` + `surface-quality-bar.md`; `principles.global.md` + `principles.md` (import-linter is product-owned `.importlinter` only — not a `.global` pair; see `docs/quality.md`)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| **Env / CI inputs / wrappers**   | Config file has no merge/`extends` — keep the synced blob generic                        | `MYPYPATH`, reusable `pylint_source_roots`, CST bake env, optional `.devcontainer/product.env` (Compose `env_file`, not synced); synced `scripts/bin/{k,d}` instead of bash aliases — see [`devcontainer.md`](devcontainer.md#bashrc-free-shell-init-no-load-envsh); uv-audit accepted-risk IDs in product `.uv-audit-ignore` (read by synced `scripts/run-uv-audit.sh`)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| **Verbatim shared fragment**     | Fleet wants identical policy; product deltas are wrong or go upstream                    | `ruff.toml` ([#60](https://github.com/fairagro/m4.2_middleware_devinfra/issues/60)), `pyrightconfig.json` ([#64](https://github.com/fairagro/m4.2_middleware_devinfra/issues/64)), `.vscode/settings.json` + `.vscode/extensions.json` (recommendations match Dev Container extensions — [#118](https://github.com/fairagro/m4.2_middleware_devinfra/issues/118)), `.devcontainer/devcontainer.json` + `docker-compose.yml` (`/workspace`, basename `name`/volumes, `remoteEnv.PATH` for `.venv/bin`+`scripts/bin` — [#65](https://github.com/fairagro/m4.2_middleware_devinfra/issues/65)/[#58](https://github.com/fairagro/m4.2_middleware_devinfra/issues/58)), `.pre-commit-config.yaml` ([#63](https://github.com/fairagro/m4.2_middleware_devinfra/issues/63)), root `.gitignore` ([#62](https://github.com/fairagro/m4.2_middleware_devinfra/issues/62)) |
| **Nested `.gitignore` overlays** | Git has no root-ignore merge; product-only paths must not live in the synced root file   | e.g. `charts/.gitignore` (TLS scratch; legacy `helmchart/` until rename), `dev_environment/.gitignore` (`demo_output`) — sync never overwrites nested ignore files; do **not** append product lines to root after sync. Fleet-wide Docker Buildx / token-seed under `.docker/` belongs in the synced root baseline ([#141](https://github.com/fairagro/m4.2_middleware_devinfra/issues/141)), not a nested overlay — tracked `.docker/config.json` stays commit-able.                                                                                                                                                                                                                                                                                                                                                                                           |

Do **not** invent mypy config-merge here — third-party silence for fleet deps (`arctrl` / `fable_library`) lives in
synced `mypy.ini` / `.pylintrc` (and Ruff isort classification); `MYPYPATH` remains the product path overlay for
first-party packages ([`docs/quality.md`](quality.md)).

## Targets

| Key              | Repository                              | Profiles                                   |
| ---------------- | --------------------------------------- | ------------------------------------------ |
| `api`            | `fairagro/m4.2_advanced_middleware_api` | `foundation` + `python-product` + `gitops` |
| `sql_to_arc`     | `fairagro/m4.2_sql_to_arc`              | `foundation` + `python-product` + `gitops` |
| `harvester`      | `fairagro/m4.2_middleware_harvester`    | `foundation` + `python-product` + `gitops` |
| `infrastructure` | `fairagro/m4.2_infrastructure`          | `foundation` + `gitops` + `infra-consumer` |

Push runs **skip** `infrastructure` by default until operators complete the Slice-2 bot checklist
([`renovate.md`](renovate.md#slice-2-checklist-infra-renovate--sync-m42_infrastructure)). Dispatch can dry-run or unskip
Infra once the PAT covers that repo and the Infra secret is set.

## Triggers

- **Push to `main`**: live sync when the **product-union** allowlist **file set** or allowlisted **content** changed vs
  `before`. Passes `--orphan-base` so consumer PRs can delete delta orphans **per target**. Always collects
  `SYNC-FOLLOWUP` from the merged PR (body + comments) when a PR exists for `HEAD` (python-product repos only).
- **`workflow_dispatch`**: inputs `dry_run` (default **true**), `skip_api`, `skip_sql_to_arc`, `skip_harvester`,
  `skip_infrastructure` (default **true**), `followup_id` (optional stable id).

Dry-run reports resolved files / would-delete orphans and targets without cloning or opening/closing PRs or creating
issues. Skip flags omit a consumer. Actions dry-run (`workflow_dispatch` with `dry_run=true`) does **not** require
`DEVINFRA_BOT_TOKEN`; live sync and follow-up ensure do. Infra dry-run works without Infra repo access on the token.

## SYNC-FOLLOWUP (product local work)

Put a trailer on the **Devinfra PR** (body preferred; comments also scanned):

```text
SYNC-FOLLOWUP: remove-stubs
```

`<stable-id>` must be a non-empty token (`[A-Za-z0-9][A-Za-z0-9._/-]*`). Re-runs reuse an open product issue labeled
`sync-followup:<id>`.

**Author / agent checklist:** if copy/`git rm` is not enough for products (never-allowlisted paths, CI env, call-site
ignores), add `SYNC-FOLLOWUP: <id>` before merge — or run Actions → Sync products with `followup_id` after merge.

Plumbing: `uv run m42-ai pr-for-commit`, `sync-followup-ids`, `sync-followup-ensure` (see `scripts/ai/README.md`). Issue
body template: [`docs/sync-followup-issue.md`](sync-followup-issue.md) (Devinfra-only).

## PR shape (one PR per sync run)

Each live sync that has allowlisted changes opens a **new** PR per product repo:

- Branch: `chore/devinfra-sync-<7-char-Devinfra-sha>` (full allowlist snapshot at that commit)
- Title includes the short SHA; body links the source Devinfra commit
- Sync does **not** force-push a rolling branch or reuse one open PR across runs
- After the new PR is created, other **open** sync PRs whose head is `chore/devinfra-sync` or `chore/devinfra-sync-*`
  get a **Superseded by #N** comment and are **closed** (not merged)
- Sync does **not** auto-merge; humans merge the latest open sync PR when ready

### Prune merged / superseded branches

Product checkouts accumulate local and `origin` heads after merges (incl. squash) and after sync closes older PRs as
**Superseded by #N**. Use the synced helper (dry-run by default):

```bash
./scripts/prune-merged-branches.sh
./scripts/prune-merged-branches.sh --apply
```

It deletes a branch only when it is an ancestor of `origin/main`, the head of a **MERGED** PR into `main`, or a tip that
still matches (no unique commits vs) a **CLOSED** PR head commit that reaches a MERGED PR via a recursive
`Superseded by #<n>` chain. Reusing a closed/superseded head **name** for new work is not enough to delete — the current
tip SHA must still be that closed PR’s head (or an ancestor of it). It never deletes `main`, the current branch, or
heads of **OPEN** PRs. Requires `gh` on `PATH` (Dev Container wrappers). Dry-run is the default (`--apply` deletes).

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

From the **Devinfra** repo root only (after `uv sync`; PyYAML comes from the project lock). Product checkouts do not
ship `scripts/sync-products.py` — use [`synced-paths.yaml`](synced-paths.yaml) there instead.

```bash
uv run python scripts/sync-products.py --list-files
uv run python scripts/sync-products.py --list-files --target infrastructure
uv run python scripts/sync-products.py --list-files --ref HEAD^
uv run python scripts/sync-products.py --dry-run --skip-infrastructure
uv run python scripts/sync-products.py --dry-run --orphan-base HEAD^ --skip-api --skip-sql-to-arc --skip-harvester
uv run python scripts/sync-products.py --dry-run --skip-harvester
```

Live local sync (opens PRs) requires a bot token in the environment and `gh` auth. Always use `uv run` — not bare
`python3`.

## Adoption

1. **Actions → Sync products → Run workflow** with `dry_run=true` (no bot secret required).
2. Set `DEVINFRA_BOT_TOKEN` on Devinfra (see Renovate docs for scopes).
3. Re-run with `dry_run=false` or merge a `main` commit that touches allowlisted paths.
4. Merge the latest sync PR in each product (older ones are superseded/closed); keep consumer overlays product-owned.
