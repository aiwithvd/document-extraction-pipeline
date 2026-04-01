import uuid
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Request, UploadFile, status
from fastapi.params import File, Form

from app.api.deps import CurrentUser, DBSession, Pagination
from app.core.storage import storage_client
from app.schemas.job import DocumentType, JobResponse, JobResultResponse
from app.services.job_service import create_job, get_job, list_user_jobs
from app.utils.exceptions import JobNotFoundError
from app.utils.validators import generate_storage_key, validate_file_size, validate_file_type

router = APIRouter()
logger = structlog.get_logger(__name__)


@router.post(
    "/upload",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a document for extraction",
)
async def upload_document(
    request: Request,
    current_user: CurrentUser,
    db: DBSession,
    file: UploadFile = File(..., description="PDF or image file (max 10 MB)"),
    document_type: DocumentType = Form(..., description="Type of document: invoice, legal, esg"),
) -> Any:
    log = logger.bind(user_id=str(current_user.id), document_type=document_type)

    # Read file content
    file_bytes = await file.read()

    # Validate size
    validate_file_size(len(file_bytes))

    # Validate MIME type via magic bytes
    mime_type = validate_file_type(file_bytes, file.filename or "upload")

    # Generate a secure, unique storage key
    original_name = file.filename or "upload"
    storage_key = generate_storage_key(current_user.id, original_name)

    # Upload to MinIO
    try:
        await storage_client.upload_file(file_bytes, storage_key, mime_type)
    except Exception as exc:
        log.error("File upload failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="File storage failed. Please try again.",
        )

    # Create job record
    job = await create_job(
        db=db,
        user_id=current_user.id,
        document_type=document_type.value,
        original_filename=original_name,
        storage_key=storage_key,
        file_size_bytes=len(file_bytes),
        mime_type=mime_type,
    )

    # Dispatch Celery task
    from app.workers.tasks import process_document

    task = process_document.delay(str(job.id), storage_key, document_type.value)
    job.celery_task_id = task.id

    log.info("Job created and queued", job_id=str(job.id), task_id=task.id)
    return job


@router.get(
    "/result/{job_id}",
    response_model=JobResultResponse,
    summary="Get extraction result for a job",
)
async def get_result(
    job_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> Any:
    try:
        job = await get_job(db, job_id, current_user.id)
    except JobNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )
    return job


@router.get(
    "/jobs",
    response_model=list[JobResponse],
    summary="List all jobs for the current user",
)
async def list_jobs(
    current_user: CurrentUser,
    db: DBSession,
    pagination: Pagination,
) -> Any:
    skip, limit = pagination
    return await list_user_jobs(db, current_user.id, skip=skip, limit=limit)
