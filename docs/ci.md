# Reusable CI workflows

Canonical GitHub Actions for the three m4.2 product repos live in this repository:

| Workflow            | Path                                                                                                                                                                                      |
| ------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Code quality        | [`.github/workflows/reusable-code-quality.yml`](https://github.com/fairagro/m4.2_middleware_devinfra/blob/main/.github/workflows/reusable-code-quality.yml)                               |
| Image / SBOM checks | [`.github/workflows/reusable-check.yml`](https://github.com/fairagro/m4.2_middleware_devinfra/blob/main/.github/workflows/reusable-check.yml)                                             |
| Docker build        | [`.github/workflows/reusable-build.yml`](https://github.com/fairagro/m4.2_middleware_devinfra/blob/main/.github/workflows/reusable-build.yml)                                             |
| Docker release      | [`.github/workflows/reusable-release.yml`](https://github.com/fairagro/m4.2_middleware_devinfra/blob/main/.github/workflows/reusable-release.yml)                                         |
| Helm final release  | [`.github/workflows/reusable-helm-release.yml`](https://github.com/fairagro/m4.2_middleware_devinfra/blob/main/.github/workflows/reusable-helm-release.yml)                               |
| Helm pre-release    | [`.github/workflows/reusable-helm-pre-release.yml`](https://github.com/fairagro/m4.2_middleware_devinfra/blob/main/.github/workflows/reusable-helm-pre-release.yml)                       |
| Renovate (per-repo) | [`.github/workflows/renovate.yml`](../.github/workflows/renovate.yml) + [`renovate.json`](../renovate.json) — see [docs/renovate.md](renovate.md)                                         |
| CodeQL (per-repo)   | [`.github/workflows/codeql.yml`](../.github/workflows/codeql.yml) — thin synced workflow; see below                                                                                       |
| Sync products       | [`.github/workflows/sync-products.yml`](https://github.com/fairagro/m4.2_middleware_devinfra/blob/main/.github/workflows/sync-products.yml) — allowlist push; see [docs/sync.md](sync.md) |

Dockerfile pins Renovate skips (`apk=…-rN`, inline `name==…`): synced
[`scripts/update-dockerfile-pins.sh`](../scripts/update-dockerfile-pins.sh) — see
[Manual Dockerfile pins](renovate.md#manual-dockerfile-pins-not-renovate).

**Stay product-local (not shared here):** PyPI / TestPyPI publish jobs and ns-pages workflows (API today).

Renovate is a **thin per-repo workflow** (not `workflow_call`), synced like other shared files. Product sync is likewise
a thin Devinfra-hosted job that opens PRs in the three product repos. Both use one bot PAT via repository secret
`DEVINFRA_BOT_TOKEN` — see [`docs/renovate.md`](renovate.md) and [`docs/sync.md`](sync.md). Same-repo release/Helm/GHCR
jobs keep using the automatic `secrets.GITHUB_TOKEN` where that is enough.

**CodeQL** is likewise a **thin per-repo workflow** (synced; not `reusable-*.yml`). Triggers: `pull_request` → `main`
plus a weekly schedule. Python/uv pins come from [`versions.env`](../versions.env) via `scripts/load-versions-env.sh`
and `uv sync --dev --all-packages` (same bootstrap family as reusable code-quality). Product Renovate must not bump the
synced `codeql.yml` — see [`docs/renovate.md`](renovate.md). Products pick up the file on the next Devinfra sync
([#13](https://github.com/fairagro/m4.2_middleware_devinfra/issues/13)); until then divergent local CodeQL copies may
still attract shadow pin PRs.

Product-distinguishing names use **`workflow_call` inputs** (e.g. `image_base_name`, `chart_dir`) — do not rely on
silent repository Variables for correct identity.

## Product app images (Bake base + last stage)

**BREAKING (issue #36):** `reusable-build.yml` builds with **Docker Buildx Bake only**. There is **no** monolith
fallback to `docker build -f docker/Dockerfile.<component>`. Do **not** bump the workflow ref until the caller has
adopted this layout (product Wave C / sync [#13](https://github.com/fairagro/m4.2_middleware_devinfra/issues/13)).

| Path (caller checkout)               | Sync from Devinfra? | Role                                                              |
| ------------------------------------ | ------------------- | ----------------------------------------------------------------- |
| `docker/Dockerfile.product-app.base` | **Yes**             | Shared stages: package-builder → binary-builder → export-binaries |
| `docker/Dockerfile.<component>`      | **No** (local)      | Thin last stage: USER / CMD / HEALTHCHECK / runtime apk / labels  |
| `docker-bake.hcl` (repo root)        | **No** (local)      | Bake targets: `<component>-base` + `<component>` with `contexts`  |

Example stubs (not used by Devinfra CST):
[`docker/examples/`](https://github.com/fairagro/m4.2_middleware_devinfra/tree/main/docker/examples/) (Devinfra-only —
not synced). ARG list is documented at the top of
[`docker/Dockerfile.product-app.base`](../docker/Dockerfile.product-app.base). Prefer `PYINSTALLER_IMPORT` (package
import path whose `main.py` is resolved after wheel install); do not pass a repo-relative entry path — PyInstaller entry
must come from the installed wheel, not from copying application source as the script path.

**Lockfile-deterministic binary-builder install
([#73](https://github.com/fairagro/m4.2_middleware_devinfra/issues/73)):** `binary-builder` copies `uv.lock` and
workspace metadata from `package-builder`, runs `uv sync --frozen --no-dev --no-install-workspace` so transitive deps
match the lock, then installs the built workspace wheels with `uv pip install --no-deps` (no live-index resolve of wheel
`Requires-Dist`). `pyinstaller` remains pinned via `PYINSTALLER_VERSION` from `versions.env`. Do **not** hand-edit this
synced base in products to “fix” install reproducibility.

**Version pins (one per component):** concrete numbers live only in repo-root [`versions.env`](../versions.env) (Dev
Container section + **Product app image** section for `PIP_VERSION`, `ALPINE_*`, `PYINSTALLER_VERSION`; shared
`PYTHON_VERSION` / `UV_VERSION`). Do **not** duplicate pins as Dockerfile `ARG` defaults or Bake HCL `variable` defaults
— inject via Bake `--set` / `reusable-build` (after `load-versions-env.sh`). The shared base `FROM` lines use
`${PYTHON_VERSION:?}` / `${ALPINE_MINOR:?}` so a forgotten build-arg fails the build loudly and BuildKit’s
`InvalidDefaultArgInFrom` check stays clean (products pick this up on the next Devinfra sync of
`docker/Dockerfile.product-app.base`).

**Structure expectation** for API, sql-to-arc, and harvester: same three-stage skeleton; product differences via base
ARGs (packages, binary name, optional compile apk extras) and local last-stage finishing. **Product-only** extras (e.g.
sql-to-arc Microsoft ODBC driver) stay in the **product-local last stage**, not in the synced base. Builder compile
extras that all products share may use `BUILDER_APK_PACKAGES`; runtime personality stays in the last stage.

Local smoke (in a product repo after adoption):

```bash
set -a && source versions.env && set +a
docker buildx bake api --load \
  --set "*.args.PYTHON_VERSION=${PYTHON_VERSION}" \
  --set "*.args.ALPINE_MINOR=${ALPINE_MINOR}" \
  --set "*.args.ALPINE_VERSION=${ALPINE_VERSION}" \
  --set "*.args.PIP_VERSION=${PIP_VERSION}" \
  --set "*.args.UV_VERSION=${UV_VERSION}" \
  --set "*.args.PYINSTALLER_VERSION=${PYINSTALLER_VERSION}"
```

`reusable-build` invokes `docker/bake-action` with `files: docker-bake.hcl` and `targets: <component>`, passing
toolchain `*.args` from `versions.env` / `load-versions-env.sh`. Artifact tags and the check contract are unchanged.

## Calling from a product repo

Replace `@main` with a **tag** or **commit SHA** once you want a frozen contract. `@main` is fine for early adoption
while this repo’s CI surface is still moving.

The reusable workflows check out the **caller** repository (not Devinfra), so `versions.env`, `.python-version`,
`scripts/load-versions-env.sh`, the **Bake product-app layout** (below), and Helm charts must exist in the product repo.
Callers that sync `versions.env` MUST also sync `scripts/load-versions-env.sh`.

**`components` is required** on `reusable-build.yml`, `reusable-check.yml`, and `reusable-release.yml`. There is no
shared default (do not omit and expect `["api"]`). A missing input fails at workflow validation. Pass a JSON array of
Bake / CST component names:

```yaml
components: '["api"]' # API
components: '["harvester"]' # Harvester
components: '["api", "worker"]' # multi-component (example)
```

`reusable-code-quality.yml` accepts `components` for caller compatibility but does not use it; it has no product-name
default and may be omitted there.

### Trivy: licenses vs vulnerabilities

- **Licences (report-only):** `reusable-check` **Licence Check** still runs Trivy `scanners: license` and uploads a JSON
  artifact, but **does not fail** the job on findings (Alpine base GPL / `restricted` is expected). When
  `reusable-release` creates a GitHub Release, it re-scans each component image and appends an **Image licenses
  (Trivy)** section (counts + package/license/classification table). License hits alone must not fail release.
- **Vulnerabilities (gate):** `reusable-check` **Security Check** keeps failing on CRITICAL/HIGH vulns (SARIF upload
  unchanged). Do not treat license policy as a reason to relax vuln gates.

Bump the product `uses:` ref after this policy lands so callers pick up report-only Licence Check.

### Feature PR (Docker build + check)

```yaml
jobs:
  code-quality:
    needs: [detect-changes]
    uses: fairagro/m4.2_middleware_devinfra/.github/workflows/reusable-code-quality.yml@main
    with:
      python_package_root: middleware
      components: '["api"]'
      skip: ${{ needs.detect-changes.outputs.code != 'true' }}
    secrets: inherit

  build:
    needs: [detect-changes]
    uses: fairagro/m4.2_middleware_devinfra/.github/workflows/reusable-build.yml@main
    with:
      components: '["api"]'
      image_base_name: fairagro-advanced-middleware
      skip: ${{ needs.detect-changes.outputs.code != 'true' }}
    secrets: inherit

  check:
    needs: [detect-changes, build]
    if: always() && needs.detect-changes.result == 'success'
    uses: fairagro/m4.2_middleware_devinfra/.github/workflows/reusable-check.yml@main
    with:
      version: ${{ needs.build.outputs.version }}
      components: '["api"]'
      image_base_name: fairagro-advanced-middleware
      skip: ${{ needs.detect-changes.outputs.code != 'true' || needs.build.result != 'success' }}
    secrets: inherit
```

### Release / pre-release (Docker)

```yaml
jobs:
  build:
    uses: fairagro/m4.2_middleware_devinfra/.github/workflows/reusable-build.yml@main
    with:
      version_bump: ${{ inputs.version_bump }}
      components: '["api"]'
      image_base_name: fairagro-advanced-middleware
    secrets: inherit

  check:
    needs: [build]
    uses: fairagro/m4.2_middleware_devinfra/.github/workflows/reusable-check.yml@main
    with:
      version: ${{ needs.build.outputs.version }}
      components: '["api"]'
      image_base_name: fairagro-advanced-middleware
    secrets: inherit

  release:
    needs: [build, check]
    uses: fairagro/m4.2_middleware_devinfra/.github/workflows/reusable-release.yml@main
    with:
      version: ${{ needs.build.outputs.version }}
      pep440_version: ${{ needs.build.outputs.pep440_version }}
      components: '["api"]'
      image_base_name: fairagro-advanced-middleware
      dockerhub_namespace: zalf
      ghcr_namespace: fairagro
      release_type: final # or feature
      tag_prefix: docker-v
      create_github_release: true
    secrets: inherit
```

Keep any **PyPI** publish steps in a product-local job or workflow after build (API only).

### Helm (thin `workflow_dispatch` caller)

```yaml
name: Helm Chart Release
on:
  workflow_dispatch:
    inputs:
      version_bump:
        type: choice
        options: [major, minor, patch]
        default: patch

jobs:
  helm:
    uses: fairagro/m4.2_middleware_devinfra/.github/workflows/reusable-helm-release.yml@main
    with:
      version_bump: ${{ inputs.version_bump }}
      chart_dir: helmchart/fairagro-advanced-middleware-api-chart
      chart_name: fairagro-advanced-middleware-api-chart
      dockerhub_namespace: zalf
      ghcr_namespace: fairagro
      require_main: true
    secrets: inherit
```

Pre-release:

```yaml
jobs:
  helm:
    uses: fairagro/m4.2_middleware_devinfra/.github/workflows/reusable-helm-pre-release.yml@main
    with:
      chart_dir: helmchart/fairagro-advanced-middleware-api-chart
      chart_name: fairagro-advanced-middleware-api-chart
      dockerhub_namespace: zalf
      ghcr_namespace: fairagro
    secrets: inherit
```

Order: publish a **Docker** release (so a `*-docker-v*` tag exists) before Helm final/pre-release. Helm sets chart
`appVersion` from the latest Docker tag.

**Helm ↔ `tag_prefix`:** Shared Helm reusables discover Docker tags with the fixed pattern `*-docker-v*` (semver /
optional `-rc.…` on pre-release). Callers MUST keep `reusable-release.yml` `tag_prefix` at the default `docker-v`. A
custom `tag_prefix` breaks Helm `appVersion` lookup unless you also change Helm (out of scope here).

## Inputs

### `reusable-code-quality.yml`

| Input                 | Default      | Purpose                                                                  |
| --------------------- | ------------ | ------------------------------------------------------------------------ |
| `python_package_root` | `middleware` | Path for ruff / pylint / mypy / bandit / pytest                          |
| `mypy_path`           | `""`         | Optional colon-separated `MYPYPATH` (stubs + src roots); empty = default |
| `pylint_source_roots` | `""`         | Optional comma-separated pylint `--source-roots`                         |
| `components`          | (optional)   | Accepted for caller compatibility; unused by this workflow               |
| `skip`                | `false`      | Successful no-op (keeps required check names green)                      |

**pytest vs pre-push:** this workflow runs `uv run pytest "${PKG}" …` **without** the synced pre-push marker filter
(`-m "not system_external and not system_local"`). CI stays the broader gate; local push excludes `system_*` by default
— see [Pre-push pytest scope](quality.md#pre-push-pytest-scope) in `docs/quality.md`.

**Markdown (Prettier / markdownlint):** when `skip` is false, the job requires root `package.json` + `package-lock.json`
(synced from Devinfra), installs Node from the caller’s `versions.env` (`NODE_VERSION`), runs `npm ci`, then
`npm run format:md:check` and `npm run lint:md` against the same shared configs as commit-stage hooks. Missing manifests
fail the job (no soft-skip).

Python version comes from the caller’s `versions.env` (`PYTHON_VERSION`) plus matching `.python-version` — there is no
version override input.

The job display name stays **`Code Quality Check (3.12)`** for existing branch rulesets.

### `reusable-check.yml`

| Input             | Default                        | Purpose                                                            |
| ----------------- | ------------------------------ | ------------------------------------------------------------------ |
| `version`         | `""`                           | Build version string (required when `skip` is false)               |
| `components`      | (required)                     | JSON array; matrix over components                                 |
| `image_base_name` | `fairagro-advanced-middleware` | Prefix for `local/<name>-<component>:<version>`                    |
| `skip`            | `false`                        | Successful no-op on all check jobs (keeps required statuses green) |

**Licence Check** is report-only (does not fail on Trivy license findings). **Security Check** still fails on
CRITICAL/HIGH vulnerabilities. See [Trivy: licenses vs vulnerabilities](#trivy-licenses-vs-vulnerabilities).

### `reusable-build.yml`

| Input             | Default                        | Purpose                                            |
| ----------------- | ------------------------------ | -------------------------------------------------- |
| `version_bump`    | `patch`                        | major / minor / patch against latest `*-docker-v*` |
| `components`      | (required)                     | JSON array; matrix build                           |
| `image_base_name` | `fairagro-advanced-middleware` | Local image tag prefix                             |
| `skip`            | `false`                        | Successful no-op without artifacts                 |

Outputs: `version`, `pep440_version`, `components`. Version scheme is shared across all three products
(`*-docker-vX.Y.Z`; on `feature/*` → `X.Y.Z-rc.<branch>.<run>`).

### `reusable-release.yml`

| Input                   | Default                        | Purpose                                                              |
| ----------------------- | ------------------------------ | -------------------------------------------------------------------- |
| `version`               | (required)                     | From build                                                           |
| `pep440_version`        | `""`                           | Caller compatibility; unused (no PyPI here)                          |
| `components`            | (required)                     | Matrix push                                                          |
| `image_base_name`       | `fairagro-advanced-middleware` | Must match build                                                     |
| `dockerhub_namespace`   | `zalf`                         | Docker Hub org/user                                                  |
| `ghcr_namespace`        | `""` → `repository_owner`      | GHCR namespace; empty uses owner                                     |
| `release_type`          | (required)                     | `feature` or `final` (prerelease flag)                               |
| `create_github_release` | `true`                         | When true: git tag + GitHub Release; when false: pushes only         |
| `tag_prefix`            | `docker-v`                     | Tag shape `{timestamp}-{prefix}{version}` (keep `docker-v` for Helm) |
| `skip`                  | `false`                        | Successful no-op                                                     |

Secrets: `DOCKERHUB_USER`, `DOCKERHUB_TOKEN` (optional — if missing, DockerHub push is skipped and the GitHub Release
body states why). GHCR uses `GITHUB_TOKEN` (`packages: write` on the reusable job). Git tags / GitHub Releases are
created even when a registry push fails; the release body includes a **Registry status** section and an **Image licenses
(Trivy)** section (informational). Re-pushing an existing release is a follow-up (retry workflow).

GHCR image tag shape: `ghcr.io/<ghcr_namespace>/<image_base_name>-<component>:<version>` (aligned with DockerHub
naming).

When `create_github_release` is false, no git tag or GitHub Release is created (image pushes still run).

### `reusable-helm-release.yml` / `reusable-helm-pre-release.yml`

| Input                   | Default                   | Purpose                                      |
| ----------------------- | ------------------------- | -------------------------------------------- |
| `chart_dir`             | (required)                | Chart path in caller checkout                |
| `chart_name`            | (required)                | Must match `name:` in Chart.yaml (validated) |
| `dockerhub_namespace`   | `zalf`                    | Docker Hub OCI namespace                     |
| `ghcr_namespace`        | `""` → `repository_owner` | GHCR OCI namespace; empty uses owner         |
| `version_bump`          | `patch`                   | Final release only                           |
| `require_main`          | `true`                    | Final release only                           |
| `create_github_release` | `true`                    | Final release only                           |
| `helm_install_name`     | `fairagro-middleware`     | Example name in release notes (final only)   |

Helm CLI version comes from the caller’s `versions.env` (`HELM_VERSION`). Secrets `DOCKERHUB_USER` / `DOCKERHUB_TOKEN`
are optional; if missing or a push fails, the Helm GitHub Release body (final) or job summary (pre-release) MUST state
the registry status and reason. GHCR uses `GITHUB_TOKEN`. Chart tags are created before registry pushes (same tag-first
policy as Docker release).

## Check artifact contract

A prior **build** job in the same workflow run must upload:

| Artifact name                        | Expected file inside              |
| ------------------------------------ | --------------------------------- |
| `docker-image-<component>-<version>` | `docker-image-<component>.tar.gz` |
| `sbom-<component>-<version>`         | `sbom-<component>.spdx.json`      |

The build must save the image into that archive **already tagged** as:

`local/<image_base_name>-<component>:<version>`

After `docker load`, the reusable checks reference that same tag (they do not retag).

Container structure tests load:

`docker/container-structure-tests/<component>.yaml` from the **caller** checkout.

## Permissions

Callers that upload SARIF need `security-events: write` on the top-level workflow (or inherit permissions that allow the
reusable security job). Prefer `secrets: inherit` when product secrets are required by nested steps. Docker/Helm pushes
need DockerHub secrets on the caller and `packages: write` for GHCR where applicable.
