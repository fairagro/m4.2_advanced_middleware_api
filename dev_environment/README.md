# Development Environment

Complete Docker Compose setup for local development and testing of the SQL-to-ARC middleware.

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
- Downloads and imports the Edaphobase dump from https://repo.edaphobase.org/rep/dumps/FAIRagro.sql
- Exits after completion

### 3. sql_to_arc
The SQL-to-ARC converter that:
- Builds from `../docker/Dockerfile.sql_to_arc`
- Waits for db-init to complete
- Mounts encrypted secrets via sops
- Runs the conversion and exits

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
3. Run the SQL-to-ARC converter

With image rebuild:
```bash
./start.sh --build
```

### View Logs

```bash
docker compose logs -f
docker compose logs -f postgres
docker compose logs -f sql_to_arc
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

The `start.sh` script uses `sops exec-file` to temporarily decrypt `client.key` during container startup.

### config.yaml

Application configuration for sql_to_arc:
- `db_host`: Set to `postgres` (Docker service name)
- `api_client.client_cert_path`: `/run/secrets/client.crt`
- `api_client.client_key_path`: `/run/secrets/client.key`

## Service Dependencies

```
postgres (healthcheck)
  ↓
db-init (waits for healthy postgres)
  ↓
sql_to_arc (waits for db-init completion)
```

## Troubleshooting

### Database not initializing
Check db-init logs:
```bash
docker compose logs db-init
```

Common issues:
- Network timeout downloading dump → retry with `docker compose up db-init`
- PostgreSQL not ready → check postgres healthcheck

### sql_to_arc fails
Check logs:
```bash
docker compose logs sql_to_arc
```

Common issues:
- Secrets not mounted → verify sops decryption works: `sops -d client.key`
- API unreachable → check `api_url` in config.yaml
- Database connection → verify db-init completed successfully

### Rebuild specific service
```bash
docker compose build sql_to_arc
docker compose up sql_to_arc
```

## Manual Usage (without start.sh)

If you don't want to use sops or the start script:

```bash
# Start postgres and db-init only
docker compose up -d postgres db-init

# Wait for initialization
docker compose logs -f db-init

# Run sql_to_arc manually (after decrypting secrets)
sops exec-file client.key \
  'docker compose run --rm sql_to_arc'
```

## Development Workflow

1. Make changes to sql_to_arc code
2. Rebuild image: `./start.sh --build`
3. View logs: `docker compose logs -f sql_to_arc`
4. Iterate

## Files

- `compose.yaml` - Docker Compose service definitions
- `config.yaml` - Application configuration
- `client.crt` - Client certificate (plain)
- `client.key` - Client private key (encrypted with sops)
- `start.sh` - Startup script with sops integration
- `run.sh` - **DEPRECATED** - Old script (kept for reference)
