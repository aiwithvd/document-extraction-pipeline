import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentType(str, Enum):
    INVOICE = "invoice"
    LEGAL = "legal"
    ESG = "esg"


class JobResponse(BaseModel):
    id: uuid.UUID
    status: JobStatus
    document_type: DocumentType
    original_filename: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JobResultResponse(JobResponse):
    result: dict[str, Any] | None = None
    error_message: str | None = None
    confidence_score: float | None = None
    processing_started_at: datetime | None = None
    processing_completed_at: datetime | None = None
