#!/bin/bash
# Git LFS Hooks Setup Script
# This script installs Git LFS hooks that are compatible with pre-commit
# Run this script after cloning the repository or when setting up a development environment

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOKS_SOURCE_DIR="$REPO_ROOT/scripts/git-hooks"
HOOKS_TARGET_DIR="$REPO_ROOT/.git/hooks"

echo "🔧 Setting up Git LFS hooks for repository..."

# Check if Git LFS is available
if ! command -v git-lfs >/dev/null 2>&1; then
    echo "❌ Git LFS is not installed!"
    echo "📦 Installing Git LFS..."

    # Try to install Git LFS
    if command -v apt-get >/dev/null 2>&1; then
        sudo apt-get update && sudo apt-get install -y git-lfs
    elif command -v brew >/dev/null 2>&1; then
        brew install git-lfs
    else
        echo "❌ Could not install Git LFS automatically."
        echo "Please install Git LFS manually: https://git-lfs.github.io/"
        exit 1
    fi
fi

echo "✅ Git LFS is available: $(git lfs version)"

# Check if we're in a Git repository
if [ ! -d "$REPO_ROOT/.git" ]; then
    echo "❌ Not in a Git repository root"
    exit 1
fi

# Backup existing hooks if they exist and are not our hooks
for hook in pre-push post-checkout post-commit post-merge; do
    target_hook="$HOOKS_TARGET_DIR/$hook"
    source_hook="$HOOKS_SOURCE_DIR/$hook"

    if [ -f "$target_hook" ] && [ -f "$source_hook" ]; then
        # Check if it's already our hook
        if grep -q "version-controlled and should be installed via" "$target_hook" 2>/dev/null; then
            echo "🔄 Hook $hook is already installed (our version)"
            continue
        fi

        # Backup existing hook
        echo "📋 Backing up existing $hook hook to $hook.backup"
        cp "$target_hook" "$target_hook.backup"
    fi

    if [ -f "$source_hook" ]; then
        echo "📝 Installing $hook hook"
        cp "$source_hook" "$target_hook"
        chmod +x "$target_hook"
    fi
done

# Initialize Git LFS (this is safe to run multiple times)
echo "🚀 Initializing Git LFS..."
git lfs install --skip-smudge

echo ""
echo "✅ Git LFS hooks setup complete!"
echo ""
echo "📁 Installed hooks:"
ls -la "$HOOKS_TARGET_DIR"/{pre-push,post-checkout,post-commit,post-merge} 2>/dev/null || true
echo ""
echo "🔍 Git LFS tracked files:"
git lfs ls-files
echo ""
echo "💡 To verify the setup:"
echo "   git lfs env"
echo "   git status"
