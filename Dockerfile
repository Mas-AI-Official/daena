# Use Python 3.10 as base image for better compatibility
FROM python:3.10-slim

# Metadata
LABEL maintainer="MAS-AI Technologies Inc."
LABEL description="Daena AI VP System - Production Image"
LABEL version="2.0.0"

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

# Set working directory
WORKDIR /app

# Install system dependencies (including curl for health checks)
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Optional: Install JAX for TPU support (can be enabled via build arg)
ARG ENABLE_TPU=false
RUN if [ "$ENABLE_TPU" = "true" ]; then \
        pip install --no-cache-dir jax jaxlib jax[tpu]; \
    fi

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p logs/traces \
    && mkdir -p data/cache \
    && mkdir -p data/metrics \
    && mkdir -p logs \
    && mkdir -p cache \
    && mkdir -p uploads

# Set up environment
ENV REDIS_HOST=redis \
    REDIS_PORT=6379 \
    MONGO_HOST=mongodb \
    MONGO_PORT=27017 \
    COMPUTE_PREFER=${COMPUTE_PREFER:-auto} \
    COMPUTE_ALLOW_TPU=${COMPUTE_ALLOW_TPU:-true} \
    COMPUTE_TPU_BATCH_FACTOR=${COMPUTE_TPU_BATCH_FACTOR:-128} \
    DAENA_REALTIME_METRICS_ENABLED=true \
    DAENA_TRACING_ENABLED=${DAENA_TRACING_ENABLED:-false}

# Expose ports
EXPOSE 8000 8001 8002

# Create necessary directories for governance artifacts
RUN mkdir -p Governance/artifacts

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

# Health check (curl already installed above as system dependency)
HEALTHCHECK --interval=30s --timeout=30s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health/ || exit 1

# Start the application using uvicorn for production
# Note: Use 1 worker for now to avoid multiprocessing issues
CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"] 