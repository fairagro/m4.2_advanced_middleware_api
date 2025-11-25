#!/usr/bin/env bash
set -e

docker compose up -d

export PGPASSWORD=postgres

# Warten bis PostgreSQL erreichbar ist
echo "Warte auf PostgreSQL..."
for i in {1..30}; do
  if psql -h localhost -U postgres -d postgres -c '\q' 2>/dev/null; then
    echo "PostgreSQL ist bereit."
    break
  fi
  sleep 1
done

# Drop database if exists
psql -h localhost -U postgres -d postgres -c "DROP DATABASE IF EXISTS edaphobase;"
# Create new database
psql -h localhost -U postgres -d postgres -c "CREATE DATABASE edaphobase;"

# Import dump
wget -O - https://repo.edaphobase.org/rep/dumps/FAIRagro.sql | \
    psql -h localhost -U postgres -d edaphobase
