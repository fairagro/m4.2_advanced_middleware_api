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

# Repo-local only: devcontainer bind-mounts host ~/.gitconfig read-only.
# --force: overwrite default hooks; project hooks below replace pre-push again.
echo "🚀 Initializing Git LFS (local config)..."
(cd "$REPO_ROOT" && git lfs install --local --skip-smudge --force)

for hook in pre-push post-checkout post-commit post-merge; do
    target_hook="$HOOKS_TARGET_DIR/$hook"
    source_hook="$HOOKS_SOURCE_DIR/$hook"

    [ -f "$source_hook" ] || continue

    if [ -f "$target_hook" ] && ! grep -q "version-controlled and should be installed via" "$target_hook" 2>/dev/null; then
        echo "📋 Backing up existing $hook hook to $hook.backup"
        cp "$target_hook" "$target_hook.backup"
    else
        echo "📝 Installing $hook hook"
    fi

    cp "$source_hook" "$target_hook"
    chmod +x "$target_hook"
done

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
