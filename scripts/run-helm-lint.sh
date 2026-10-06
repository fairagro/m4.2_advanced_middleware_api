#!/usr/bin/env bash
# Commit-stage Helm lint + default-values template smoke.
# Discovers helmchart/<chart>/Chart.yaml and helm/<chart>/Chart.yaml.
# No charts → success (Helm optional). Charts present → helm on PATH required.
# Environment: host or Dev Container. Supported pin: versions.env HELM_VERSION (Dev Container image).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

shopt -s nullglob

charts=()
for yaml in helmchart/*/Chart.yaml helm/*/Chart.yaml; do
  [[ -f "${yaml}" ]] || continue
  charts+=("$(dirname "${yaml}")")
done

if [[ "${#charts[@]}" -eq 0 ]]; then
  echo "helm lint: no helmchart/*/Chart.yaml or helm/*/Chart.yaml — skipping." >&2
  exit 0
fi

helm_pin=""
if [[ -f "${REPO_ROOT}/versions.env" ]]; then
  helm_pin="$(grep -E '^HELM_VERSION=' "${REPO_ROOT}/versions.env" | tail -n1 | cut -d= -f2- || true)"
fi

if ! command -v helm >/dev/null 2>&1; then
  echo "helm lint: charts found (${charts[*]}) but helm is not on PATH." >&2
  echo "helm lint: use the Linux Dev Container (Helm from versions.env HELM_VERSION=${helm_pin:-unset}) or install that pin." >&2
  exit 1
fi

echo "helm lint: using $(command -v helm) ($(helm version --short 2>/dev/null || echo unknown)) pin=${helm_pin:-unset}" >&2

for chart in "${charts[@]}"; do
  echo "helm lint: lint ${chart}" >&2
  helm lint "./${chart}"
  echo "helm lint: template smoke ${chart}" >&2
  helm template ci-smoke "./${chart}" >/dev/null
done
