class DocumentExtractionError(Exception):
    """Base exception for document extraction errors."""


class OCRError(DocumentExtractionError):
    """Raised when OCR processing fails."""


class LLMExtractionError(DocumentExtractionError):
    """Raised when LLM extraction fails after all retries."""


class SchemaValidationError(DocumentExtractionError):
    """Raised when extracted data does not match the expected schema."""


class StorageError(DocumentExtractionError):
    """Raised when file storage operations fail."""


class JobNotFoundError(DocumentExtractionError):
    """Raised when a job cannot be found or does not belong to the requesting user."""
