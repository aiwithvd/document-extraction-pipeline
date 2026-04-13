#!/usr/bin/env python3
"""
One-time bootstrap: download MinerU model weights from HuggingFace and push to MinIO.

Run this script once before the first deployment (or after wiping the MinIO bucket).
Subsequently, the worker will pull models from MinIO on startup via ensure_models().

Usage:
    python scripts/init_mineru_models.py
    python scripts/init_mineru_models.py --local-dir /tmp/mineru_models --bucket mineru-models

Prerequisites:
    - MinIO must be running and accessible
    - MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY must be set (via .env or env vars)
    - mineru[all] must be installed in the current Python environment
    - HuggingFace network access required for the initial download

Note:
    The mineru_models Docker volume persists between container restarts — only run
    this script again if the volume is wiped or the bucket is empty.
"""

import argparse
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

# Allow running from the project root without installing the package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def _write_temp_config(local_dir: str) -> None:
    """Write ~/magic-pdf.json pointing at local_dir for the download step."""
    config = {
        "models-dir": local_dir,
        "device-mode": "cpu",  # CPU is sufficient for the download-only step
        "layout-config": {"model": "doclayout_yolo"},
    }
    config_path = Path.home() / "magic-pdf.json"
    config_path.write_text(json.dumps(config, indent=2))
    logger.info("Wrote temporary MinerU config: %s", config_path)


def download_models(local_dir: str) -> None:
    """Download MinerU model weights to local_dir.

    Tries the standard `mineru-models-download` CLI entry point first.
    Falls back to triggering download implicitly via a no-op parse if the
    dedicated command is not available (version-dependent behaviour).
    """
    Path(local_dir).mkdir(parents=True, exist_ok=True)
    _write_temp_config(local_dir)

    logger.info("Downloading MinerU models to %s ...", local_dir)

    # Try the dedicated download command (available in most MinerU releases)
    result = subprocess.run(
        ["mineru-models-download", "--model-dir", local_dir],
        capture_output=False,
    )
    if result.returncode == 0:
        logger.info("Model download complete via mineru-models-download")
        return

    # Fallback: some versions expose download via magic-pdf CLI
    logger.warning(
        "mineru-models-download returned %d — trying magic-pdf fallback",
        result.returncode,
    )
    result = subprocess.run(
        ["magic-pdf", "download-models", "--model-dir", local_dir],
        capture_output=False,
    )
    if result.returncode == 0:
        logger.info("Model download complete via magic-pdf")
        return

    # Last resort: trigger implicit download by importing the model module
    logger.warning(
        "magic-pdf fallback returned %d — triggering implicit model init",
        result.returncode,
    )
    try:
        from magic_pdf.model.doc_analyze_by_custom_model import doc_analyze  # noqa: F401

        logger.info("Model import triggered — check %s for downloaded files", local_dir)
    except Exception as exc:
        logger.error("All download methods failed: %s", exc)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download MinerU models and push to MinIO"
    )
    parser.add_argument(
        "--local-dir",
        default="/tmp/mineru_models",
        help="Local path to download models into (default: /tmp/mineru_models)",
    )
    parser.add_argument(
        "--bucket",
        default=None,
        help="Override MinIO bucket name (default: MINERU_MODELS_BUCKET setting)",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Skip HuggingFace download; push existing files in --local-dir to MinIO",
    )
    args = parser.parse_args()

    from app.core.config import settings
    from app.utils.model_sync import push_models_to_minio

    bucket = args.bucket or settings.MINERU_MODELS_BUCKET

    if not args.skip_download:
        download_models(args.local_dir)
    else:
        logger.info("Skipping download — using existing files in %s", args.local_dir)

    # Verify there are files to push
    local_files = list(Path(args.local_dir).rglob("*"))
    file_count = sum(1 for f in local_files if f.is_file())
    if file_count == 0:
        logger.error(
            "No files found in %s — download may have failed or wrong path",
            args.local_dir,
        )
        sys.exit(1)

    logger.info("Uploading %d model files to MinIO bucket '%s' ...", file_count, bucket)
    pushed = push_models_to_minio(args.local_dir, bucket)
    logger.info("Done. Pushed %d files to s3://%s", pushed, bucket)
    logger.info(
        "Workers will pull models from '%s' automatically on next startup.", bucket
    )


if __name__ == "__main__":
    main()
