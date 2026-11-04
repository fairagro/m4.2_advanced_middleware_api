#!/usr/bin/env bash
#
# Update Dockerfile pins that shared Renovate does not manage:
#   - Alpine apk pins via ARG defaults (fleet style B):
#       ARG CA_CERTIFICATES_VERSION=20260611-r0
#       RUN apk add --no-cache "ca-certificates=${CA_CERTIFICATES_VERSION}"
#     Resolve apk package name (in order):
#       1) ARG → strip _VERSION, lower-case, '_' → '-' (e.g. CA_CERTIFICATES → ca-certificates)
#       2) If that name is missing from APKINDEX: first "pkg=${ARG}" / pkg=${ARG} usage in the Dockerfile
#       3) Else optional override map (e.g. LIBSTDCXX_VERSION → libstdc++ when '+' cannot be in an ARG name)
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

# When the ARG→pkg transform cannot spell the real apk name (e.g. '+').
declare -A APK_PKG_OVERRIDES=(
  [LIBSTDCXX_VERSION]="libstdc++"
)

# First apk package referenced as "pkg=${ARG}" or pkg=${ARG} in the Dockerfile.
apk_pkg_from_usage() {
  local dockerfile="$1" arg="$2"
  local hit
  hit="$(grep -oE "\"[^\"]+=\\$\\{${arg}\\}\"" "$dockerfile" 2>/dev/null | head -1 || true)"
  if [[ -n "$hit" ]]; then
    hit="${hit#\"}"
    hit="${hit%\"}"
    printf '%s' "${hit%%=*}"
    return 0
  fi
  hit="$(grep -oE "[a-zA-Z0-9_+:.-]+=\\$\\{${arg}\\}" "$dockerfile" 2>/dev/null | head -1 || true)"
  if [[ -n "$hit" ]]; then
    printf '%s' "${hit%%=*}"
    return 0
  fi
  return 1
}

# Prefer derived name when present in APKINDEX; else Dockerfile usage; else override map.
resolve_apk_pkg() {
  local dockerfile="$1" arg_name="$2"
  local derived usage override

  derived="$(arg_name_to_apk_pkg "$arg_name")"
  if latest_apk_version "$derived" >/dev/null 2>&1; then
    printf '%s' "$derived"
    return 0
  fi

  usage="$(apk_pkg_from_usage "$dockerfile" "$arg_name" || true)"
  if [[ -n "$usage" ]] && latest_apk_version "$usage" >/dev/null 2>&1; then
    printf '%s' "$usage"
    return 0
  fi

  override="${APK_PKG_OVERRIDES[$arg_name]:-}"
  if [[ -n "$override" ]] && latest_apk_version "$override" >/dev/null 2>&1; then
    printf '%s' "$override"
    return 0
  fi

  if [[ -n "$usage" ]]; then
    printf '%s' "$usage"
  elif [[ -n "$override" ]]; then
    printf '%s' "$override"
  else
    printf '%s' "$derived"
  fi
  return 1
}

declare -A PKG_VERSIONS=()
LOADED_ALPINE_MINOR=""
TMP_DIR=""

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

    if ! pkg="$(resolve_apk_pkg "$dockerfile" "$arg_name")"; then
      echo "ERROR: ${arg_name} → apk '${pkg}' not in APKINDEX (Alpine ${alpine_minor})" >&2
      failed=1
      continue
    fi
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

main() {
  TMP_DIR="$(mktemp -d)"
  trap 'rm -rf "$TMP_DIR"' EXIT

  local list_file="${TMP_DIR}/dockerfiles.txt"
  resolve_dockerfiles "$@" >"$list_file"
  local dockerfiles=()
  mapfile -t dockerfiles <"$list_file"
  if ((${#dockerfiles[@]} == 0)); then
    echo "ERROR: no Dockerfiles to update" >&2
    exit 1
  fi
  local overall=0 dockerfile
  for dockerfile in "${dockerfiles[@]}"; do
    if ! update_one_dockerfile "$dockerfile"; then
      overall=1
    fi
  done
  exit "$overall"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
