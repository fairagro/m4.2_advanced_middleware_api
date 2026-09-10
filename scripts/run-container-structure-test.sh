#!/usr/bin/env bash
# Build a Docker image via Bake and run container-structure-test.
# Product repos override paths/tag via env (or positional args).
#
# Environment: host or Dev Container (needs Docker + container-structure-test on PATH).
#
# Usage (Bake base + last stage — issue #36; Bake-only, no monolith docker build):
#   CST_BAKE_TARGET=api CST_IMAGE_TAG=myapp:test \
#     CST_CONFIG=docker/container-structure-tests/api.yaml \
#     ./scripts/run-container-structure-test.sh
#   Optional: CST_BAKE_FILE=docker-bake.hcl (default)
#
# Positional (optional, override env):
#   $1 Bake target
#   $2 image tag
#   $3 config file or directory of *.yaml tests

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

# Optional pins for Bake *.args only. Do not use load-versions-env.sh
# (that enforces unrelated pins and rewrites .python-version).
VERSIONS_ENV="${REPO_ROOT}/versions.env"
if [[ -f "${VERSIONS_ENV}" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "${VERSIONS_ENV}"
  set +a
fi

CST_BAKE_TARGET="${1:-${CST_BAKE_TARGET:-}}"
CST_IMAGE_TAG="${2:-${CST_IMAGE_TAG:-app:structure-test}}"
CST_CONFIG="${3:-${CST_CONFIG:-docker/container-structure-tests}}"
CST_BAKE_FILE="${CST_BAKE_FILE:-docker-bake.hcl}"

soft_skip_no_product_cst() {
  # Soft-skip shared Devinfra (and similar): no product CST suite.
  # Devinfra may still ship docker/Dockerfile.product-app.base + examples without
  # docker/container-structure-tests/.
  if [[ ! -e "${REPO_ROOT}/docker" ]] \
    || [[ ! -d "${REPO_ROOT}/docker/container-structure-tests" ]]; then
    echo "WARNING: skipping container-structure-test ($1)." >&2
    exit 0
  fi
}

if [[ -z "${CST_BAKE_TARGET}" ]]; then
  soft_skip_no_product_cst "CST_BAKE_TARGET unset; no product CST layout under docker/"
  echo "ERROR: CST_BAKE_TARGET is required (Bake-only; no monolith docker build)." >&2
  echo "Set CST_BAKE_TARGET or pass the Bake target as \$1." >&2
  exit 1
fi

if [[ ! -f "${CST_BAKE_FILE}" ]]; then
  soft_skip_no_product_cst "no ${CST_BAKE_FILE} for CST_BAKE_TARGET=${CST_BAKE_TARGET}"
  echo "ERROR: Bake file not found: ${CST_BAKE_FILE}" >&2
  echo "Set CST_BAKE_FILE or create repo-root docker-bake.hcl." >&2
  exit 1
fi

bake_set_args=()
# Pass through common pins when present in versions.env (products may use more).
for var in PYTHON_VERSION UV_VERSION ALPINE_VERSION ALPINE_MINOR PIP_VERSION PYINSTALLER_VERSION; do
  if [[ -n "${!var:-}" ]]; then
    bake_set_args+=(--set "*.args.${var}=${!var}")
  fi
done

echo "Building Docker image via Bake (${CST_BAKE_FILE} target=${CST_BAKE_TARGET} → ${CST_IMAGE_TAG})..."
docker buildx bake -f "${CST_BAKE_FILE}" "${CST_BAKE_TARGET}" --load \
  --set "${CST_BAKE_TARGET}.tags=${CST_IMAGE_TAG}" \
  "${bake_set_args[@]}"

configs=()
if [[ -d "${CST_CONFIG}" ]]; then
  shopt -s nullglob
  configs=("${CST_CONFIG}"/*.yaml "${CST_CONFIG}"/*.yml)
  shopt -u nullglob
  if [[ ${#configs[@]} -eq 0 ]]; then
    echo "ERROR: no *.yaml / *.yml under ${CST_CONFIG}" >&2
    exit 1
  fi
elif [[ -f "${CST_CONFIG}" ]]; then
  configs=("${CST_CONFIG}")
else
  echo "ERROR: CST config not found: ${CST_CONFIG}" >&2
  echo "Set CST_CONFIG or pass path as \$3." >&2
  exit 1
fi

echo "Running Container Structure Test (${#configs[@]} config(s))..."
for cfg in "${configs[@]}"; do
  container-structure-test test --image "${CST_IMAGE_TAG}" --config "${cfg}"
done
