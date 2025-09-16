# ---- Build Stage ----
# python:3.12-alpine3.22
FROM python@sha256:02a73ead8397e904cea6d17e18516f1df3590e05dc8823bd5b1c7f849227d272 AS builder

# Installiere Build-Tools für native Builds
RUN apk add --no-cache \
    build-base=0.5-r3 \
    python3-dev=3.12.11-r0 \
    libffi-dev=3.4.8-r0 \
    openssl-dev=3.5.2-r0 \
    cargo=1.87.0-r0

WORKDIR /middleware_api

COPY . /middleware_api

# Upgrade pip und installiere Abhängigkeiten
RUN pip install --no-cache-dir --upgrade pip==25.2 uv==0.8.17 \
    && uv sync --no-dev \
    && uv pip install pyinstaller \
    && . /middleware_api/.venv/bin/activate \
    && PYTHONPATH=/middleware_api/middleware_api \
       pyinstaller --onefile middleware_api/main.py --name middleware_api


# # ---- Runtime Stage ----
# alpine:3.22.1
FROM alpine@sha256:4bcff63911fcb4448bd4fdacec207030997caf25e9bea4045fa6c8c44de311d1

WORKDIR /middleware_api

ENV UVICORN_HOST=0.0.0.0
ENV UVICORN_PORT=8000
ENV MIDDLEWARE_API_CONFIG=/middleware_api/demo_config.yaml

COPY --from=builder /middleware_api/dist/middleware_api .
COPY config.yaml $MIDDLEWARE_API_CONFIG

# Create non-root user and group and fix permissions
RUN apk add --no-cache curl=8.14.1-r1 \
    && addgroup -S middleware && adduser -S middleware -G middleware \
    && chown -R middleware:middleware /middleware_api

USER middleware

EXPOSE $UVICORN_PORT

ENTRYPOINT ["/middleware_api/middleware_api"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD sh -c "curl -f http://${UVICORN_HOST}:${UVICORN_PORT}/v1/liveness || exit 1"