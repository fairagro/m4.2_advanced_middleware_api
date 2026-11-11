#!/usr/bin/env bash
# Install pinned actionlint onto PATH (CI / host / Dev Container). Pin from versions.env ACTIONLINT_VERSION.
# Load versions.env directly — do not source load-versions-env.sh (that rewrites
# .python-version; CI may invoke this script with sudo and would leave .python-version root-owned).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

VERSIONS_ENV="${REPO_ROOT}/versions.env"
if [[ ! -f "${VERSIONS_ENV}" ]]; then
  echo "install-actionlint: versions.env not found: ${VERSIONS_ENV}" >&2
  exit 1
fi
set -a
# shellcheck source=/dev/null
source "${VERSIONS_ENV}"
set +a

PIN="${ACTIONLINT_VERSION:-}"
if [[ -z "${PIN}" ]]; then
  echo "install-actionlint: ACTIONLINT_VERSION missing from versions.env" >&2
  exit 1
fi

VER="${PIN#v}"
DEST="${ACTIONLINT_INSTALL_DIR:-/usr/local/bin}"
TMP="$(mktemp -d)"
trap 'rm -rf "${TMP}"' EXIT

ARCH="$(uname -m)"
case "${ARCH}" in
  x86_64 | amd64) ASSET_ARCH="amd64" ;;
  aarch64 | arm64) ASSET_ARCH="arm64" ;;
  *)
    echo "install-actionlint: unsupported arch: ${ARCH}" >&2
    exit 1
    ;;
esac

ASSET="actionlint_${VER}_linux_${ASSET_ARCH}.tar.gz"
BASE_URL="https://github.com/rhysd/actionlint/releases/download/${PIN}"
curl -fsSL "${BASE_URL}/${ASSET}" -o "${TMP}/${ASSET}"
tar -xz -C "${TMP}" -f "${TMP}/${ASSET}"
install -m 0755 "${TMP}/actionlint" "${DEST}/actionlint"
actionlint -version
