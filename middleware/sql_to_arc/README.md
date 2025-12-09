# SQL to ARC Converter

The `sql_to_arc` package converts data from a PostgreSQL database schema into FAIR ARC containers using ARCtrl, and uploads them to the Advanced Middleware API.

## Features

- Async PostgreSQL access via `psycopg` (v3)
- Mapping of Investigations, Studies, Assays to ARCtrl models
- Batch upload to the Middleware API using `ApiClient`
- Pydantic-based configuration

## Requirements

- Python 3.12+
- PostgreSQL reachable from runtime
- The workspace packages `shared` and `api_client` available (uv workspace)

## Install (uv)

This repo uses `uv` for dependency management.

```bash
# from repository root
uv sync --all-packages
uv run python -m middleware.sql_to_arc.main
```

If you prefer a virtual environment only for this package:

```bash
cd middleware/sql_to_arc
uv sync
uv run python -m middleware.sql_to_arc.main
```

## Configuration

Configuration is defined by `middleware.sql_to_arc.config.Config` and can be provided as dict, env, or file. The default example in `main.py`:

```python
config = Config.from_data({
  "db_name": "edaphobase",
  "db_user": "postgres",
  "db_password": "postgres",
  "db_host": "localhost",
  "rdi": "edaphobase",
  "api_client": {
    "api_url": "http://localhost:8000",
    "client_cert_path": "/path/to/cert.pem",
    "client_key_path": "/path/to/key.pem",
    "verify_ssl": "false",
  },
})
```

Environment variables can be supported by extending `Config` (e.g., `pydantic` `BaseSettings`).

## Running

Run the converter locally (async):

```bash
uv run python -m middleware.sql_to_arc.main
```

This will:

- Open a DB connection
- Fetch Investigations, Studies, Assays
- Map them to ARCtrl objects
- Upload batches to the Middleware API

## Docker

A Dockerfile for building a standalone binary exists at `docker/Dockerfile.sql_to_arc`.

Build:

```bash
docker build -f docker/Dockerfile.sql_to_arc -t sql-to-arc .
```

Run:

```bash
docker run --rm -e DB_HOST=... -e DB_USER=... -e DB_PASSWORD=... -e API_URL=... sql-to-arc
```

Adjust env variables or mount configuration as needed.

## Development

- Tests are under `middleware/sql_to_arc/tests`
- Mapping logic in `middleware/sql_to_arc/src/middleware/sql_to_arc/mapper.py`
- Main entrypoint `middleware/sql_to_arc/src/middleware/sql_to_arc/main.py`

Lint / format / type-check:

```bash
uv run ruff check
uv run ruff format
uv run mypy -p middleware.sql_to_arc
```

## Troubleshooting

- Connection errors: verify DB host/port/user/password
- API errors: ensure `api_client` settings and server availability
- Type errors: run `uv run mypy` and update models/config accordingly
