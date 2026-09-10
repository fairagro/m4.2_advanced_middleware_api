(return 0 2>/dev/null) && sourced=1 || sourced=0
if [ $sourced -eq 0 ]; then
  echo "ERROR, this script is meant to be sourced."
  exit 1
fi

# Sourced from interactive ~/.bashrc — never abort the parent shell.
# Promote shared shell-init upstream: m4.2_middleware_devinfra#58.
__load_env_saved_opts="$(set +o)"
set +e
set +u
set +o pipefail 2>/dev/null || true

# Load Environment Script
# Decrypts shared `.env.integration.enc` → `.env`, then personal tokens
# (scripts/dev-tokens.sh: TTY prompt, /commandhistory/tokens.env).

# figure out some paths
mydir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)
repo_root="${mydir}/.."

# pre-commit and other dev tools live in the uv venv (not on PATH by default)
if [ -d "${repo_root}/.venv/bin" ]; then
    case ":${PATH}:" in
        *:"${repo_root}/.venv/bin":*) ;;
        *) export PATH="${repo_root}/.venv/bin:${PATH}" ;;
    esac
fi

# Product MYPYPATH until Devinfra #58 / #63 (verbatim pre-commit has no path overlay).
# Feature/pre-release/release pass the same value as reusable-code-quality `mypy_path`.
if [ -z "${MYPYPATH:-}" ]; then
    export MYPYPATH="stubs:middleware/api/src:middleware/api_client/src:middleware/shared/src:middleware/api/tests/unit:middleware/api_client/tests/unit:middleware/shared/tests"
fi

# Wave C Bake: pre-push container-structure-test needs CST_BAKE_TARGET matching docker-bake.hcl.
if [ -z "${CST_BAKE_TARGET:-}" ] && [ -f "${repo_root}/docker-bake.hcl" ]; then
    export CST_BAKE_TARGET=api
fi

# Setup aliases (completions: static files in image + bash-completion lazy-load)
alias k=kubectl
alias d=docker
alias kda="kubectl delete all,pdb,configmap,secret,pvc,ingress,serviceaccount,endpoints --all"
alias kga="kubectl get all,pdb,configmap,secret,pvc,ingress,serviceaccount,endpoints"
alias ksn="kubectl config set-context --current --namespace"

# Set bash completion for aliases
declare -F __start_kubectl &>/dev/null && complete -o default -F __start_kubectl k
declare -F __start_docker &>/dev/null && complete -o default -F __start_docker d

# ggshield (dev dependency in .venv; same PATH as pre-commit above)
if command -v ggshield &> /dev/null; then
    if [ -n "${GITGUARDIAN_API_KEY:-}" ]; then
        echo "✅ ggshield: using GITGUARDIAN_API_KEY from environment"
    elif [ -f ~/.config/ggshield/auth_config.yaml ] && grep -q "token:" ~/.config/ggshield/auth_config.yaml 2>/dev/null; then
        echo "✅ ggshield: authenticated (~/.config/ggshield/auth_config.yaml)"
    else
        echo "🔐 ggshield not authenticated — run: ggshield auth login --method token"
        echo "   Or set GITGUARDIAN_API_KEY (non-interactive)"
    fi
else
    echo "⚠️ ggshield not available - run: uv sync --dev --all-packages"
fi

ENCRYPTED_FILE="${mydir}/../.env.integration.enc"
DECRYPTED_FILE="${mydir}/../.env"

# Check if .env file already exists and is not empty
if [ -f "$DECRYPTED_FILE" ] && [ -s "$DECRYPTED_FILE" ]; then
    echo "✅ $DECRYPTED_FILE already exists and is not empty - skipping decryption"

    # Still load for current shell if not already loaded
    if [ -z "${GITLAB_API_TOKEN:-}" ]; then
        echo "🔄 Loading existing environment variables..."
        set -a
        # shellcheck source=/dev/null
        source "$DECRYPTED_FILE"
        set +a
        echo "✅ Environment variables loaded from existing $DECRYPTED_FILE"
    else
        echo "✅ Environment variables already loaded"
    fi
else
    # Check if SOPS is available
    if ! command -v sops &> /dev/null; then
        echo "⚠️ SOPS not available - skipping secrets loading"
    elif [ ! -f "$ENCRYPTED_FILE" ]; then
        echo "⚠️ $ENCRYPTED_FILE not found - skipping secrets loading"
    elif grep -q '"sops"' "$ENCRYPTED_FILE" 2>/dev/null; then
        if sops -d "$ENCRYPTED_FILE" > "$DECRYPTED_FILE" 2>/dev/null; then
            echo "✅ Encrypted secrets decrypted to $DECRYPTED_FILE"
            set -a
            # shellcheck source=/dev/null
            source "$DECRYPTED_FILE"
            set +a
        else
            echo "❌ Error decrypting $ENCRYPTED_FILE"
            echo "💡 Possible causes:"
            echo "   - Wrong GPG password"
            echo "   - GPG key not available"
            echo "   - SOPS configuration error"
            echo "📝 Tests may fail without valid GITLAB_API_TOKEN"
        fi
    else
        echo "⚠️ $ENCRYPTED_FILE is not encrypted or not in SOPS format"
        echo "📝 Tests may fail without valid GITLAB_API_TOKEN"
    fi
fi

# shellcheck source=scripts/dev-tokens.sh
source "${mydir}/dev-tokens.sh"

eval "${__load_env_saved_opts}"
return 0
