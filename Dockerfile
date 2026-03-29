# ==============================================================
# Daena V2 Production Dockerfile -- Multi-Stage Build
# ==============================================================
# Stage 1: Build React frontend with Vite
# Stage 2: Python backend with compiled frontend assets
# Result: Single container serving API + SPA on port 8000
#
# Build args:
#   DAENA_VERSION  -- semantic version (default: 2.0.0)
#   BUILD_DATE     -- ISO 8601 timestamp (auto-set in deploy script)
#   GIT_SHA        -- short git commit hash
# ==============================================================

ARG DAENA_VERSION=2.0.1

# --- Stage 1: Frontend Build ---
FROM node:20-alpine AS frontend-build

WORKDIR /frontend

# Install deps first (layer cache optimization)
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund

# Copy source and build
COPY frontend/ ./

# Create a dummy .daena-port so vite.config.ts doesn't warn during build
RUN echo "8000" > /tmp/.daena-port && \
    mkdir -p /frontend/../backend && \
    cp /tmp/.daena-port /frontend/../backend/.daena-port || true

RUN npm run build


# --- Stage 2: Backend + Serve Frontend ---
FROM python:3.12-slim AS production

ARG DAENA_VERSION=2.0.1
ARG BUILD_DATE=unknown
ARG GIT_SHA=unknown

# OCI image labels
LABEL org.opencontainers.image.title="Daena" \
      org.opencontainers.image.description="Governed Multi-Agent LLM Orchestration Platform" \
      org.opencontainers.image.version="${DAENA_VERSION}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.revision="${GIT_SHA}" \
      org.opencontainers.image.vendor="MAS-AI Technologies Inc." \
      org.opencontainers.image.source="https://github.com/mas-ai/daena"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_ENV=production \
    DEBUG=false \
    DAENA_VERSION=${DAENA_VERSION}

WORKDIR /app

# System dependencies (curl for healthcheck, pg libs for asyncpg)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast Python dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install Python dependencies (cache-friendly: pyproject.toml first)
COPY backend/pyproject.toml backend/README.md ./
COPY backend/app/ ./app/
RUN uv pip install --system "."

# Copy remaining backend files (migrations, run.py, etc.)
COPY backend/ ./

# Copy compiled frontend into backend static directory
COPY --from=frontend-build /frontend/dist /app/static

# Create non-root user for security
RUN groupadd -r daena && useradd -r -g daena -s /bin/false daena && \
    chown -R daena:daena /app

USER daena

EXPOSE 8000

# Liveness probe: basic /health endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -sf http://localhost:8000/health || exit 1

# Production: uvicorn with 2 workers, graceful shutdown
# For high-traffic: switch to gunicorn -k uvicorn.workers.UvicornWorker
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "2", \
     "--timeout-keep-alive", "65", \
     "--access-log", \
     "--log-level", "info"]
