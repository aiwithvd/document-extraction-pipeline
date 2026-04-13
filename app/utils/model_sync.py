"""
MinIO-backed model sync utilities for MinerU model weights.

Models are stored as objects in a dedicated MinIO bucket (MINERU_MODELS_BUCKET).
At worker startup, ensure_models() pulls them to the local filesystem path
(MINERU_MODELS_DIR) if not already present. The first-time population of the
bucket is done by scripts/init_mineru_models.py.
"""

import logging
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.core.config import settings

logger = logging.getLogger(__name__)


def _make_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=f"{'https' if settings.MINIO_USE_SSL else 'http'}://{settings.MINIO_ENDPOINT}",
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


def push_models_to_minio(local_dir: str, bucket: str) -> int:
    """Upload all files under local_dir to bucket, preserving relative paths as keys.

    Returns the count of files uploaded.
    """
    client = _make_s3_client()
    root = Path(local_dir)
    count = 0
    for file_path in sorted(root.rglob("*")):
        if not file_path.is_file():
            continue
        object_key = str(file_path.relative_to(root))
        logger.info("Uploading model file: %s", object_key)
        client.upload_file(str(file_path), bucket, object_key)
        count += 1
    logger.info("Pushed %d model files to s3://%s", count, bucket)
    return count


def pull_models_from_minio(bucket: str, local_dir: str) -> int:
    """Download all objects in bucket to local_dir, recreating the key structure.

    Uses the S3 paginator to handle buckets with more than 1000 objects.
    Uses download_file (multipart streaming) — never loads model files into RAM.
    Returns the count of files downloaded.
    """
    client = _make_s3_client()
    root = Path(local_dir)
    paginator = client.get_paginator("list_objects_v2")
    count = 0
    for page in paginator.paginate(Bucket=bucket):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            dest = root / key
            dest.parent.mkdir(parents=True, exist_ok=True)
            logger.info("Downloading model file: %s", key)
            client.download_file(bucket, key, str(dest))
            count += 1
    logger.info("Pulled %d model files from s3://%s", count, bucket)
    return count


def ensure_models(local_dir: str, bucket: str) -> None:
    """Ensure MinerU models are present at local_dir.

    If the directory is empty or missing, models are pulled from the MinIO
    bucket. Raises RuntimeError if the bucket is also empty — that means
    scripts/init_mineru_models.py has not been run yet.
    """
    root = Path(local_dir)
    root.mkdir(parents=True, exist_ok=True)

    has_local = any(root.rglob("*"))
    if has_local:
        logger.info("MinerU models already present at %s, skipping sync", local_dir)
        return

    logger.info(
        "No local models found at %s — pulling from MinIO bucket '%s'",
        local_dir,
        bucket,
    )
    try:
        count = pull_models_from_minio(bucket, local_dir)
    except ClientError as exc:
        raise RuntimeError(
            f"Failed to pull MinerU models from MinIO bucket '{bucket}': {exc}"
        ) from exc

    if count == 0:
        raise RuntimeError(
            f"MinIO bucket '{bucket}' is empty. "
            "Run scripts/init_mineru_models.py first to download and push model weights."
        )

    logger.info("Model sync complete: %d files pulled to %s", count, local_dir)
