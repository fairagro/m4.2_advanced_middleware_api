# Development Environment

Complete Docker Compose setup for local development and testing of the FAIRagro Advanced Middleware.

## Services

### 1. postgres

PostgreSQL 15 database server with:

- Default credentials: `postgres/postgres`
- Port: `5432`
- Persistent volume: `postgres_data`
- Health check enabled

### 2. db-init

One-time initialization container that:

- Waits for PostgreSQL to be healthy
- Drops and recreates `edaphobase` database
- Downloads and imports the Edaphobase dump from <https://repo.edaphobase.org/rep/dumps/FAIRagro.sql>
- Exits after completion

### 3. middleware-api

The FAIRagro Middleware API service that:

- Builds from `../docker/Dockerfile.api`
- Runs on port `8000`
- Provides REST API for ARC management
- No mTLS validation in dev mode (HTTP without client certs)
- Health check via `/v1/liveness` endpoint

## Quick Start

### Prerequisites

- Docker and Docker Compose
- [sops](https://github.com/getsops/sops) for secret management
- Age or PGP key configured for sops decryption

### Start Everything

```bash
./start.sh
```

This will:

1. Start PostgreSQL
2. Initialize the database with Edaphobase data
3. Start the Middleware API and Celery worker

With image rebuild:

```bash
./start.sh --build
```

### View Logs

```bash
docker compose logs -f
docker compose logs -f postgres
docker compose logs -f middleware-api
```

### Stop Services

```bash
docker compose down
```

### Clean Everything (including data)

```bash
docker compose down -v
```

## Configuration

### Environment Variables

Set via `.env` file or shell environment:

- `POSTGRES_USER` - Database user (default: `postgres`)
- `POSTGRES_PASSWORD` - Database password (default: `postgres`)

### Secrets with sops

The `client.key` file should be encrypted with sops:

```bash
# Encrypt (first time)
sops -e -i client.key

# Edit encrypted file
sops client.key

# Decrypt to view
sops -d client.key
```

The `start.sh` script uses `sops exec-env` with `secrets.enc.yaml` during container startup.

## Troubleshooting

### Database not initializing

Check db-init logs:

```bash
docker compose logs db-init
```

Common issues:

- Network timeout downloading dump → retry with `docker compose up db-init`
- PostgreSQL not ready → check postgres healthcheck

### API unreachable

Check logs:

```bash
docker compose logs middleware-api
```

Common issues:

- Database connection → verify db-init completed successfully

## Development Workflow

1. Make changes to API code
2. Rebuild image: `./start.sh --build`
3. View logs: `docker compose logs -f middleware-api`
4. Iterate

## Files

- `compose.yaml` - Docker Compose service definitions
- `middleware-api-config.yaml` - API application configuration
- `client.crt` - Client certificate (plain)
- `client.key` - Client private key (encrypted with sops)
- `start.sh` - Startup script with sops integration
