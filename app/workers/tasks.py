import asyncio
import uuid
from datetime import datetime, timezone

import structlog
from celery.exceptions import MaxRetriesExceededError
from sqlalchemy import select

from app.core.celery_app import celery_app
from app.core.logging import configure_logging
from app.core.storage import StorageClient
from app.models.job import Job
from app.services.llm_service import LLMExtractionService
from app.services.mineru_service import mineru_service
from app.utils.exceptions import DocumentExtractionError
from app.utils.text_processing import clean_markdown
from app.workers.sync_db import get_sync_db

configure_logging()
logger = structlog.get_logger(__name__)


def _get_job(db, job_id: uuid.UUID) -> Job | None:
    return db.execute(select(Job).where(Job.id == job_id)).scalar_one_or_none()


@celery_app.task(
    bind=True,
    name="app.workers.tasks.process_document",
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
    reject_on_worker_lost=True,
)
def process_document(self, job_id: str, storage_key: str, document_type: str) -> dict:
    """Full document extraction pipeline: download → MinerU → LLM → save result."""
    _job_id = uuid.UUID(job_id)
    log = logger.bind(job_id=job_id, document_type=document_type)
    log.info("Starting document processing")

    try:
        # Step 1: mark as processing
        with get_sync_db() as db:
            job = _get_job(db, _job_id)
            if job is None:
                log.error("Job not found")
                return {"status": "failed", "error": "job not found"}

            # Idempotency guard
            if job.status == "completed":
                log.info("Job already completed, skipping")
                return {"status": "completed"}

            job.status = "processing"
            job.processing_started_at = datetime.now(timezone.utc)
            job.celery_task_id = self.request.id

        # Step 2: download file
        log.info("Downloading file from storage")
        storage = StorageClient()
        file_bytes: bytes = asyncio.run(storage.download_file(storage_key))

        # Step 3: MinerU extraction
        log.info("Running MinerU extraction")
        with get_sync_db() as db:
            job = _get_job(db, _job_id)
            mime_type = job.mime_type if job else "application/pdf"

        raw_text: str = asyncio.run(mineru_service.extract_text(file_bytes, mime_type))
        cleaned_text = clean_markdown(raw_text)
        log.info("MinerU extraction complete", text_length=len(cleaned_text))

        # Step 4: save OCR text
        with get_sync_db() as db:
            job = _get_job(db, _job_id)
            if job:
                job.ocr_text = cleaned_text[:50000]  # cap stored OCR text

        # Step 5: LLM extraction
        log.info("Running LLM extraction")
        llm = LLMExtractionService()
        result_dict, confidence = asyncio.run(llm.extract(cleaned_text, document_type))
        log.info("LLM extraction complete", confidence=confidence)

        # Step 6: save result
        with get_sync_db() as db:
            job = _get_job(db, _job_id)
            if job:
                job.status = "completed"
                job.result = result_dict
                job.confidence_score = confidence
                job.processing_completed_at = datetime.now(timezone.utc)

        log.info("Job completed successfully")
        return {"status": "completed", "confidence": confidence}

    except DocumentExtractionError as exc:
        log.error("Extraction error", error=str(exc))
        _mark_failed(_job_id, str(exc))
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            log.error("Max retries exceeded, marking job as failed")
            _mark_failed(_job_id, f"Max retries exceeded: {exc}")
            return {"status": "failed", "error": str(exc)}

    except Exception as exc:
        log.exception("Unexpected error during processing")
        _mark_failed(_job_id, str(exc))
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            _mark_failed(_job_id, f"Max retries exceeded: {exc}")
            return {"status": "failed", "error": str(exc)}


def _mark_failed(job_id: uuid.UUID, error_message: str) -> None:
    try:
        with get_sync_db() as db:
            job = _get_job(db, job_id)
            if job:
                job.status = "failed"
                job.error_message = error_message[:2000]
                job.processing_completed_at = datetime.now(timezone.utc)
    except Exception:
        pass  # Don't raise from error handler
