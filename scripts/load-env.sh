(return 0 2>/dev/null) && sourced=1 || sourced=0
if [ $sourced -eq 0 ]; then
  echo "ERROR, this script is meant to be sourced."
  exit 1
fi

# Load Environment Script
# Decrypts .env.integration.enc and generates .env for tests

# figure out some paths
mydir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)

# import all public keyfiles into gpg keyring so sops can find them
public_key_path="${mydir}/../public_gpg_keys"
for file in "$public_key_path"/*.asc; do
    [ -e "$file" ] || continue
    gpg --import "$file"
done

# Create Bash autocompletion for installed tools
[ -f /etc/bash_completion ] && . /etc/bash_completion || true
command -v kubectl &>/dev/null && . <(kubectl completion bash) || true
command -v helm &>/dev/null && . <(helm completion bash) || true
command -v docker &>/dev/null && . <(docker completion bash) || true
command -v minikube &>/dev/null && . <(minikube completion bash) || true
command -v sops &>/dev/null && . <(sops completion bash) || true

# Setup aliases
alias k=kubectl
alias d=docker
alias kda="kubectl delete all,pdb,configmap,secret,pvc,ingress,serviceaccount,endpoints --all"
alias kga="kubectl get all,pdb,configmap,secret,pvc,ingress,serviceaccount,endpoints"
alias ksn="kubectl config set-context --current --namespace"

# Set bash completion for aliases
declare -F __start_kubectl &>/dev/null && complete -o default -F __start_kubectl k
declare -F __start_docker &>/dev/null && complete -o default -F __start_docker d

# Install pre-commit hooks if not already installed
if command -v pre-commit &> /dev/null; then
    hooks_installed=true
    if [ ! -f "${mydir}/../.git/hooks/pre-commit" ]; then
        echo "🔧 Installing pre-commit hooks..."
        (cd "${mydir}/.." && pre-commit install --hook-type pre-commit)
        hooks_installed=$?
    fi
    if [ ! -f "${mydir}/../.git/hooks/pre-push" ]; then
        echo "🔧 Installing pre-push hooks..."
        (cd "${mydir}/.." && pre-commit install --hook-type pre-push)
        hooks_installed=$?
    fi
    if [ $hooks_installed -eq 0 ]; then
        echo "✅ Pre-commit and pre-push hooks installed successfully"
    else
        echo "⚠️ Failed to install some hooks"
    fi
else
    echo "⚠️ pre-commit not available - skipping hook installation"
fi

ENCRYPTED_FILE="${mydir}/../.env.integration.enc"
DECRYPTED_FILE="${mydir}/../.env"

# Check if .env file already exists and is not empty
if [ -f "$DECRYPTED_FILE" ] && [ -s "$DECRYPTED_FILE" ]; then
    echo "✅ $DECRYPTED_FILE already exists and is not empty - skipping decryption"

    # Still load for current shell if not already loaded
    if [ -z "$GITLAB_API_TOKEN" ]; then
        echo "🔄 Loading existing environment variables..."
        set -a
        source "$DECRYPTED_FILE"
        set +a
        echo "✅ Environment variables loaded from existing $DECRYPTED_FILE"
    else
        echo "✅ Environment variables already loaded"
    fi
    return 0
fi

# Check if SOPS is available
if ! command -v sops &> /dev/null; then
    echo "⚠️ SOPS not available - skipping secrets loading"
    return 0
fi

# Check if encrypted file exists
if [ ! -f "$ENCRYPTED_FILE" ]; then
    echo "⚠️ $ENCRYPTED_FILE not found - skipping secrets loading"
    return 0
fi

# Decrypt the encrypted file and write to .env
if grep -q '"sops"' "$ENCRYPTED_FILE" 2>/dev/null; then
    # Decrypt encrypted file and write to .env
    sops -d "$ENCRYPTED_FILE" > "$DECRYPTED_FILE" 2>/dev/null
    if [ $? -eq 0 ]; then
        echo "✅ Encrypted secrets decrypted to $DECRYPTED_FILE"

        # Also load for current shell
        set -a
        source "$DECRYPTED_FILE"
        set +a
    else
        echo "❌ Error decrypting $ENCRYPTED_FILE"
        echo "💡 Possible causes:"
        echo "   - Wrong GPG password"
        echo "   - GPG key not available"
        echo "   - SOPS configuration error"
        echo "📝 Tests may fail without valid GITLAB_API_TOKEN"
        return 0  # Graceful return so sourcing continues
    fi
else
    echo "⚠️ $ENCRYPTED_FILE is not encrypted or not in SOPS format"
    echo "📝 Tests may fail without valid GITLAB_API_TOKEN"
    return 0  # Graceful return so sourcing continues
fi
