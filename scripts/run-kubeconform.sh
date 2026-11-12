#!/usr/bin/env bash
# Thin kubeconform wrapper for consumer CI after helm template (or any rendered manifests).
# Usage:
#   scripts/run-kubeconform.sh [kubeconform flags…] [--] [manifest files…]
#   helm template … | scripts/run-kubeconform.sh [kubeconform flags…]
# Does not discover charts, does not run helm template, does not ship CRD schema packs.
# Environment: host or Dev Container. Pin: versions.env KUBECONFORM_VERSION
# (+ scripts/install-pinned-tool.sh kubeconform).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

pin=""
if [[ -f "${REPO_ROOT}/versions.env" ]]; then
  pin="$(grep -E '^KUBECONFORM_VERSION=' "${REPO_ROOT}/versions.env" | tail -n1 | cut -d= -f2- || true)"
fi

if ! command -v kubeconform >/dev/null 2>&1; then
  echo "run-kubeconform: kubeconform is not on PATH." >&2
  echo "run-kubeconform: use the Linux Dev Container (KUBECONFORM_VERSION=${pin:-unset}) or bash scripts/install-pinned-tool.sh kubeconform." >&2
  exit 1
fi

echo "run-kubeconform: using $(command -v kubeconform) pin=${pin:-unset}" >&2

# TTY + no manifest paths → usage (flags-only like `-summary` would otherwise hang on stdin).
# Piped stdin and/or positional paths (including after `--`) are fine.
has_manifest_arg=0
seen_dd=0
for arg in "$@"; do
  if [[ "${seen_dd}" -eq 1 ]]; then
    has_manifest_arg=1
    break
  fi
  if [[ "${arg}" == "--" ]]; then
    seen_dd=1
    continue
  fi
  if [[ "${arg}" != -* ]]; then
    has_manifest_arg=1
    break
  fi
done

if [[ -t 0 && "${has_manifest_arg}" -eq 0 ]]; then
  echo "run-kubeconform: pass manifest files and/or pipe YAML on stdin; extra args are forwarded to kubeconform." >&2
  echo "run-kubeconform: example: helm template ci ./charts/app | bash scripts/run-kubeconform.sh -summary" >&2
  exit 1
fi

exec kubeconform "$@"
