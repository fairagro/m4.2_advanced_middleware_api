#!/bin/bash

# Code Quality Check Script
# Führt alle Qualitätsprüfungen lokal aus

echo "🔍 Starting Code Quality Checks..."
echo "=================================="

# Farben für bessere Lesbarkeit
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print status
print_status() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ $1 passed${NC}"
    else
        echo -e "${RED}❌ $1 failed${NC}"
        exit 1
    fi
}

# Run all quality checks defined in pre-commit
echo -e "${YELLOW}🔍 1. Running all pre-commit checks..."
pre-commit run --hook-stage push --all-files
print_status 'pre-commit checks'
echo -e "${GREEN}🎉 All quality checks passed!${NC}"
echo "================================="
