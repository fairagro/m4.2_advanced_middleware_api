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

The API is containerized using Docker and is built as a standalone binary with PyInstaller within an Alpine Linux container to provide a minimal, secure runtime environment.

### Scaling & Performance

**Scaling must be done via horizontal replicas (multiple pods/containers) and NOT via internal worker processes.**

The application is bundled using PyInstaller on Python 3.12. Due to known issues with `importlib.metadata` and Pydantic v2's plugin system in "frozen" (PyInstaller) environments, using multiple Uvicorn workers (`--workers > 1`) can lead to startup crashes (e.g., `TypeError: stat: path should be string, bytes, os.PathLike or integer, not NoneType`).

To scale the API:

- In Kubernetes: Increase the `replicaCount` in the Helm chart.
- Locally: Start multiple container instances behind a load balancer.

### Build Configuration

See `docker/Dockerfile.api` for the PyInstaller build configuration. Note that specific package metadata is explicitly included in the build (using `--copy-metadata`) to ensure compatibility with Pydantic and other metadata-sensitive libraries.
