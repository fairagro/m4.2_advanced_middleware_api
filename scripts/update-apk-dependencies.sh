#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DOCKERFILE="${PROJECT_DIR}/docker/Dockerfile.api"
APK_INDEX_URL="https://dl-cdn.alpinelinux.org/alpine/v3.23/main/x86_64/APKINDEX.tar.gz"

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

  # Escape dots in version string (literal in versions, but special in sed regex)
  escaped_current="${current//./\\.}"
  sed -i "s|\(^\|[[:space:]]\)${pkg}=${escaped_current}\([[:space:]]\|$\)|\1${pkg}=${latest}\2|g" "$DOCKERFILE"

done < <(grep -oE '[a-z0-9][a-z0-9_-]*=[0-9][a-z0-9._]+-r[0-9]+' "$DOCKERFILE" || true)

# --- Update pip-installed Python packages (PEP 440: name==X.Y.Z) ---
echo "🐍 Updating pip-pinned packages..."

while IFS= read -r match; do
  [[ "$match" =~ ^([a-zA-Z0-9][a-zA-Z0-9_-]*)==([0-9][a-z0-9._]*)$ ]] || continue

  pkg="${BASH_REMATCH[1]}"
  current="${BASH_REMATCH[2]}"

  latest=$(curl -sf "https://pypi.org/pypi/${pkg}/json" | python3 -c "import sys,json; print(json.load(sys.stdin)['info']['version'])" 2>/dev/null || true)

  if [[ -z "$latest" ]]; then
    echo "⚠️  $pkg not found on PyPI"
    continue
  fi

  if [[ "$latest" == "$current" ]]; then
    echo "✔ $pkg already up-to-date ($current)"
    continue
  fi

  echo "⬆️  $pkg: $current → $latest"

  escaped_current="${current//./\\.}"
  sed -i "s|\(^\|[[:space:]]\)${pkg}==${escaped_current}\([[:space:]]\|$\)|\1${pkg}==${latest}\2|g" "$DOCKERFILE"

done < <(grep -oE '[a-zA-Z0-9][a-zA-Z0-9_-]*==[0-9][a-z0-9._]*' "$DOCKERFILE" || true)

echo "✅ Done. Backup at ${DOCKERFILE}.bak"
rm -rf "$TMP_DIR"
