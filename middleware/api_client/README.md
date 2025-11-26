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
from middleware.api_client import Config, MiddlewareClient
from middleware.shared.api_models.models import CreateOrUpdateArcsRequest

async def main():
    # Load configuration
    config = Config.from_yaml_file(Path("config.yaml"))

    # Use client with context manager
    async with MiddlewareClient(config) as client:
        # Create request
        request = CreateOrUpdateArcsRequest(
            rdi="my-rdi",
            arcs=[{
                "@context": "https://w3id.org/ro/crate/1.1/context",
                "@id": "my-arc",
                "@type": "Dataset",
                # ... more RO-Crate fields
            }]
        )

        # Send request
        response = await client.create_or_update_arcs(request)
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

### `create_or_update_arcs(request)`

Creates or updates ARCs in the Middleware API.

**Parameters:**

- `request` (CreateOrUpdateArcsRequest): Request containing RDI and ARC data

**Returns:**

- `CreateOrUpdateArcsResponse`: Response with operation results

**Raises:**

- `MiddlewareClientError`: If the request fails

## Error Handling

All errors are raised as `MiddlewareClientError` exceptions:

```python
from middleware.api_client import MiddlewareClientError

try:
    response = await client.create_or_update_arcs(request)
except MiddlewareClientError as e:
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
