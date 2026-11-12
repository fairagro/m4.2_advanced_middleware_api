#!/usr/bin/env bash
# Install a versions.env-pinned GitHub-release CLI onto PATH (CI / host / Dev Container).
# Usage: bash scripts/install-pinned-tool.sh <gitleaks|actionlint|kubeconform|cst|git-cliff>
# Load versions.env directly — do not source load-versions-env.sh (that rewrites
# .python-version; CI may invoke this script with sudo and would leave .python-version root-owned).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TOOL="${1:-}"

if [[ -z "${TOOL}" ]]; then
  echo "install-pinned-tool: usage: $0 <gitleaks|actionlint|kubeconform|cst|git-cliff>" >&2
  exit 1
fi

VERSIONS_ENV="${REPO_ROOT}/versions.env"
if [[ ! -f "${VERSIONS_ENV}" ]]; then
  echo "install-pinned-tool: versions.env not found: ${VERSIONS_ENV}" >&2
  exit 1
fi
set -a
# shellcheck source=/dev/null
source "${VERSIONS_ENV}"
set +a

uname_arch="$(uname -m)"
map_arch() {
  # $1 = amd64|arm64|x64 style for this tool
  case "${uname_arch}" in
    x86_64 | amd64) echo "$1" ;;
    aarch64 | arm64) echo "${2:-arm64}" ;;
    *)
      echo "install-pinned-tool: unsupported arch: ${uname_arch}" >&2
      return 1
      ;;
  esac
}

case "${TOOL}" in
  gitleaks)
    PIN="${GITLEAKS_VERSION:-}"
    PIN_NAME="GITLEAKS_VERSION"
    DEST="${GITLEAKS_INSTALL_DIR:-${PINNED_TOOL_INSTALL_DIR:-/usr/local/bin}}"
    ;;
  actionlint)
    PIN="${ACTIONLINT_VERSION:-}"
    PIN_NAME="ACTIONLINT_VERSION"
    DEST="${ACTIONLINT_INSTALL_DIR:-${PINNED_TOOL_INSTALL_DIR:-/usr/local/bin}}"
    ;;
  kubeconform)
    PIN="${KUBECONFORM_VERSION:-}"
    PIN_NAME="KUBECONFORM_VERSION"
    DEST="${KUBECONFORM_INSTALL_DIR:-${PINNED_TOOL_INSTALL_DIR:-/usr/local/bin}}"
    ;;
  cst)
    PIN="${CST_VERSION:-}"
    PIN_NAME="CST_VERSION"
    DEST="${CST_INSTALL_DIR:-${PINNED_TOOL_INSTALL_DIR:-/usr/local/bin}}"
    ;;
  git-cliff)
    PIN="${GIT_CLIFF_VERSION:-}"
    PIN_NAME="GIT_CLIFF_VERSION"
    DEST="${GIT_CLIFF_INSTALL_DIR:-${PINNED_TOOL_INSTALL_DIR:-/usr/local/bin}}"
    ;;
  *)
    echo "install-pinned-tool: unsupported tool id: ${TOOL}" >&2
    echo "install-pinned-tool: supported: gitleaks actionlint kubeconform cst git-cliff" >&2
    exit 1
    ;;
esac

if [[ -z "${PIN}" ]]; then
  echo "install-pinned-tool: ${PIN_NAME} missing from versions.env" >&2
  exit 1
fi

VER="${PIN#v}"
mkdir -p "${DEST}"

case "${TOOL}" in
  gitleaks)
    ASSET_ARCH="$(map_arch x64 arm64)"
    ASSET="gitleaks_${VER}_linux_${ASSET_ARCH}.tar.gz"
    BASE_URL="https://github.com/gitleaks/gitleaks/releases/download/${PIN}"
    TMP="$(mktemp -d)"
    trap 'rm -rf "${TMP}"' EXIT
    curl -fsSL "${BASE_URL}/${ASSET}" -o "${TMP}/${ASSET}"
    tar -xz -C "${TMP}" -f "${TMP}/${ASSET}"
    install -m 0755 "${TMP}/gitleaks" "${DEST}/gitleaks"
    "${DEST}/gitleaks" version
    ;;
  actionlint)
    ASSET_ARCH="$(map_arch amd64 arm64)"
    ASSET="actionlint_${VER}_linux_${ASSET_ARCH}.tar.gz"
    BASE_URL="https://github.com/rhysd/actionlint/releases/download/${PIN}"
    TMP="$(mktemp -d)"
    trap 'rm -rf "${TMP}"' EXIT
    curl -fsSL "${BASE_URL}/${ASSET}" -o "${TMP}/${ASSET}"
    tar -xz -C "${TMP}" -f "${TMP}/${ASSET}"
    install -m 0755 "${TMP}/actionlint" "${DEST}/actionlint"
    "${DEST}/actionlint" -version
    ;;
  kubeconform)
    ASSET_ARCH="$(map_arch amd64 arm64)"
    ASSET="kubeconform-linux-${ASSET_ARCH}.tar.gz"
    BASE_URL="https://github.com/yannh/kubeconform/releases/download/${PIN}"
    TMP="$(mktemp -d)"
    trap 'rm -rf "${TMP}"' EXIT
    curl -fsSL "${BASE_URL}/${ASSET}" -o "${TMP}/${ASSET}"
    tar -xz -C "${TMP}" -f "${TMP}/${ASSET}"
    install -m 0755 "${TMP}/kubeconform" "${DEST}/kubeconform"
    "${DEST}/kubeconform" -v
    ;;
  cst)
    # Official release asset is linux-amd64 only (matches prior install-cst.sh).
    ASSET="container-structure-test-linux-amd64"
    URL="https://github.com/GoogleContainerTools/container-structure-test/releases/download/${PIN}/${ASSET}"
    curl -fsSL "${URL}" -o "${DEST}/container-structure-test"
    chmod +x "${DEST}/container-structure-test"
    ln -sfn "${DEST}/container-structure-test" "${DEST}/cst"
    "${DEST}/container-structure-test" version
    ;;
  git-cliff)
    # Prior script pinned the x86_64 GNU tarball (CI/Dev Container linux/amd64).
    ASSET="git-cliff-${VER}-x86_64-unknown-linux-gnu.tar.gz"
    BASE_URL="https://github.com/orhun/git-cliff/releases/download/${PIN}"
    TMP="$(mktemp -d)"
    trap 'rm -rf "${TMP}"' EXIT
    curl -fsSL "${BASE_URL}/${ASSET}" -o "${TMP}/${ASSET}"
    curl -fsSL "${BASE_URL}/${ASSET}.sha512" -o "${TMP}/${ASSET}.sha512"
    (cd "${TMP}" && sha512sum -c "${ASSET}.sha512")
    tar -xz -C "${TMP}" -f "${TMP}/${ASSET}"
    install -m 0755 "${TMP}/git-cliff-${VER}/git-cliff" "${DEST}/git-cliff"
    "${DEST}/git-cliff" --version
    ;;
esac
