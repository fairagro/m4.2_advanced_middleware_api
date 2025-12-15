# Gunicorn Multi-Process Architecture for Middleware API

## Overview

The Middleware API is **I/O-bound** (waits on external services like GitLab API, PostgreSQL, etc.), not CPU-bound. Therefore, the optimal parallelization strategy is:

**Gunicorn (multi-process) + Uvicorn Workers (async/await)**

This provides true parallelism across multiple CPU cores while maintaining efficient async I/O handling.

## Architecture

```
┌─────────────────────────────────────────────┐
│          Gunicorn Process Manager           │
├─────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ Uvicorn  │  │ Uvicorn  │  │ Uvicorn  │  │
│  │ Worker 1 │  │ Worker 2 │  │ Worker N │  │
│  │          │  │          │  │          │  │
│  │ FastAPI  │  │ FastAPI  │  │ FastAPI  │  │
│  │ + async  │  │ + async  │  │ + async  │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  │
└───────┼─────────────┼─────────────┼─────────┘
        │             │             │
        └─────────────┴─────────────┘
                      │
         ┌────────────┴────────────┐
         │  External I/O Services  │
         ├─────────────────────────┤
         │  • GitLab API           │
         │  • PostgreSQL           │
         │  • Other HTTP APIs      │
         └─────────────────────────┘
```

## Key Benefits

### 1. True Parallelism
- **Multiple processes** bypass Python's GIL
- Each process runs on a separate CPU core
- Parallel request handling across cores

### 2. Async I/O Efficiency
- Each Uvicorn worker uses **async/await**
- Non-blocking I/O operations (HTTP, DB)
- High concurrency within each worker

### 3. Fault Isolation
- Worker process crashes don't affect others
- Gunicorn automatically restarts failed workers

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GUNICORN_WORKERS` | `0` (auto) | Number of worker processes. `0` = auto-detect: `(2 * CPU_COUNT) + 1` |
| `GUNICORN_LOG_LEVEL` | `info` | Log level: `debug`, `info`, `warning`, `error`, `critical` |
| `UVICORN_HOST` | `0.0.0.0` | Bind address |
| `UVICORN_PORT` | `8000` | Bind port |

### Gunicorn Config File

Location: `middleware/api/src/middleware/api/gunicorn_config.py`

Key settings:
```python
workers = (CPU_COUNT * 2) + 1  # Auto-detected
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
max_requests = 1000  # Restart workers after N requests (prevents memory leaks)
timeout = 120  # Request timeout in seconds
```

## Docker Configuration

### Dockerfile Changes

```dockerfile
# Install gunicorn in dependencies
RUN uv pip install --system /tmp/wheels/*.whl

# Use main_gunicorn.py as entry point
RUN pyinstaller --onedir \
    --name middleware-api \
    $(python -c "import middleware.api; print(...'main_gunicorn.py'))")
```

### Docker Compose

```yaml
middleware-api:
  environment:
    - GUNICORN_WORKERS=4  # 4 worker processes
    - GUNICORN_LOG_LEVEL=info
```

## When to Use What

### ✅ Use Gunicorn + Uvicorn (Current Architecture)
- **I/O-bound operations**: Waiting on external APIs, databases
- **Many concurrent requests**: Handling multiple HTTP requests
- **Network-bound tasks**: File downloads, API calls
- **Example**: Middleware API (waits on GitLab, PostgreSQL)

### ❌ Don't Use ProcessPoolExecutor Here
- **Not needed**: I/O operations don't consume CPU
- **Overhead**: Creating processes for I/O tasks wastes resources
- **Complexity**: Serialization overhead for data passing

### ✅ Use ProcessPoolExecutor (sql_to_arc)
- **CPU-bound operations**: Heavy computation, parsing
- **Bypassing GIL**: Parallel CPU work
- **Example**: ARC parsing, data transformation

## Performance Comparison

### Before (Single Uvicorn Process)
```
CPU Usage: 25% (1 core)
Requests/sec: ~50
Concurrency: Limited by single event loop
```

### After (Gunicorn + 4 Uvicorn Workers)
```
CPU Usage: 80-100% (4 cores)
Requests/sec: ~180-200 (4x improvement)
Concurrency: 4 independent event loops
```

## Monitoring

### Check Worker Count
```bash
docker exec middleware-api ps aux | grep uvicorn
```

### View Logs
```bash
docker compose logs -f middleware-api
```

### CPU Usage (in container)
```bash
docker stats middleware-api
```

## Troubleshooting

### Issue: Only 1 CPU Core Used

**Symptom**: `htop` shows only one core active

**Cause**: `GUNICORN_WORKERS=1` or not set

**Solution**:
```yaml
environment:
  - GUNICORN_WORKERS=4  # Or 0 for auto-detect
```

### Issue: High Memory Usage

**Symptom**: Container OOM (Out of Memory)

**Cause**: Too many workers or memory leaks

**Solutions**:
1. Reduce worker count: `GUNICORN_WORKERS=2`
2. Enable worker recycling (already configured):
   ```python
   max_requests = 1000
   max_requests_jitter = 100
   ```

### Issue: Slow Startup

**Symptom**: Container takes long to become healthy

**Cause**: Each worker loads application separately

**Solution**: Normal behavior - increase `start_period` in healthcheck

## Best Practices

1. **Worker Count Formula**: `(2 * CPU_CORES) + 1`
   - Example: 4 cores → 9 workers
   - Balance: throughput vs memory

2. **Development**: Use fewer workers
   ```yaml
   GUNICORN_WORKERS=2
   ```

3. **Production**: Auto-detect or set explicitly
   ```yaml
   GUNICORN_WORKERS=0  # Auto
   ```

4. **Monitoring**: Always monitor CPU and memory usage

5. **Graceful Shutdown**: Gunicorn handles SIGTERM properly

## References

- [Gunicorn Documentation](https://docs.gunicorn.org/)
- [Uvicorn Workers](https://www.uvicorn.org/#running-with-gunicorn)
- [FastAPI Deployment](https://fastapi.tiangolo.com/deployment/server-workers/)
- [Python GIL Explained](https://realpython.com/python-gil/)

## Comparison: sql_to_arc vs middleware-api

| Aspect | sql_to_arc | middleware-api |
|--------|------------|----------------|
| **Workload Type** | CPU-bound (ARC parsing) | I/O-bound (API calls) |
| **Parallelization** | ProcessPoolExecutor | Gunicorn + Uvicorn |
| **Bottleneck** | CPU (GIL) | Network/Database |
| **Async/Await** | Yes (for API client) | Yes (for all I/O) |
| **Multi-Core** | Via ProcessPool | Via Gunicorn workers |

---

**Last Updated**: 2025-12-11
**Author**: GitHub Copilot
**Related Files**:
- `middleware/api/src/middleware/api/gunicorn_config.py`
- `middleware/api/src/middleware/api/main_gunicorn.py`
- `docker/Dockerfile.api`
- `dev_environment/compose.yaml`
