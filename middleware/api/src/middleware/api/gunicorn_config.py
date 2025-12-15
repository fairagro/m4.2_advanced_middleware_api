"""Gunicorn configuration for the Middleware API.

This configuration enables multiple worker processes to handle I/O-bound
operations in parallel (waiting on external APIs, database, etc.).
"""

import multiprocessing
import os

# Server Socket
bind = f"{os.getenv('UVICORN_HOST', '127.0.0.1')}:{os.getenv('UVICORN_PORT', '8000')}"

# Worker Processes - auto-detect if GUNICORN_WORKERS=0
_workers_env = int(os.getenv("GUNICORN_WORKERS", "0"))
workers = multiprocessing.cpu_count() * 2 + 1 if _workers_env == 0 else _workers_env
worker_class = "uvicorn.workers.UvicornWorker"

# Worker Connections
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 100

# Timeout
timeout = 120
graceful_timeout = 30
keepalive = 5

# Logging
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process Naming
proc_name = "middleware-api"

# Server Mechanics
daemon = False
pidfile: str | None = None
user: str | None = None
group: str | None = None
tmp_upload_dir: str | None = None

# SSL (if needed in future)
# keyfile = None
# certfile = None
