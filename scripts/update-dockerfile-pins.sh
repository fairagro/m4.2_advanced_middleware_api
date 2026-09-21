#!/usr/bin/env bash
#
# Update Dockerfile pins that shared Renovate does not manage:
#   - Alpine apk pins via ARG defaults (fleet style B):
#       ARG CA_CERTIFICATES_VERSION=20260611-r0
#       RUN apk add --no-cache "ca-certificates=${CA_CERTIFICATES_VERSION}"
#     ARG NAME maps to apk package by stripping _VERSION, lower-casing, '_' → '-'.
#   - Inline pip-style pins in the Dockerfile: name==X.Y.Z (from PyPI)
#
# Does NOT edit versions.env / .python-version (Devinfra Renovate + sync SoT).
# Does NOT write *.bak sidecars — use git to roll back.
# Does NOT support inline apk literals pkg=X.Y.Z-rN (style A) — those fail loud.
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

# ARG CA_CERTIFICATES_VERSION → ca-certificates
arg_name_to_apk_pkg() {
  local arg="$1"
  local base="${arg%_VERSION}"
  printf '%s' "$base" | tr '[:upper:]' '[:lower:]' | tr '_' '-'
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
  local failed=0

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

  # Style A leftover: inline apk version literals are not supported.
  local inline_apk
  inline_apk="$(grep -oE '[a-z0-9][a-z0-9_-]*=[0-9][a-z0-9._]+-r[0-9]+' "$dockerfile" || true)"
  if [[ -n "$inline_apk" ]]; then
    echo "ERROR: inline apk version literals are not supported (use ARG <PKG>_VERSION=… + \"pkg=\${…}\"):" >&2
    printf '%s\n' "$inline_apk" | sort -u | sed 's/^/  /' >&2
    failed=1
  fi

  ensure_apkindex "$alpine_minor"

  echo "Updating apk ARG pins (…_VERSION=*-rN)..."
  local arg_line arg_name current pkg latest escaped_current
  while IFS= read -r arg_line; do
    [[ "$arg_line" =~ ^ARG[[:space:]]+([A-Za-z_][A-Za-z0-9_]*)=([0-9][a-z0-9._]+-r[0-9]+)[[:space:]]*$ ]] || continue
    arg_name="${BASH_REMATCH[1]}"
    current="${BASH_REMATCH[2]}"
    [[ "$arg_name" == *_VERSION ]] || continue

    pkg="$(arg_name_to_apk_pkg "$arg_name")"
    latest="$(latest_apk_version "$pkg" || true)"

    if [[ -z "$latest" ]]; then
      echo "ERROR: ${arg_name} → apk '${pkg}' not in APKINDEX (Alpine ${alpine_minor})" >&2
      failed=1
      continue
    fi
    if [[ "$latest" == "$current" ]]; then
      echo "  ok   ${arg_name}=${current} (${pkg})"
      continue
    fi
    echo "  bump ${arg_name}: ${current} -> ${latest} (${pkg})"
    escaped_current="${current//./\\.}"
    sed -i -E "s|^(ARG[[:space:]]+${arg_name}=)${escaped_current}([[:space:]]*)$|\1${latest}\2|" "$dockerfile"
  done < <(grep -E '^ARG[[:space:]]+[A-Za-z_][A-Za-z0-9_]*=[0-9][a-z0-9._]+-r[0-9]+[[:space:]]*$' "$dockerfile" || true)

  echo "Updating inline pip pins (name==…)..."
  while IFS= read -r match; do
    [[ "$match" =~ ^([a-zA-Z0-9][a-zA-Z0-9_-]*)==([0-9][a-z0-9._]*)$ ]] || continue

    local pkg_pip="${BASH_REMATCH[1]}"
    local current_pip="${BASH_REMATCH[2]}"
    local latest_pip
    latest_pip="$(pypi_latest "$pkg_pip" || true)"

    if [[ -z "$latest_pip" ]]; then
      echo "  skip ${pkg_pip}: PyPI lookup failed"
      continue
    fi
    if [[ "$latest_pip" == "$current_pip" ]]; then
      echo "  ok   ${pkg_pip}==${current_pip}"
      continue
    fi
    echo "  bump ${pkg_pip}: ${current_pip} -> ${latest_pip}"
    sed -i "s|${pkg_pip}==${current_pip}|${pkg_pip}==${latest_pip}|g" "$dockerfile"
  done < <(grep -oE '[a-zA-Z0-9][a-zA-Z0-9_-]*==[0-9][a-z0-9._]*' "$dockerfile" || true)

  if [[ "$failed" -ne 0 ]]; then
    echo "ERROR: pin update failed for ${dockerfile}" >&2
    return 1
  fi
  echo "Done: ${dockerfile} (no .bak; roll back with git if needed)"
}

LIST_FILE="${TMP_DIR}/dockerfiles.txt"
resolve_dockerfiles "$@" >"$LIST_FILE"
mapfile -t DOCKERFILES <"$LIST_FILE"
if ((${#DOCKERFILES[@]} == 0)); then
  echo "ERROR: no Dockerfiles to update" >&2
  exit 1
fi
OVERALL=0
for DOCKERFILE in "${DOCKERFILES[@]}"; do
  if ! update_one_dockerfile "$DOCKERFILE"; then
    OVERALL=1
  fi
done
exit "$OVERALL"
