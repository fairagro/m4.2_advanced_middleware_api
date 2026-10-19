#!/usr/bin/env bash
# Resolve next base semver (X.Y.Z) for Docker or Helm release tags.
# Surfaces use fleet tags N-docker-vX.Y.Z / N-chart-vX.Y.Z (R1).
# version_bump=auto uses git-cliff Conventional Commits classification (F1 fail closed).
#
# Usage:
#   scripts/detect-version-bump.sh --surface docker|helm [--bump auto|major|minor|patch]
# Env: GIT_CLIFF_CONFIG (default: repo-root cliff.toml)
#
# Prints X.Y.Z on stdout. Logs on stderr.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

SURFACE=""
BUMP="auto"

usage() {
  echo "Usage: $0 --surface docker|helm [--bump auto|major|minor|patch]" >&2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --surface)
      SURFACE="${2:-}"
      shift 2
      ;;
    --bump)
      BUMP="${2:-}"
      shift 2
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    *)
      echo "detect-version-bump: unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ "${SURFACE}" != "docker" && "${SURFACE}" != "helm" ]]; then
  echo "detect-version-bump: --surface must be docker or helm" >&2
  exit 1
fi

case "${BUMP}" in
  auto | major | minor | patch) ;;
  *)
    echo "detect-version-bump: --bump must be auto|major|minor|patch (got '${BUMP}')" >&2
    exit 1
    ;;
esac

if [[ "${SURFACE}" == "docker" ]]; then
  TAG_GLOB='*-docker-v*'
  TAG_GREP='^[0-9]+-docker-v[0-9]+\.[0-9]+\.[0-9]+$'
  TAG_STRIP='s/^[0-9]*-docker-v//'
else
  TAG_GLOB='*-chart-v*'
  TAG_GREP='^[0-9]+-chart-v[0-9]+\.[0-9]+\.[0-9]+$'
  TAG_STRIP='s/^[0-9]*-chart-v//'
fi

LATEST_FULL="$(git tag --list "${TAG_GLOB}" | grep -E "${TAG_GREP}" | sort -V | tail -1 || true)"
if [[ -z "${LATEST_FULL}" ]]; then
  LATEST_VERSION="0.0.0"
  RANGE_FROM=""
else
  LATEST_VERSION="$(echo "${LATEST_FULL}" | sed "${TAG_STRIP}")"
  RANGE_FROM="${LATEST_FULL}"
fi

MAJOR="$(echo "${LATEST_VERSION}" | cut -d. -f1)"
MINOR="$(echo "${LATEST_VERSION}" | cut -d. -f2)"
PATCH="$(echo "${LATEST_VERSION}" | cut -d. -f3)"

bump_manual() {
  case "$1" in
    major)
      MAJOR=$((MAJOR + 1))
      MINOR=0
      PATCH=0
      ;;
    minor)
      MINOR=$((MINOR + 1))
      PATCH=0
      ;;
    patch)
      PATCH=$((PATCH + 1))
      ;;
  esac
  echo "${MAJOR}.${MINOR}.${PATCH}"
}

if [[ "${BUMP}" != "auto" ]]; then
  bump_manual "${BUMP}"
  exit 0
fi

if ! command -v git-cliff >/dev/null 2>&1; then
  echo "detect-version-bump: git-cliff not on PATH (pin GIT_CLIFF_VERSION; use Dev Container or install in CI)" >&2
  exit 1
fi
if ! command -v jq >/dev/null 2>&1; then
  echo "detect-version-bump: jq is required for auto bump" >&2
  exit 1
fi

CLIFF_CONFIG="${GIT_CLIFF_CONFIG:-${REPO_ROOT}/cliff.toml}"
if [[ ! -f "${CLIFF_CONFIG}" ]]; then
  echo "detect-version-bump: cliff config not found: ${CLIFF_CONFIG}" >&2
  exit 1
fi

if [[ -n "${RANGE_FROM}" ]]; then
  RANGE_ARGS=("${RANGE_FROM}..HEAD")
else
  RANGE_ARGS=()
fi

# Fleet tags are not plain semver; use cliff only to classify Conventional Commits.
# Do not pass --unreleased: without a surface tag_pattern, cliff treats every tag as a
# release boundary, so --unreleased + .[0] would only see commits after the newest tag of
# *any* surface (R1 Docker/Helm tags interleave) and silently under-bump. Classify the full
# RANGE_FROM..HEAD by aggregating commits across all cliff segments.
CLIFF_ERR="$(mktemp)"
set +e
CTX="$(git cliff "${RANGE_ARGS[@]}" --context --config "${CLIFF_CONFIG}" 2>"${CLIFF_ERR}")"
CLIFF_EC=$?
set -e
if [[ "${CLIFF_EC}" -ne 0 ]]; then
  echo "detect-version-bump: auto failed — git-cliff exited ${CLIFF_EC} (surface=${SURFACE}, since=${LATEST_FULL:-<root>})" >&2
  cat "${CLIFF_ERR}" >&2 || true
  rm -f "${CLIFF_ERR}"
  exit 1
fi
rm -f "${CLIFF_ERR}"
if [[ -z "${CTX}" || "${CTX}" == "[]" ]]; then
  echo "detect-version-bump: auto failed — no commit context since '${LATEST_FULL:-<none>}' (surface=${SURFACE})" >&2
  exit 1
fi

# shellcheck disable=SC2016
CLASS="$(echo "${CTX}" | jq -r '
  [.[].commits[]] as $c
  | if ($c | length) == 0 then "empty"
    elif ($c | map(select(.breaking == true)) | length) > 0 then "major"
    elif ($c | map(select(.group != null and (.group | test("Features")))) | length) > 0 then "minor"
    else "patch"
    end
')"

case "${CLASS}" in
  empty)
    echo "detect-version-bump: auto failed — no commits since '${LATEST_FULL:-<none>}' (surface=${SURFACE}); use explicit version_bump or commit changes" >&2
    exit 1
    ;;
  major | minor | patch)
    echo "detect-version-bump: auto → ${CLASS} (from ${LATEST_VERSION}, surface=${SURFACE}, since=${LATEST_FULL:-<root>})" >&2
    bump_manual "${CLASS}"
    ;;
  *)
    echo "detect-version-bump: auto failed — unexpected classification '${CLASS}'" >&2
    exit 1
    ;;
esac
