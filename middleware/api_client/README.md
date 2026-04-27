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
        # Send a single ARC
        response = await client.create_or_update_arc(
            rdi="my-rdi",
            arc=arc,  # Can be ARC object, dict, or JSON string
        )
        print(f"ARC status: {response.status}")

        # Or run a harvest workflow
        async def arc_stream():
            yield arc  # Can yield ARC objects, dicts, or JSON strings

        harvest = await client.harvest_arcs(
            rdi="my-rdi",
            arcs=arc_stream(),
            expected_datasets=1,
        )
        print(f"Harvest status: {harvest.status}")


asyncio.run(main())
```

## Configuration Options

| Option | Type | Required | Default | Description |
| ------ | ---- | -------- | ------- | ----------- |
| `log_level` | string | No | INFO | Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL) |
| `api_url` | string | Yes | - | Base URL of the Middleware API |
| `client_cert_path` | string | No | null | Path to client certificate (PEM format) |
| `client_key_path` | string | No | null | Path to client private key (PEM format) |
| `ca_cert_path` | string | No | null | Path to CA certificate for server verification |
| `timeout` | float | No | 30.0 | Request timeout in seconds |
| `verify_ssl` | bool | No | true | Enable SSL certificate verification |
| `max_concurrency` | int | No | 10 | Maximum concurrent API requests (also default for `harvest_arcs`) |

## API Methods

### `create_or_update_arc(rdi: str, arc: ARC | dict | str) -> ArcResult`

Create or update one ARC in the Middleware API.

**Parameters:**

- `rdi` (str): The RDI identifier (e.g., "edaphobase").
- `arc` (ARC | dict | str): ARC object from arctrl, pre-serialised RO-Crate dict, or JSON string.

**Returns:**

- `ArcResult`: Contains the result of the operation.

**Raises:**

- `ApiClientError`: If the request fails due to HTTP errors, network issues, or invalid JSON.

**Example:**

```python
from arctrl import ARC, ArcInvestigation

inv = ArcInvestigation.create(identifier="my-arc-001", title="My ARC")
arc = ARC.from_arc_investigation(inv)

response = await client.create_or_update_arc(
    rdi="edaphobase",
    arc=arc,  # Can also be dict or JSON string
)
```

### `harvest_arcs(rdi: str, arcs: AsyncIterator[ARC | dict | str], expected_datasets: int | None = None) -> HarvestResult`

Convenience workflow to create a harvest, upload all ARCs from an async iterator, and complete the harvest.

- Uses `config.max_concurrency` by default.
- Continues on item-level submission errors and skips failed items.
- Cancels the harvest only for catastrophic errors.
- Supports ARC objects, pre-serialised RO-Crate dicts, and JSON strings.

All errors are raised as `ApiClientError` exceptions:

```python
from middleware.api_client import ApiClientError

try:
    response = await client.create_or_update_arc(
        rdi="my-rdi",
        arc=arc,  # Can be ARC object, dict, or JSON string
    )
except ApiClientError as e:
    print(f"API Error: {e}")
