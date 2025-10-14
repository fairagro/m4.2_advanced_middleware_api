#!/bin/bash

# Load Environment Script
# Decrypts .env.integration.enc and generates .env for tests

# Note: No 'set -e' so container starts even if secrets loading fails

ENCRYPTED_FILE=".env.integration.enc"
DECRYPTED_FILE=".env"

# Check if SOPS is available
if ! command -v sops &> /dev/null; then
    echo "⚠️ SOPS not available - skipping secrets loading"
    exit 0
fi

# Check if encrypted file exists
if [ ! -f "$ENCRYPTED_FILE" ]; then
    echo "⚠️ $ENCRYPTED_FILE not found - skipping secrets loading"
    exit 0
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
        exit 0  # Graceful exit so container starts
    fi
else
    echo "⚠️ $ENCRYPTED_FILE is not encrypted or not in SOPS format"
    echo "📝 Tests may fail without valid GITLAB_API_TOKEN"
    exit 0  # Graceful exit so container starts
fi
