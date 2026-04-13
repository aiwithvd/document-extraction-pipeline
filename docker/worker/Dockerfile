FROM python:3.11-slim AS base

# Install system dependencies for MinerU and file type detection
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    libmagic1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user
RUN useradd -m -u 1000 appuser

WORKDIR /app

# Install Python dependencies (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .

# Create model directory and set ownership
RUN mkdir -p /app/models/mineru
RUN chown -R appuser:appuser /app

COPY docker/worker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

USER appuser

# Uncomment for GPU workers (requires NVIDIA Container Toolkit):
# LABEL com.nvidia.volumes.needed="nvidia_driver"

CMD ["/entrypoint.sh"]
