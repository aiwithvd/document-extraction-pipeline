#!/bin/sh
set -e

echo "Syncing MinerU models from MinIO..."
python -c "
from app.utils.model_sync import ensure_models
from app.core.config import settings
ensure_models(settings.MINERU_MODELS_DIR, settings.MINERU_MODELS_BUCKET)
print('Models ready.')
"

echo "Starting Celery worker..."
exec celery -A app.core.celery_app worker \
    --loglevel=info \
    --queues=extraction \
    --concurrency=2
