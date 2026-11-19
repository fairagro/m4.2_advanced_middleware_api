#!/usr/bin/env bash
# Install a pinned oasdiff binary for local / CI use (#651).
set -euo pipefail

OASDIFF_VERSION="${OASDIFF_VERSION:-1.39.0}"
INSTALL_DIR="${OASDIFF_INSTALL_DIR:-${HOME}/.local/bin}"

os="$(uname -s)"
arch="$(uname -m)"
case "${os}" in
  Linux) goos=linux ;;
  Darwin) goos=darwin ;;
  *)
    echo "error: unsupported OS ${os}" >&2
    exit 2
    ;;
esac
case "${arch}" in
  x86_64 | amd64) goarch=amd64 ;;
  aarch64 | arm64) goarch=arm64 ;;
  *)
    echo "error: unsupported arch ${arch}" >&2
    exit 2
    ;;
esac

# macOS release is a fat binary archive.
if [[ "${goos}" == "darwin" ]]; then
  asset="oasdiff_${OASDIFF_VERSION}_darwin_all.tar.gz"
else
  asset="oasdiff_${OASDIFF_VERSION}_${goos}_${goarch}.tar.gz"
fi

url="https://github.com/oasdiff/oasdiff/releases/download/v${OASDIFF_VERSION}/${asset}"
tmpdir="$(mktemp -d)"
cleanup() { rm -rf "${tmpdir}"; }
trap cleanup EXIT

echo "Downloading ${url}"
curl -fsSL -o "${tmpdir}/${asset}" "${url}"
tar -xzf "${tmpdir}/${asset}" -C "${tmpdir}"
mkdir -p "${INSTALL_DIR}"
install -m 0755 "${tmpdir}/oasdiff" "${INSTALL_DIR}/oasdiff"
echo "Installed oasdiff ${OASDIFF_VERSION} -> ${INSTALL_DIR}/oasdiff"
"${INSTALL_DIR}/oasdiff" --version || "${INSTALL_DIR}/oasdiff" version || true
