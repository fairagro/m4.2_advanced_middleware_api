---
name: config-wrapper
description: >
  Reference for the ConfigWrapper / ConfigBase pattern from middleware.shared.
  Use when adding config fields, reading config values, overriding via
  environment variables or Docker secrets, or extending ConfigBase in a new
  component. ConfigWrapper is the single source of truth for all configuration.
compatibility: Python 3.12+, pydantic v2, middleware.shared
---

# ConfigWrapper — Usage Reference

`ConfigWrapper` (from `middleware.shared.config`) wraps a YAML file and adds
environment variable and Docker secret overrides. A component's `Config` class
extends `ConfigBase` and is populated via `Config.from_config_wrapper(wrapper)`.

---

## Loading Configuration

```python
from middleware.shared.config.config_wrapper import ConfigWrapper
from mycomponent.config import Config  # extends ConfigBase

wrapper = ConfigWrapper.from_yaml_file(path, prefix="MY_PREFIX")
config = Config.from_config_wrapper(wrapper)
```

---

## Override Resolution Order

For every config field, the wrapper resolves values in this order:

1. **Environment variable**: `{PREFIX}_{FIELD_PATH}` (uppercase, `_` as separator)
2. **Docker secret file**: `/run/secrets/{prefix}_{field_path}` (lowercase)
3. **YAML file value**
4. **Pydantic field default**

Nested fields use `_` as path separator:

- `api_client.api_url` with prefix `MY_APP` → `MY_APP_API_CLIENT_API_URL`

---

## Type Coercion (env / secret values are always strings)

| String value | Parsed as |
| --- | --- |
| `"true"` / `"True"` / `"TRUE"` | `True` (bool) |
| `"false"` / `"False"` / `"FALSE"` | `False` (bool) |
| `"123"` | `123` (int) |
| `"3.14"` | `3.14` (float) |
| `""` (empty) | `None` |
| anything else | `str` |

---

## Extending ConfigBase

`ConfigBase` is an optional convenience base class from `middleware.shared`
that bundles config options shared across FAIRagro middleware components. You
can subclass it to inherit those fields, or use plain `pydantic.BaseModel` if
your component doesn't need them.

```python
from typing import Annotated
from pydantic import Field, SecretStr
from middleware.shared.config.config_base import ConfigBase  # optional


class Config(ConfigBase):  # or BaseModel if ConfigBase fields aren't needed
    # Required field (no default)
    connection_string: Annotated[SecretStr, Field(description="DB connection URI")]

    # Optional field with default
    batch_size: Annotated[
        int,
        Field(description="Records to fetch per batch.", ge=1),
    ] = 100
```

---

## ConfigBase vs plain BaseModel

**Use `ConfigBase`** (from `middleware.shared`) only for **top-level component
configs** — i.e., the `Config` class that is loaded from a YAML file via
`ConfigWrapper`. It adds `log_level`, `otel`, and `from_config_wrapper`.

---

## ConfigBase (optional convenience base)

`ConfigBase` from `middleware.shared` is a FAIRagro-specific convenience class.
Use it when your component should share the standard logging and OpenTelemetry
fields; skip it for components that don't need them.

Inherited fields:

```python
log_level: LogLevel = "INFO"  # "DEBUG" | "INFO" | "WARNING" | "ERROR" | "CRITICAL"
otel: OtelConfig  # OpenTelemetry settings
```

`OtelConfig` fields:

- `endpoint: str | None` — OTLP collector URL
- `log_console_spans: bool` — print spans to stdout
- `log_level: LogLevel` — OTLP log export level

---

## Secrets Handling

- `SecretStr` fields: access the value as `.get_secret_value()` only at the
  point of use (e.g., when creating a DB engine). Never pass them to `str()`
  or log them directly.
- Docker secrets: mount files to `/run/secrets/`; the wrapper resolves them
  automatically using the full key name (lowercase).

---

## Typing Rule

All `ConfigBase`/`BaseModel` subclasses **must be fully typed** — `dict[str, Any]`
and bare `Any` fields are forbidden.

When a config field holds a nested config, declare its **concrete Pydantic type**:

```python
# ✗ Wrong — loses schema validation and type safety
config: dict[str, Any]

# ✓ Correct — Pydantic validates at startup; IDE support works
config: Annotated[InspireToArcConfig, Field(description="Inspire plugin configuration")]
```

---

## Defaults Rule

**All defaults belong in the `Config` class — never in application code.**

If application code needs a fallback value (e.g. `sys.maxsize`, a hardcoded
constant, or a magic number), that value belongs as a Pydantic field default
in the relevant `Config` class instead. This makes the default visible,
overridable via env/secret/YAML, and documented.

```python
# ✗ Wrong — default hidden in application code, not overridable
effective_max = config.max_records if config.max_records is not None else sys.maxsize

# ✓ Correct — default declared in Config, code uses it directly
class Config(BaseModel):
    chunk_size: Annotated[int, Field(description="Records per page.", ge=1)] = 10

# in code:
records_iter = csw_client.get_records(chunk_size=config.chunk_size)
```

---

## Testing

In unit tests, instantiate `Config` directly without the wrapper:

```python
config = Config(
    connection_string=SecretStr("postgresql+asyncpg://user:pass@localhost/db"),
    # ... other required fields
)
```

In integration tests, mock at the wrapper boundary:

```python
mocker.patch("mycomponent.main.ConfigWrapper.from_yaml_file")
mocker.patch("mycomponent.main.Config.from_config_wrapper", return_value=mock_config)
```
