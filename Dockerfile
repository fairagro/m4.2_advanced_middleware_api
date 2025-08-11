# ---- Build Stage ----
FROM python:3.12-alpine AS builder

# Installiere Build-Tools für native Builds
RUN apk add --no-cache \
    build-base \
    python3-dev \
    libffi-dev \
    openssl-dev \
    cargo

WORKDIR /middleware_api

COPY . /middleware_api

# Upgrade pip und installiere Abhängigkeiten
RUN pip install --upgrade pip uv \
    && uv sync --no-dev \
    && uv pip install pyinstaller \
    && source /middleware_api/.venv/bin/activate \
    && PYTHONPATH=/middleware_api/app \
       pyinstaller --onefile app/main.py --name middleware_api


# # ---- Runtime Stage ----
FROM alpine:latest

WORKDIR /middleware_api

COPY --from=builder /middleware_api/dist/middleware_api .

# Create non-root user and group and fix permissions
RUN addgroup -S middleware && adduser -S middleware -G middleware \
    && chown -R middleware:middleware /middleware_api

USER middleware

EXPOSE 8000

ENTRYPOINT ["/middleware_api/middleware_api"]
