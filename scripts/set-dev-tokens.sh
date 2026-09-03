#!/usr/bin/env bash
# Prompt for GH_TOKEN and GITGUARDIAN_API_KEY and save (overrides a previous skip).
# Source this to export into the current shell:  source scripts/set-dev-tokens.sh
# Do not `set -euo pipefail` here — this file is sourced into the caller shell.
export DEV_TOKENS_FORCE=1
# shellcheck source=scripts/dev-tokens.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/dev-tokens.sh"
unset DEV_TOKENS_FORCE
