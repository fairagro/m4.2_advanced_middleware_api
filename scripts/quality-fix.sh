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

echo -e "${YELLOW}🔧 1. Running Black (Auto-formatting)...${NC}"
uv run black middleware_api/ tests/
echo -e "${GREEN}✅ Black formatting applied${NC}"

echo -e "${YELLOW}🔧 2. Running isort (Auto-sorting imports)...${NC}"
uv run isort middleware_api/ tests/
echo -e "${GREEN}✅ Import sorting applied${NC}"

echo -e "${YELLOW}🔧 3. Running Ruff (Auto-fixing)...${NC}"
uv run ruff check --fix middleware_api/ tests/ || true
echo -e "${GREEN}✅ Ruff auto-fixes applied${NC}"

echo -e "${GREEN}🎉 Auto-fixes completed!${NC}"
echo "Now run the quality checks to see remaining issues:"
echo "./scripts/quality-check.sh"
