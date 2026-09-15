#!/usr/bin/env bash
#
# Update Dockerfile pins that shared Renovate does not manage:
#   - Alpine apk pins: name=X.Y.Z-rN (from Alpine APKINDEX main + community)
#   - Inline pip-style pins in the Dockerfile: name==X.Y.Z (from PyPI)
#
# Does NOT edit versions.env / .python-version (Devinfra Renovate + sync SoT).
#
# Usage:
#   ./scripts/update-dockerfile-pins.sh
#   ./scripts/update-dockerfile-pins.sh path/to/Dockerfile
#
# With no argument, uses the single docker/Dockerfile.* in the repo (excluding
# docker/Dockerfile.product-app.base). Multiple product Dockerfiles → pass a path.
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

resolve_dockerfile() {
  if [[ $# -gt 0 ]]; then
    printf '%s' "$1"
    return 0
  fi

  local matches=()
  local f base
  shopt -s nullglob
  for f in "${PROJECT_DIR}"/docker/Dockerfile.*; do
    base="$(basename "$f")"
    [[ "$base" == "Dockerfile.product-app.base" ]] && continue
    matches+=("$f")
  done
  shopt -u nullglob

  if ((${#matches[@]} == 1)); then
    printf '%s' "${matches[0]}"
    return 0
  fi
  if ((${#matches[@]} == 0)); then
    echo "ERROR: no docker/Dockerfile.* found (excluding product-app.base); pass a path" >&2
    return 1
  fi
  echo "ERROR: multiple docker/Dockerfile.* candidates; pass a path:" >&2
  printf '  %s\n' "${matches[@]}" >&2
  return 1
}

if [[ $# -gt 0 ]]; then
  DOCKERFILE="$(resolve_dockerfile "$1")"
else
  DOCKERFILE="$(resolve_dockerfile)"
fi

if [[ ! -f "$DOCKERFILE" ]]; then
  echo "ERROR: Dockerfile not found: $DOCKERFILE" >&2
  exit 1
fi

# Alpine major.minor from FROM tags, then versions.env ALPINE_MINOR.
detect_alpine_minor() {
  local extracted
  extracted="$(
    grep -E '^FROM ' "$DOCKERFILE" | grep -oE 'alpine[0-9]+\.[0-9]+' | grep -oE '[0-9]+\.[0-9]+' | head -1 || true
  )"
  if [[ -z "$extracted" ]]; then
    extracted="$(
      grep -m1 -E '^FROM[[:space:]]+alpine:' "$DOCKERFILE" 2>/dev/null \
        | sed -E 's/.*alpine:([0-9]+\.[0-9]+).*/\1/' || true
    )"
    [[ "$extracted" =~ ^[0-9]+\.[0-9]+$ ]] || extracted=""
  fi
  if [[ -z "$extracted" && -f "${PROJECT_DIR}/versions.env" ]]; then
    extracted="$(
      set -a
      # shellcheck disable=SC1091
      source "${PROJECT_DIR}/versions.env"
      set +a
      printf '%s' "${ALPINE_MINOR:-}"
    )"
  fi
  printf '%s' "$extracted"
}

ALPINE_MINOR="$(detect_alpine_minor)"
if [[ ! "$ALPINE_MINOR" =~ ^[0-9]+\.[0-9]+$ ]]; then
  echo "ERROR: could not detect Alpine major.minor from $DOCKERFILE or versions.env ALPINE_MINOR" >&2
  exit 1
fi
echo "Alpine ${ALPINE_MINOR} (APKINDEX)"

pypi_latest() {
  local pkg="$1"
  local json
  json="$(curl -sf "https://pypi.org/pypi/${pkg}/json")" || return 1
  if command -v uv >/dev/null 2>&1; then
    printf '%s' "$json" | uv run --directory "$PROJECT_DIR" python -c \
      "import sys, json; print(json.load(sys.stdin)['info']['version'])"
  else
    printf '%s' "$json" | python3 -c \
      "import sys, json; print(json.load(sys.stdin)['info']['version'])"
  fi
}

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

declare -A PKG_VERSIONS

parse_apkindex() {
  local index_file="$1"
  local pkg=""
  local line

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
  done <"$index_file"
}

echo "Downloading Alpine APKINDEX (main + community)..."
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

echo "Updating apk pins in ${DOCKERFILE}..."
cp "$DOCKERFILE" "${DOCKERFILE}.bak"

# Match only Alpine-style pinned packages: name=X.Y.Z-rN
# Hyphen must be at the END of [a-z0-9_-] to be literal in POSIX ERE.
while IFS= read -r match; do
  [[ "$match" =~ ^([a-z0-9][a-z0-9_-]*)=([0-9][a-z0-9._]+-r[0-9]+)$ ]] || continue

  pkg="${BASH_REMATCH[1]}"
  current="${BASH_REMATCH[2]}"
  latest="$(latest_apk_version "$pkg" || true)"

  if [[ -z "$latest" ]]; then
    echo "  skip ${pkg}: not in APKINDEX"
    continue
  fi
  if [[ "$latest" == "$current" ]]; then
    echo "  ok   ${pkg}=${current}"
    continue
  fi
  echo "  bump ${pkg}: ${current} -> ${latest}"
  escaped_current="${current//./\\.}"
  sed -i "s#\(^\|[[:space:]]\)${pkg}=${escaped_current}\([[:space:]]\|$\)#\1${pkg}=${latest}\2#g" "$DOCKERFILE"
done < <(grep -oE '[a-z0-9][a-z0-9_-]*=[0-9][a-z0-9._]+-r[0-9]+' "$DOCKERFILE" || true)

echo "Updating inline pip pins (name==…) in ${DOCKERFILE}..."
while IFS= read -r match; do
  [[ "$match" =~ ^([a-zA-Z0-9][a-zA-Z0-9_-]*)==([0-9][a-z0-9._]*)$ ]] || continue

  pkg="${BASH_REMATCH[1]}"
  current="${BASH_REMATCH[2]}"
  latest="$(pypi_latest "$pkg" || true)"

  if [[ -z "$latest" ]]; then
    echo "  skip ${pkg}: PyPI lookup failed"
    continue
  fi
  if [[ "$latest" == "$current" ]]; then
    echo "  ok   ${pkg}==${current}"
    continue
  fi
  echo "  bump ${pkg}: ${current} -> ${latest}"
  sed -i "s|${pkg}==${current}|${pkg}==${latest}|g" "$DOCKERFILE"
done < <(grep -oE '[a-zA-Z0-9][a-zA-Z0-9_-]*==[0-9][a-z0-9._]*' "$DOCKERFILE" || true)

echo "Done. Backup: ${DOCKERFILE}.bak"
