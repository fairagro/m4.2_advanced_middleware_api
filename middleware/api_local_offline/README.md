# fairagro-middleware-api-local-offline

Local offline Middleware API stand-in for harvester and sql-to-arc tests: enough `/v3` harvest HTTP for
`ApiClient.harvest_arcs`, writes each accepted ARC under a configurable directory (no CouchDB, RabbitMQ, or DataHUB).

## Install

```bash
uv add fairagro-middleware-api-local-offline
# or: pip install fairagro-middleware-api-local-offline
```

Pair with `fairagro-middleware-api-client` in consumer test suites.

## Run (CLI)

```yaml
# local_offline.yaml — do not reuse a production API config
log_level: INFO
output_root: /data/arcs
```

```bash
middleware-api-local-offline --config local_offline.yaml --port 8000
# Optional: --host 0.0.0.0 when the process must accept connections from other containers
```

Point `ApiClient` at `http://127.0.0.1:8000` and assert on files under `output_root`.

## In-process (pytest / ASGI)

```python
from pathlib import Path
from middleware.api_local_offline import LocalOfflineConfig, create_local_offline_app

app = create_local_offline_app(LocalOfflineConfig(output_root=Path("/tmp/arcs")))
```

## Config

Only stand-in fields are accepted (`extra=forbid`). Keys such as `couchdb`, `celery`, and `arc_store` are rejected so a
production Middleware YAML cannot be loaded by mistake.
