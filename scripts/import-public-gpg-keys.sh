#!/usr/bin/env bash
# Import project public GPG keys once (for SOPS encrypt / key-id checks).

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
public_key_path="${script_dir}/../public_gpg_keys"

shopt -s nullglob
keys=( "${public_key_path}"/*.asc )
if [ ${#keys[@]} -eq 0 ]; then
    exit 0
fi

for file in "${keys[@]}"; do
    gpg --batch --import "$file"
done
