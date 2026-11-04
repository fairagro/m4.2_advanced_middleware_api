#!/usr/bin/env bash
# Install pinned container-structure-test onto PATH (CI / host). Pin from versions.env CST_VERSION.
# Load versions.env directly — do not source load-versions-env.sh (that rewrites
# .python-version; CI may invoke this script with sudo and would leave .python-version root-owned).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

VERSIONS_ENV="${REPO_ROOT}/versions.env"
if [[ ! -f "${VERSIONS_ENV}" ]]; then
  echo "install-cst: versions.env not found: ${VERSIONS_ENV}" >&2
  exit 1
fi
set -a
# shellcheck source=/dev/null
source "${VERSIONS_ENV}"
set +a

PIN="${CST_VERSION:-}"
if [[ -z "${PIN}" ]]; then
  echo "install-cst: CST_VERSION missing from versions.env" >&2
  exit 1
fi

DEST="${CST_INSTALL_DIR:-/usr/local/bin}"
ASSET="container-structure-test-linux-amd64"
URL="https://github.com/GoogleContainerTools/container-structure-test/releases/download/${PIN}/${ASSET}"

curl -fsSL "${URL}" -o "${DEST}/container-structure-test"
chmod +x "${DEST}/container-structure-test"
ln -sfn "${DEST}/container-structure-test" "${DEST}/cst"
container-structure-test version
