import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job
from app.utils.exceptions import JobNotFoundError


async def create_job(
    db: AsyncSession,
    user_id: uuid.UUID,
    document_type: str,
    original_filename: str,
    storage_key: str,
    file_size_bytes: int,
    mime_type: str,
) -> Job:
    job = Job(
        user_id=user_id,
        document_type=document_type,
        original_filename=original_filename,
        storage_key=storage_key,
        file_size_bytes=file_size_bytes,
        mime_type=mime_type,
        status="pending",
    )
    db.add(job)
    await db.flush()  # get the generated id before commit
    return job


async def get_job(db: AsyncSession, job_id: uuid.UUID, user_id: uuid.UUID) -> Job:
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.user_id == user_id)
    )
    job = result.scalar_one_or_none()
    if job is None:
        raise JobNotFoundError(f"Job {job_id} not found")
    return job


async def update_job_status(
    db: AsyncSession,
    job_id: uuid.UUID,
    status: str,
    **kwargs: Any,
) -> Job:
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        raise JobNotFoundError(f"Job {job_id} not found")

    job.status = status
    job.updated_at = datetime.now(timezone.utc)
    for key, value in kwargs.items():
        setattr(job, key, value)

    return job


async def list_user_jobs(
    db: AsyncSession,
    user_id: uuid.UUID,
    skip: int = 0,
    limit: int = 20,
) -> list[Job]:
    result = await db.execute(
        select(Job)
        .where(Job.user_id == user_id)
        .order_by(Job.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all())
