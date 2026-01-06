# Middleware API Client

Python client for the FAIRagro Middleware API with certificate-based authentication (mTLS).

## Features

- ✅ Certificate-based authentication (mutual TLS)
- ✅ Configuration via YAML files, environment variables, or Docker secrets
- ✅ Async context manager support
- ✅ Comprehensive error handling
- ✅ Type-safe with Pydantic models

## Installation

This package is part of the FAIRagro Advanced Middleware project and uses local dependencies.

## Quick Start

### 1. Create Configuration File

```yaml
# config.yaml
log_level: INFO
api_url: https://your-api-server:8000
client_cert_path: /path/to/client-cert.pem
client_key_path: /path/to/client-key.pem
ca_cert_path: /path/to/ca-cert.pem  # optional
timeout: 30.0
verify_ssl: true
```

### 2. Use the Client

```python
import asyncio
from pathlib import Path
from arctrl import ARC, ArcInvestigation
from middleware.api_client import Config, ApiClient

async def main():
    # Load configuration
    config = Config.from_yaml_file(Path("config.yaml"))

    # Create ARC object
    inv = ArcInvestigation.create(identifier="my-arc", title="My ARC")
    arc = ARC.from_arc_investigation(inv)

    # Use client with context manager
    async with ApiClient(config) as client:
        # Send request
        response = await client.create_or_update_arcs(
            rdi="my-rdi",
            arcs=[arc]
        )
        print(f"Created/Updated {len(response.arcs)} ARCs")

asyncio.run(main())
```

## Configuration Options

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `log_level` | string | No | INFO | Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL) |
| `api_url` | string | Yes | - | Base URL of the Middleware API |
| `client_cert_path` | string | Yes | - | Path to client certificate (PEM format) |
| `client_key_path` | string | Yes | - | Path to client private key (PEM format) |
| `ca_cert_path` | string | No | null | Path to CA certificate for server verification |
| `timeout` | float | No | 30.0 | Request timeout in seconds |
| `verify_ssl` | bool | No | true | Enable SSL certificate verification |

## API Methods

### `create_or_update_arcs(rdi: str, arcs: list[ARC]) -> CreateOrUpdateArcsResponse`

Create or update ARCs in the Middleware API.

**Parameters:**

- `rdi` (str): The RDI identifier (e.g., "edaphobase").
- `arcs` (list[ARC]): List of ARC objects from arctrl library.

**Returns:**

- `CreateOrUpdateArcsResponse`: Contains the result of the operation.

**Raises:**

- `ApiClientError`: If the request fails due to HTTP errors or network issues.

**Example:**

```python
from arctrl import ARC, ArcInvestigation

inv = ArcInvestigation.create(identifier="my-arc-001", title="My ARC")
arc = ARC.from_arc_investigation(inv)

response = await client.create_or_update_arcs(
    rdi="edaphobase",
    arcs=[arc]
)
```

All errors are raised as `ApiClientError` exceptions:

```python
from middleware.api_client import ApiClientError

try:
    response = await client.create_or_update_arcs(
        rdi="my-rdi",
        arcs=[arc]
    )
except ApiClientError as e:
    print(f"API Error: {e}")
```

## Configuration via Environment Variables

You can override configuration values using environment variables:

```bash
export API_URL="https://production-api:8000"
export CLIENT_CERT_PATH="/secure/certs/prod-cert.pem"
export CLIENT_KEY_PATH="/secure/certs/prod-key.pem"
```

Or use Docker secrets in `/run/secrets/`.

## License

This is part of the FAIRagro Advanced Middleware project.
