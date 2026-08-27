#!/usr/bin/env bash
# Update pinned versions in docker/Dockerfile.api and versions.env:
#   - Alpine apk package pins (from Alpine APKINDEX)
#   - pip / uv pins in versions.env (from PyPI)
#   - Dockerfile ${VAR:-fallback} defaults (kept aligned with versions.env)
#
# Usage:
#   ./scripts/update-docker-pins.sh
#   ./scripts/update-docker-pins.sh path/to/Dockerfile
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DOCKERFILE="${PROJECT_DIR}/docker/Dockerfile.api"
VERSIONS_ENV="${PROJECT_DIR}/versions.env"

# Allow an optional Dockerfile path override for other repository variants.
if [[ $# -gt 0 ]]; then
  DOCKERFILE="$1"
fi

if [[ ! -f "$DOCKERFILE" ]]; then
  echo "❌ Dockerfile not found: $DOCKERFILE" >&2
  exit 1
fi

# shellcheck source=load-versions-env.sh
source "${SCRIPT_DIR}/load-versions-env.sh"
echo "🏔️  Alpine ${ALPINE_VERSION} (minor ${ALPINE_MINOR} for APKINDEX, from versions.env)"

update_versions_env_pin() {
  local key="$1"
  local value="$2"
  if grep -qE "^${key}=" "${VERSIONS_ENV}"; then
    sed -i "s#^${key}=.*#${key}=${value}#" "${VERSIONS_ENV}"
  else
    echo "${key}=${value}" >> "${VERSIONS_ENV}"
  fi
}

# Sync Dockerfile ${NAME:-fallback} defaults to match versions.env (SoT).
# Quoting is pieced so bash never treats :- as its own parameter-expansion operator.
sync_dockerfile_arg_fallback() {
  local arg_name="$1"
  local fallback="$2"
  local pattern='\$\{'"${arg_name}"':-[^}]+\}'
  local replacement='${'"${arg_name}"':-'"${fallback}"'}'
  if grep -qE "${pattern}" "$DOCKERFILE"; then
    sed -i -E "s#${pattern}#${replacement}#g" "$DOCKERFILE"
    echo "✔ Dockerfile \${${arg_name}:-…} → ${fallback}"
  else
    echo "⚠️  No \${${arg_name}:-…} fallback found in Dockerfile"
  fi
}

sync_all_dockerfile_fallbacks() {
  echo "📌 Syncing Dockerfile :-fallbacks from versions.env..."
  sync_dockerfile_arg_fallback "PIP_VERSION" "${PIP_VERSION}"
  sync_dockerfile_arg_fallback "UV_VERSION" "${UV_VERSION}"
  # FROM python:${PYTHON_VERSION:-X.Y} uses major.minor only
  sync_dockerfile_arg_fallback "PYTHON_VERSION" "${PYTHON_VERSION%.*}"
  sync_dockerfile_arg_fallback "ALPINE_VERSION" "${ALPINE_VERSION}"
  sync_dockerfile_arg_fallback "ALPINE_MINOR" "${ALPINE_MINOR}"
}

TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

declare -A PKG_VERSIONS

parse_apkindex() {
  local index_file="$1"
  local pkg=""

  while IFS= read -r line; do
    case "$line" in
      P:*)
        pkg="${line#P:}"
        ;;
      V:*)
        if [[ -n "$pkg" ]]; then
          PKG_VERSIONS["$pkg"]+="${line#V:}"$'\n'
        fi
        ;;
      "")
        pkg=""
        ;;
    esac
  done < "$index_file"
}

echo "⬇️ Downloading Alpine package indices..."
for repo in main community; do
  index_archive="${TMP_DIR}/${repo}.tar.gz"
  curl -sL "https://dl-cdn.alpinelinux.org/alpine/v${ALPINE_MINOR}/${repo}/x86_64/APKINDEX.tar.gz" \
    -o "$index_archive"
  tar -xzf "$index_archive" -C "$TMP_DIR"
  parse_apkindex "${TMP_DIR}/APKINDEX"
  rm -f "${TMP_DIR}/APKINDEX"
done

latest_apk_version() {
  local pkg="$1"
  local versions="${PKG_VERSIONS[$pkg]:-}"

  [[ -n "$versions" ]] || return 1
  printf '%s\n' "$versions" | sed '/^$/d' | sort -V | tail -1
}

echo "🔍 Updating Alpine apk pins in Dockerfile..."

cp "$DOCKERFILE" "${DOCKERFILE}.bak"

# Match only Alpine-style pinned packages: name=X.Y.Z-rN
# NOTE: hyphen must be at the END of the character class [a-z0-9_-] to be literal
#       Writing \- inside [...] creates an unexpected range in POSIX ERE
while IFS= read -r match; do
  [[ "$match" =~ ^([a-z0-9][a-z0-9_-]*)=([0-9][a-z0-9._]+-r[0-9]+)$ ]] || continue

  pkg="${BASH_REMATCH[1]}"
  current="${BASH_REMATCH[2]}"
  latest="$(latest_apk_version "$pkg" || true)"

  if [[ -z "$latest" ]]; then
    echo "⚠️  $pkg not found in index"
    continue
  fi

  if [[ "$latest" == "$current" ]]; then
    echo "✔ $pkg already up-to-date ($current)"
    continue
  fi

  echo "⬆️  $pkg: $current → $latest"

  escaped_current="${current//./\\.}"
  sed -i "s#\(^\|[[:space:]]\)${pkg}=${escaped_current}\([[:space:]]\|$\)#\1${pkg}=${latest}\2#g" "$DOCKERFILE"

done < <(grep -oE '[a-z0-9][a-z0-9_-]*=[0-9][a-z0-9._]+-r[0-9]+' "$DOCKERFILE" || true)

# --- Update pip / uv in versions.env (PyPI), then mirror into Dockerfile :-fallbacks ---
echo "🐍 Updating pip/uv pins in versions.env..."

for pkg_key in pip:PIP_VERSION uv:UV_VERSION; do
  pkg="${pkg_key%%:*}"
  env_key="${pkg_key##*:}"
  current="${!env_key}"

  latest=$(curl -sf "https://pypi.org/pypi/${pkg}/json" | python3 -c "import sys,json; print(json.load(sys.stdin)['info']['version'])" 2>/dev/null || true)

  if [[ -z "$latest" ]]; then
    echo "⚠️  $pkg not found on PyPI"
    continue
  fi

  if [[ "$latest" == "$current" ]]; then
    echo "✔ $pkg already up-to-date ($current)"
    continue
  fi

  echo "⬆️  $pkg: $current → $latest (versions.env ${env_key})"
  update_versions_env_pin "${env_key}" "${latest}"
done

# Re-load pins after versions.env edits, sync .python-version + Dockerfile fallbacks
# shellcheck source=load-versions-env.sh
source "${SCRIPT_DIR}/load-versions-env.sh"
sync_all_dockerfile_fallbacks

echo "✅ Done. Backup at ${DOCKERFILE}.bak"
rm -rf "$TMP_DIR"
