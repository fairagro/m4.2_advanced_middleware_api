#!/usr/bin/env bash
# Container GPG setup: host agent socket, writable trustdb copy, public key import.
# Run once from devcontainer postCreate (order-sensitive — do not split across hooks).

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/.." && pwd)"
public_key_path="${repo_root}/public_gpg_keys"

mkdir -p ~/.gnupg
chmod 700 ~/.gnupg
rm -f ~/.gnupg/gpg-agent.conf
grep -qF use-agent ~/.gnupg/gpg.conf 2>/dev/null || echo use-agent >> ~/.gnupg/gpg.conf

if [ -S /host-gpg/S.gpg-agent.extra ]; then
    ln -sf /host-gpg/S.gpg-agent.extra ~/.gnupg/S.gpg-agent
else
    echo "WARN: host gpg-agent socket missing — run gpg on host, then devpod up --recreate"
fi

# Writable copy: a readonly bind-mounted trustdb symlink breaks gpg --import on recreate.
rm -f ~/.gnupg/trustdb.gpg
if [ -f /host-gpg/trustdb.gpg ]; then
    cp /host-gpg/trustdb.gpg ~/.gnupg/trustdb.gpg
fi

shopt -s nullglob
keys=( "${public_key_path}"/*.asc )
if [ ${#keys[@]} -gt 0 ]; then
    for file in "${keys[@]}"; do
        gpg --batch --import "$file"
    done
fi
