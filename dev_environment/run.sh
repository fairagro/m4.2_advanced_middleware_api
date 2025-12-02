#!/usr/bin/env bash
set -e

# ---- Run docker-compose to start PostgreSQL ----

docker compose up -d


# ---- Import Edaphobase dump into PostgreSQL ----

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


# ---- Build sql-to-arc tool ----
(
  cd ..
  docker build -f docker/Dockerfile.sql_to_arc -t sql_to_arc:test .
)

# ---- Run sql-to-arc

export DB_PASSWORD=$PGPASSWORD

sops exec-file client.key \
  'docker run \
  -v {}:/tmp/client.key \
  -v client.crt:/tmp/client.crt \
  -v config.yaml:/tmp/config.yaml \
  sql_to_arc:test \
  /middleware/sql_to_arc -c /tmp/config.yaml'
