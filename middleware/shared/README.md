# FAIRagro Advanced Middleware - Shared Components

This package contains shared utilities and components used across the FAIRagro Advanced Middleware system.

## Overview

The `shared` package provides:

- **Configuration Management**: Base classes and utilities for configuration handling
- **Common Models**: Pydantic models used across multiple middleware components
- **Utilities**: Helper functions and classes for common operations

## Components

### Configuration (`middleware.shared.config`)

Configuration utilities including:

- `ConfigWrapper`: Base class for configuration management
- Environment variable handling
- Configuration validation with Pydantic

### Models

Shared Pydantic models for data validation and serialization across the middleware.

## Usage

This package is used as a dependency by other middleware components:

- `api`: The main REST API
- `api_client`: Client library for API interaction
- `sql_to_arc`: SQL to ARC conversion
- `inspire_to_arc`: INSPIRE metadata to ARC conversion

## Dependencies

- `pydantic>=2.12.4`: Data validation and settings management

## Development

Install in development mode:

```bash
uv sync --package shared
```

Run tests:

```bash
uv run pytest middleware/shared/tests
```
