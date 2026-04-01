import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_upload_requires_auth(client: AsyncClient, sample_pdf_bytes: bytes):
    response = await client.post(
        "/documents/upload",
        files={"file": ("invoice.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")},
        data={"document_type": "invoice"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_upload_pdf_returns_job_id(
    client: AsyncClient,
    auth_headers: dict,
    sample_pdf_bytes: bytes,
):
    with patch("app.api.routes.documents.storage_client") as mock_storage, \
         patch("app.api.routes.documents.validate_file_type", return_value="application/pdf"), \
         patch("app.workers.tasks.process_document") as mock_task:
        mock_storage.upload_file = AsyncMock(return_value="uploads/test/key.pdf")
        mock_task.delay.return_value = MagicMock(id="celery-task-id")

        response = await client.post(
            "/documents/upload",
            files={"file": ("invoice.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")},
            data={"document_type": "invoice"},
            headers=auth_headers,
        )

    assert response.status_code == 202
    data = response.json()
    assert "id" in data
    assert data["status"] == "pending"
    assert data["document_type"] == "invoice"


@pytest.mark.asyncio
async def test_upload_invalid_document_type(
    client: AsyncClient,
    auth_headers: dict,
    sample_pdf_bytes: bytes,
):
    response = await client.post(
        "/documents/upload",
        files={"file": ("doc.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")},
        data={"document_type": "unknown_type"},
        headers=auth_headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_upload_file_too_large(client: AsyncClient, auth_headers: dict):
    big_file = b"x" * (11 * 1024 * 1024)  # 11 MB
    with patch("app.api.routes.documents.validate_file_type", return_value="application/pdf"):
        response = await client.post(
            "/documents/upload",
            files={"file": ("big.pdf", io.BytesIO(big_file), "application/pdf")},
            data={"document_type": "invoice"},
            headers=auth_headers,
        )
    assert response.status_code == 413
