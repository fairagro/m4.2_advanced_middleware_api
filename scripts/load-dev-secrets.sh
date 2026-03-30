#!/usr/bin/env bash
#
# Source this script to load development secrets from dev_environment/secrets.enc.yaml
# into the current shell.
#
# Usage:
#   source scripts/load-dev-secrets.sh
#

(return 0 2>/dev/null) && sourced=1 || sourced=0
if [ "$sourced" -eq 0 ]; then
  echo "ERROR: this script must be sourced, not executed."
  echo "Use: source scripts/load-dev-secrets.sh"
  exit 1
fi

# Do not modify caller shell options when sourced.
# We keep explicit error handling below instead of relying on strict mode.

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
repo_root="$(cd -- "$script_dir/.." &> /dev/null && pwd)"
secrets_file="$repo_root/dev_environment/secrets.enc.yaml"

if ! command -v sops &> /dev/null; then
  echo "ERROR: sops is not installed or not in PATH"
  return 1
fi

if [ ! -f "$secrets_file" ]; then
  echo "ERROR: secrets file not found: $secrets_file"
  return 1
fi

raw_env="$(sops exec-env "$secrets_file" 'env' 2>/dev/null || true)"

if [ -z "$raw_env" ]; then
  echo "ERROR: failed to decrypt or read env from $secrets_file"
  echo "Check sops decryption/key setup."
  return 1
fi

keys=(
  GITLAB_API_TOKEN
  GIT_REPO_TOKEN
  CELERY_BROKER_URL
  RABBITMQ_DEFAULT_USER
  RABBITMQ_DEFAULT_PASS
  COUCHDB_USER
  COUCHDB_PASSWORD
)

loaded_any=0
for k in "${keys[@]}"; do
  value="$(printf '%s\n' "$raw_env" | sed -n "s/^${k}=//p" | head -n 1)"
  if [ -n "$value" ]; then
    export "$k=$value"
    loaded_any=1
  fi
done

if [ "$loaded_any" -eq 0 ]; then
  echo "ERROR: no variables were loaded from $secrets_file"
  echo "Check sops decryption/key setup."
  return 1
fi

echo "Loaded development secrets into current shell:"
echo "  - GITLAB_API_TOKEN"
echo "  - GIT_REPO_TOKEN"
echo "  - CELERY_BROKER_URL"
echo "  - RABBITMQ_DEFAULT_USER"
echo "  - RABBITMQ_DEFAULT_PASS"
echo "  - COUCHDB_USER"
echo "  - COUCHDB_PASSWORD"
