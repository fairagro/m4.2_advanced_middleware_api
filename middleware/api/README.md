# FAIRagro Advanced Middleware API

This is the main REST API for the FAIRagro Advanced Middleware system.

## Overview

The API provides endpoints for:

- **ARC Management**: Create, update, and manage ARC (Annotated Research Context) objects
- **Data Conversion**: Convert data from various sources (SQL, INSPIRE metadata) into ARC format
- **GitLab Integration**: Synchronize ARC objects with GitLab repositories

## Architecture

The API is built with:

- **FastAPI**: Modern, high-performance web framework
- **Uvicorn**: ASGI server for running the application
- **arctrl**: Python library for working with ARC objects
- **python-gitlab**: GitLab API integration

## Dependencies

The API depends on:

- `shared`: Shared utilities and configuration
- `arctrl`: ARC object manipulation
- `fastapi`: Web framework
- `uvicorn`: ASGI server
- `python-gitlab`: GitLab integration
- `pyyaml`: Configuration parsing
- `cryptography`: Security and encryption

## Development

Install dependencies:

```bash
uv sync --package api
```

Run tests:

```bash
uv run pytest middleware/api/tests
```

Run the API locally:

```bash
uv run uvicorn middleware.api.main:app --reload
```

## Deployment

The API is containerized using Docker and can be built as a standalone binary with PyInstaller for minimal runtime dependencies.

See `docker/Dockerfile.api` for the build configuration.
