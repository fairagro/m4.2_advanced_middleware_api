# ---- Build Stage ----
FROM python:3.12.12-alpine3.22 AS builder

# Installiere Build-Tools für native Builds
RUN apk add --no-cache \
    build-base=0.5-r3 \
    python3-dev=3.12.12-r0 \
    libffi-dev=3.4.8-r0 \
    openssl-dev=3.5.4-r0 \
    cargo=1.87.0-r0

WORKDIR /middleware_api

COPY . /middleware_api

# Upgrade pip und installiere Abhängigkeiten
RUN pip install --no-cache-dir --upgrade pip==25.2 uv==0.9.2
RUN uv sync --no-dev
RUN uv pip install pyinstaller
RUN . /middleware_api/.venv/bin/activate && \
        PYTHONPATH=/middleware_api/middleware_api \
        pyinstaller --onefile middleware_api/main.py --name middleware_api


# # ---- Runtime Stage ----
FROM alpine:3.22.2

WORKDIR /middleware_api

ENV UVICORN_HOST=0.0.0.0
ENV UVICORN_PORT=8000

COPY --from=builder /middleware_api/dist/middleware_api .

# Create non-root user and group and fix permissions
RUN apk add --no-cache curl=8.14.1-r2 \
    && addgroup -S middleware && adduser -S middleware -G middleware \
    && chown -R middleware:middleware /middleware_api

USER middleware

EXPOSE $UVICORN_PORT

ENTRYPOINT ["/middleware_api/middleware_api"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD ["curl", "-f", "http://${UVICORN_HOST}:${UVICORN_PORT}/v1/liveness"]
