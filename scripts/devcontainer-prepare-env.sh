#!/usr/bin/env bash
# Host-side prepare before Dev Container Compose build (Linux/macOS initializeCommand).
# Copies versions.env → .devcontainer/.env so Compose can substitute build-args.
# Environment: host or Dev Container workspace root (repo checkout).
# Windows uses scripts/devcontainer-prepare-env.cmd → .ps1 (#415); do not call bash there.
#
# Must rm before cp: if .devcontainer/.env is a symlink, overwrite would write
# through into versions.env. core.symlinks=false checkouts cannot rely on a
# tracked symlink (#410).

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/.." && pwd)"
cd "${repo_root}"

if [[ ! -f versions.env ]]; then
  echo "ERROR: versions.env missing at repo root (${repo_root})" >&2
  exit 1
fi

mkdir -p .devcontainer
rm -f .devcontainer/.env
cp versions.env .devcontainer/.env
echo "Prepared .devcontainer/.env from versions.env"
