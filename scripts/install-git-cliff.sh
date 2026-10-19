#!/usr/bin/env bash
# Install pinned git-cliff onto PATH (CI / host). Pin from versions.env GIT_CLIFF_VERSION.
# Load versions.env directly — do not source load-versions-env.sh (that rewrites
# .python-version; CI invokes this script with sudo and would leave .python-version root-owned).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

VERSIONS_ENV="${REPO_ROOT}/versions.env"
if [[ ! -f "${VERSIONS_ENV}" ]]; then
  echo "install-git-cliff: versions.env not found: ${VERSIONS_ENV}" >&2
  exit 1
fi
set -a
# shellcheck source=/dev/null
source "${VERSIONS_ENV}"
set +a

PIN="${GIT_CLIFF_VERSION:-}"
if [[ -z "${PIN}" ]]; then
  echo "install-git-cliff: GIT_CLIFF_VERSION missing from versions.env" >&2
  exit 1
fi

VER="${PIN#v}"
DEST="${GIT_CLIFF_INSTALL_DIR:-/usr/local/bin}"
TMP="$(mktemp -d)"
trap 'rm -rf "${TMP}"' EXIT

ASSET="git-cliff-${VER}-x86_64-unknown-linux-gnu.tar.gz"
BASE_URL="https://github.com/orhun/git-cliff/releases/download/${PIN}"
curl -fsSL "${BASE_URL}/${ASSET}" -o "${TMP}/${ASSET}"
curl -fsSL "${BASE_URL}/${ASSET}.sha512" -o "${TMP}/${ASSET}.sha512"
# Published release checksum (same channel as the tarball; catches corrupt/partial downloads).
(cd "${TMP}" && sha512sum -c "${ASSET}.sha512")
tar -xz -C "${TMP}" -f "${TMP}/${ASSET}"
install -m 0755 "${TMP}/git-cliff-${VER}/git-cliff" "${DEST}/git-cliff"
git-cliff --version
