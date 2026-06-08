#!/usr/bin/env bash
#
# Open this repository in a Dev Container via DevPod + Cursor.
#
# Cursor has no built-in "Reopen in Container" (unlike VS Code). DevPod builds
# the devcontainer and connects Cursor over SSH — equivalent to VS Code's flow,
# where load-env.sh runs inside the container after it starts (via postCreateCommand).
#
# Usage:
#   ./scripts/start-devcontainer-cursor.sh
#   ./scripts/start-devcontainer-cursor.sh --recreate
#   ./scripts/start-devcontainer-cursor.sh --reset
#
# Platform notes:
#   Host GPG agent bind-mount (SOPS in container) requires Linux and XDG_RUNTIME_DIR.
#   On macOS/Windows, see .devcontainer/cursor/README.md (decrypt .env on the host).

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/.." && pwd)"
devcontainer_path=".devcontainer/cursor/devcontainer.json"

extra_args=()
for arg in "$@"; do
    case "$arg" in
        --recreate | --reset)
            extra_args+=("$arg")
            ;;
        -h | --help)
            cat << 'EOF_HELP'
Open this repository in a Dev Container via DevPod + Cursor.

Cursor has no built-in "Reopen in Container" (unlike VS Code). DevPod builds
the devcontainer and connects Cursor over SSH — equivalent to VS Code's flow,
where load-env.sh runs inside the container after it starts (via postCreateCommand).

Usage:
  ./scripts/start-devcontainer-cursor.sh
  ./scripts/start-devcontainer-cursor.sh --recreate
  ./scripts/start-devcontainer-cursor.sh --reset

Platform notes:
  Host GPG agent bind-mount (SOPS in container) requires Linux and XDG_RUNTIME_DIR.
  On macOS/Windows, see .devcontainer/cursor/README.md (decrypt .env on the host).
EOF_HELP
            exit 0
            ;;
        *)
            echo "ERROR: Unknown argument: $arg" >&2
            echo "Run with --help for usage." >&2
            exit 1
            ;;
    esac
done

if ! command -v devpod &>/dev/null; then
    echo "ERROR: devpod not found in PATH. Install DevPod: https://devpod.sh/docs/getting-started/install" >&2
    exit 1
fi

if ! docker info &>/dev/null; then
    echo "WARNING: Local Docker daemon is not running or not reachable. If you are using a remote DevPod provider, you can ignore this." >&2
fi

echo "==> Starting DevPod workspace (devcontainer: ${devcontainer_path})"
devpod up "${repo_root}" \
    --devcontainer-path "${devcontainer_path}" \
    --ide cursor \
    "${extra_args[@]}"

echo ""
echo "==> Done. Cursor should open the workspace in the Dev Container."
echo "    One-time setup (uv sync, hooks) runs via postCreateCommand; load-env.sh loads env vars per shell."
echo "    Host ~/.gitconfig is bind-mounted; GPG agent forwarding is Linux-only."
echo "    See .devcontainer/cursor/README.md for mounts and macOS/Windows workarounds."
