import re
import uuid
from datetime import date
from pathlib import Path

import magic
from fastapi import HTTPException, status

from app.core.config import settings

_ALLOWED_MIME_TYPES = set(settings.ALLOWED_MIME_TYPES)


def validate_file_type(file_bytes: bytes, filename: str) -> str:
    """Detect MIME type from actual file bytes (not extension) and validate."""
    detected = magic.from_buffer(file_bytes, mime=True)
    if detected not in _ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type '{detected}'. Allowed: {sorted(_ALLOWED_MIME_TYPES)}",
        )
    return detected


def validate_file_size(size: int) -> None:
    """Raise HTTP 413 if the file exceeds the configured limit."""
    if size > settings.MAX_FILE_SIZE_BYTES:
        limit_mb = settings.MAX_FILE_SIZE_BYTES / (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds the {limit_mb:.0f} MB limit",
        )


def sanitize_filename(filename: str) -> str:
    """Strip path components, remove unsafe characters, and limit length."""
    # Take only the base name (no directory traversal)
    name = Path(filename).name
    # Replace anything that is not alphanumeric, dot, hyphen, or underscore
    name = re.sub(r"[^\w.\-]", "_", name)
    # Collapse multiple underscores / dots
    name = re.sub(r"_+", "_", name)
    # Limit to 200 chars to stay well within filesystem limits
    return name[:200] or "upload"


def generate_storage_key(user_id: uuid.UUID, filename: str) -> str:
    """Return a unique, user-scoped object key for MinIO."""
    today = date.today().isoformat()
    safe_name = sanitize_filename(filename)
    unique = uuid.uuid4().hex[:8]
    return f"uploads/{user_id}/{today}/{unique}_{safe_name}"
