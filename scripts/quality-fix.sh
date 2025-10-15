#!/bin/bash

# Code Quality Fix Script
# Führt automatische Korrekturen durch

set -e

echo "🔧 Starting Code Quality Fixes..."
echo "================================="

# Farben
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}🔧 1. Running Ruff (Auto-fixing linting issues)...${NC}"
uv run ruff check --fix middleware_api/ tests/ || true
echo -e "${GREEN}✅ Ruff auto-fixes applied${NC}"

echo -e "${YELLOW}🔧 2. Running Ruff (Auto-formatting)...${NC}"
uv run ruff format middleware_api/ tests/
echo -e "${GREEN}✅ Ruff formatting applied${NC}"

echo -e "${GREEN}🎉 Auto-fixes completed!${NC}"
echo "Now run the quality checks to see remaining issues:"
echo "./scripts/quality-check.sh"
