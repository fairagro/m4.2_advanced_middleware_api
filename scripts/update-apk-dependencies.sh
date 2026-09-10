#!/usr/bin/env bash
# Update Alpine apk pins in docker/Dockerfile.api (product helper until Devinfra #68).
# Alpine minor for APKINDEX comes from versions.env (SoT) — not the Dockerfile FROM line.
# Dockerfile.api uses alpine${ALPINE_MINOR:-…} / alpine:${ALPINE_VERSION:-…}, which the old
# literal `alpine3.xx` grep cannot parse.
#
# Usage:
#   ./scripts/update-apk-dependencies.sh
#   ./scripts/update-apk-dependencies.sh path/to/Dockerfile
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DOCKERFILE="${PROJECT_DIR}/docker/Dockerfile.api"

# Allow an optional Dockerfile path override for other repository variants.
if [[ $# -gt 0 ]]; then
  DOCKERFILE="$1"
fi

if [[ ! -f "$DOCKERFILE" ]]; then
  echo "❌ Dockerfile not found: $DOCKERFILE" >&2
  exit 1
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "❌ uv not found on PATH (required to query PyPI)." >&2
  exit 1
fi

# shellcheck source=load-versions-env.sh
source "${SCRIPT_DIR}/load-versions-env.sh"
if [[ -z "${ALPINE_MINOR:-}" ]]; then
  echo "❌ ALPINE_MINOR unset after loading versions.env" >&2
  exit 1
fi
echo "🏔️  Alpine minor ${ALPINE_MINOR} (APKINDEX from versions.env)"

APK_INDEX_URL="https://dl-cdn.alpinelinux.org/alpine/v${ALPINE_MINOR}/main/x86_64/APKINDEX.tar.gz"

TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

echo "⬇️ Downloading Alpine index..."
curl -sL "$APK_INDEX_URL" -o "$TMP_DIR/APKINDEX.tar.gz"

tar -xzf "$TMP_DIR/APKINDEX.tar.gz" -C "$TMP_DIR"

INDEX_FILE="$TMP_DIR/APKINDEX"

declare -A PKG_MAP

echo "📦 Parsing APKINDEX..."
pkg=""

while IFS= read -r line; do
  case "$line" in
    P:*)
      pkg="${line#P:}"
      ;;
    V:*)
      [[ -n "$pkg" ]] && PKG_MAP["$pkg"]="${line#V:}"
      ;;
    "")
      pkg=""
      ;;
  esac
done < "$INDEX_FILE"

echo "🔍 Updating Dockerfile..."

cp "$DOCKERFILE" "${DOCKERFILE}.bak"

# Match only Alpine-style pinned packages: name=X.Y.Z-rN
# NOTE: hyphen must be at the END of the character class [a-z0-9_-] to be literal
#       Writing \- inside [...] creates an unexpected range in POSIX ERE
while IFS= read -r match; do
  [[ "$match" =~ ^([a-z0-9][a-z0-9_-]*)=([0-9][a-z0-9._]+-r[0-9]+)$ ]] || continue

  pkg="${BASH_REMATCH[1]}"
  current="${BASH_REMATCH[2]}"
  latest="${PKG_MAP[$pkg]:-}"

  if [[ -z "$latest" ]]; then
    echo "⚠️  $pkg not found in index"
    continue
  fi

  if [[ "$latest" == "$current" ]]; then
    echo "✔ $pkg already up-to-date ($current)"
    continue
  fi

  echo "⬆️  $pkg: $current → $latest"

  # Replace exact Alpine package version pins in the Dockerfile.
  sed -i "s|${pkg}=${current}|${pkg}=${latest}|g" "$DOCKERFILE"

done < <(grep -oE '[a-z0-9][a-z0-9_-]*=[0-9][a-z0-9._]+-r[0-9]+' "$DOCKERFILE" || true)

# --- Update pip-installed Python packages (PEP 440: name==X.Y.Z) ---
echo "🐍 Updating pip-pinned packages..."

pypi_latest() {
  local pkg="$1"
  local json
  if ! json="$(curl -sf "https://pypi.org/pypi/${pkg}/json")"; then
    return 1
  fi
  # Spec: uv only — do not call bare python3/python.
  printf '%s' "$json" | uv run --directory "$PROJECT_DIR" python -c \
    "import sys, json; print(json.load(sys.stdin)['info']['version'])"
}

while IFS= read -r match; do
  [[ "$match" =~ ^([a-zA-Z0-9][a-zA-Z0-9_-]*)==([0-9][a-z0-9._]*)$ ]] || continue

  pkg="${BASH_REMATCH[1]}"
  current="${BASH_REMATCH[2]}"

  if ! latest="$(pypi_latest "$pkg")"; then
    echo "⚠️  $pkg: failed to fetch or parse PyPI metadata"
    continue
  fi
  if [[ -z "$latest" ]]; then
    echo "⚠️  $pkg: empty version from PyPI response"
    continue
  fi

  if [[ "$latest" == "$current" ]]; then
    echo "✔ $pkg already up-to-date ($current)"
    continue
  fi

  echo "⬆️  $pkg: $current → $latest"

  # Replace exact pip package version pins in the Dockerfile.
  sed -i "s|${pkg}==${current}|${pkg}==${latest}|g" "$DOCKERFILE"

done < <(grep -oE '[a-zA-Z0-9][a-zA-Z0-9_-]*==[0-9][a-z0-9._]*' "$DOCKERFILE" || true)

echo "✅ Done. Backup at ${DOCKERFILE}.bak"
