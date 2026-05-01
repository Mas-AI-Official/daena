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


# --- Stage 2: Backend + Serve Frontend (Kali Linux) ---
FROM kalilinux/kali-rolling AS production

ARG DAENA_VERSION=2.0.1
ARG BUILD_DATE=unknown
ARG GIT_SHA=unknown

# OCI image labels
LABEL org.opencontainers.image.title="Daena" \
      org.opencontainers.image.description="Power-First AI Operating System" \
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
    DAENA_VERSION=${DAENA_VERSION} \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# System dependencies: Python 3.12, curl, pg libs, Kali tools
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        python3-venv \
        python3-dev \
        curl \
        libpq5 \
        libpq-dev \
        gcc \
        nmap \
        whois \
        dnsutils \
        net-tools \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (cache-friendly: pyproject.toml first)
COPY backend/pyproject.toml backend/README.md ./
COPY backend/app/ ./app/
RUN pip install --no-cache-dir --break-system-packages "."

# Copy remaining backend files (migrations, run.py, etc.)
COPY backend/ ./

# Copy soul vault (Daena's character foundation -- gitignored, built into image)
COPY backend/app/soul/ ./app/soul/

# Copy compiled frontend into backend static directory
COPY --from=frontend-build /frontend/dist /app/static

# Copy production entrypoint (alembic upgrade head -> uvicorn).
# See start.sh at the repo root.
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

# Create non-root user for security
RUN groupadd -r daena && useradd -r -g daena -s /bin/false daena && \
    chown -R daena:daena /app

USER daena

EXPOSE 8000

# Liveness probe: basic /health endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -sf http://localhost:8000/health || exit 1

# Production entrypoint: runs `alembic upgrade head` then exec's uvicorn.
# See /app/start.sh.
ENTRYPOINT ["/app/start.sh"]
