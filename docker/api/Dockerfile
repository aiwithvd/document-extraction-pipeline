FROM python:3.11-slim AS base

# Install system dependencies for OCR and file type detection
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    poppler-utils \
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

RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

COPY docker/api/entrypoint.sh /entrypoint.sh
CMD ["/bin/sh", "/entrypoint.sh"]
