#!/usr/bin/env bash
#
# DevPod injects credsStore=devpod into ~/.docker/config.json. The helper
# listens on the host (localhost:12049) and is unreachable inside DinD, so
# docker pull/compose fails with "connection refused". Use a container-local
# config without a credential helper instead.
#
# Intended to be sourced (load-env.sh, start.sh). Must not use "exit" when
# sourced — that would close the interactive shell. Use prefixed locals to
# avoid clobbering caller variables (e.g. script_dir in start.sh).

(return 0 2>/dev/null) && _sourced=1 || _sourced=0

_setup_docker_script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_setup_docker_repo_root="$(cd "${_setup_docker_script_dir}/.." && pwd)"
_setup_docker_config="${_setup_docker_repo_root}/.devcontainer/docker-config"

if [[ ! -f "${_setup_docker_config}/config.json" ]]; then
  echo "WARN: missing ${_setup_docker_config}/config.json" >&2
  [[ "${_sourced}" -eq 1 ]] && return 0
  exit 0
fi

if [[ -f "${HOME}/.docker/config.json" ]] \
  && grep -q '"credsStore"[[:space:]]*:[[:space:]]*"devpod"' "${HOME}/.docker/config.json" 2>/dev/null; then
  export DOCKER_CONFIG="${_setup_docker_config}"
  echo "✅ Docker: using container-local config (DevPod credsStore disabled for DinD)"
fi

unset _setup_docker_script_dir _setup_docker_repo_root _setup_docker_config _sourced

[[ "${BASH_SOURCE[0]}" != "${0}" ]] && return 0
exit 0
