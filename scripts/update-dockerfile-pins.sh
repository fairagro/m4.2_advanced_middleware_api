#!/usr/bin/env bash
#
# Update Dockerfile pins that shared Renovate does not manage:
#   - Alpine apk pins: name=X.Y.Z-rN (from Alpine APKINDEX main + community)
#   - Inline pip-style pins in the Dockerfile: name==X.Y.Z (from PyPI)
#
# Does NOT edit versions.env / .python-version (Devinfra Renovate + sync SoT).
# Does NOT write *.bak sidecars — use git to roll back.
#
# Usage:
#   ./scripts/update-dockerfile-pins.sh
#   ./scripts/update-dockerfile-pins.sh path/to/Dockerfile
#
# With no argument, updates every docker/Dockerfile.* except
# docker/Dockerfile.product-app.base. Pass a path to update a single file.
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

list_candidate_dockerfiles() {
  local f base
  shopt -s nullglob
  for f in "${PROJECT_DIR}"/docker/Dockerfile.*; do
    base="$(basename "$f")"
    [[ "$base" == "Dockerfile.product-app.base" ]] && continue
    printf '%s\n' "$f"
  done
  shopt -u nullglob
}

resolve_dockerfiles() {
  if [[ $# -gt 0 ]]; then
    printf '%s\n' "$1"
    return 0
  fi

  local matches=()
  mapfile -t matches < <(list_candidate_dockerfiles)
  if ((${#matches[@]} == 0)); then
    echo "ERROR: no docker/Dockerfile.* found (excluding product-app.base); pass a path" >&2
    return 1
  fi
  printf '%s\n' "${matches[@]}"
}

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

# Alpine major.minor from FROM tags, then versions.env ALPINE_MINOR.
detect_alpine_minor() {
  local dockerfile="$1"
  local extracted
  extracted="$(
    grep -E '^FROM ' "$dockerfile" | grep -oE 'alpine[0-9]+\.[0-9]+' | grep -oE '[0-9]+\.[0-9]+' | head -1 || true
  )"
  if [[ -z "$extracted" ]]; then
    extracted="$(
      grep -m1 -E '^FROM[[:space:]]+alpine:' "$dockerfile" 2>/dev/null \
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

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

declare -A PKG_VERSIONS=()
LOADED_ALPINE_MINOR=""

parse_apkindex() {
  local index_file="$1"
  local pkg="" line

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

ensure_apkindex() {
  local alpine_minor="$1"
  if [[ "$LOADED_ALPINE_MINOR" == "$alpine_minor" ]]; then
    return 0
  fi

  PKG_VERSIONS=()
  echo "Downloading Alpine ${alpine_minor} APKINDEX (main + community)..."
  local repo index_archive
  for repo in main community; do
    index_archive="${TMP_DIR}/${alpine_minor//./_}_${repo}.tar.gz"
    curl -sL "https://dl-cdn.alpinelinux.org/alpine/v${alpine_minor}/${repo}/x86_64/APKINDEX.tar.gz" \
      -o "$index_archive"
    tar -xzf "$index_archive" -C "$TMP_DIR"
    parse_apkindex "${TMP_DIR}/APKINDEX"
    rm -f "${TMP_DIR}/APKINDEX"
  done
  LOADED_ALPINE_MINOR="$alpine_minor"
}

latest_apk_version() {
  local pkg="$1"
  local versions="${PKG_VERSIONS[$pkg]:-}"
  [[ -n "$versions" ]] || return 1
  printf '%s\n' "$versions" | sed '/^$/d' | sort -V | tail -1
}

update_one_dockerfile() {
  local dockerfile="$1"

  if [[ ! -f "$dockerfile" ]]; then
    echo "ERROR: Dockerfile not found: $dockerfile" >&2
    return 1
  fi

  local alpine_minor
  alpine_minor="$(detect_alpine_minor "$dockerfile")"
  if [[ ! "$alpine_minor" =~ ^[0-9]+\.[0-9]+$ ]]; then
    echo "ERROR: could not detect Alpine major.minor from $dockerfile or versions.env ALPINE_MINOR" >&2
    return 1
  fi
  echo "=== ${dockerfile} (Alpine ${alpine_minor})"

  ensure_apkindex "$alpine_minor"

  echo "Updating apk pins..."
  # Match only Alpine-style pinned packages: name=X.Y.Z-rN
  # Hyphen must be at the END of [a-z0-9_-] to be literal in POSIX ERE.
  while IFS= read -r match; do
    [[ "$match" =~ ^([a-z0-9][a-z0-9_-]*)=([0-9][a-z0-9._]+-r[0-9]+)$ ]] || continue

    local pkg="${BASH_REMATCH[1]}"
    local current="${BASH_REMATCH[2]}"
    local latest
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
    local escaped_current="${current//./\\.}"
    sed -i "s#\(^\|[[:space:]]\)${pkg}=${escaped_current}\([[:space:]]\|$\)#\1${pkg}=${latest}\2#g" "$dockerfile"
  done < <(grep -oE '[a-z0-9][a-z0-9_-]*=[0-9][a-z0-9._]+-r[0-9]+' "$dockerfile" || true)

  echo "Updating inline pip pins (name==…)..."
  while IFS= read -r match; do
    [[ "$match" =~ ^([a-zA-Z0-9][a-zA-Z0-9_-]*)==([0-9][a-z0-9._]*)$ ]] || continue

    local pkg="${BASH_REMATCH[1]}"
    local current="${BASH_REMATCH[2]}"
    local latest
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
    sed -i "s|${pkg}==${current}|${pkg}==${latest}|g" "$dockerfile"
  done < <(grep -oE '[a-zA-Z0-9][a-zA-Z0-9_-]*==[0-9][a-z0-9._]*' "$dockerfile" || true)

  echo "Done: ${dockerfile} (no .bak; roll back with git if needed)"
}

LIST_FILE="${TMP_DIR}/dockerfiles.txt"
resolve_dockerfiles "$@" >"$LIST_FILE"
mapfile -t DOCKERFILES <"$LIST_FILE"
if ((${#DOCKERFILES[@]} == 0)); then
  echo "ERROR: no Dockerfiles to update" >&2
  exit 1
fi
for DOCKERFILE in "${DOCKERFILES[@]}"; do
  update_one_dockerfile "$DOCKERFILE"
done
