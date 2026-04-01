import io
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job
from app.models.user import User


async def _create_job(db: AsyncSession, user: User, status: str = "pending") -> Job:
    job = Job(
        user_id=user.id,
        status=status,
        document_type="invoice",
        original_filename="test.pdf",
        storage_key="uploads/test/test.pdf",
        file_size_bytes=1024,
        mime_type="application/pdf",
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


@pytest.mark.asyncio
async def test_get_result_pending_job(
    client: AsyncClient,
    auth_headers: dict,
    test_user: User,
    db_session: AsyncSession,
):
    job = await _create_job(db_session, test_user, status="pending")
    response = await client.get(f"/documents/result/{job.id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pending"
    assert data["result"] is None


@pytest.mark.asyncio
async def test_get_result_completed_job(
    client: AsyncClient,
    auth_headers: dict,
    test_user: User,
    db_session: AsyncSession,
):
    job = await _create_job(db_session, test_user, status="completed")
    job.result = {"invoice_number": "INV-001", "vendor_name": "Acme", "total_amount": 100.0}
    job.confidence_score = 0.95
    await db_session.commit()

    response = await client.get(f"/documents/result/{job.id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["result"]["invoice_number"] == "INV-001"
    assert data["confidence_score"] == 0.95


@pytest.mark.asyncio
async def test_get_result_not_found(client: AsyncClient, auth_headers: dict):
    random_id = uuid.uuid4()
    response = await client.get(f"/documents/result/{random_id}", headers=auth_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_result_other_user_job(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """A user should not be able to see another user's job."""
    from app.core.security import create_access_token, hash_password
    from datetime import timedelta

    other_user = User(
        id=uuid.uuid4(),
        email="other@example.com",
        hashed_password=hash_password("password123"),
        is_active=True,
    )
    db_session.add(other_user)
    await db_session.commit()

    job = await _create_job(db_session, other_user)

    # Log in as a different user
    own_user = User(
        id=uuid.uuid4(),
        email="owner@example.com",
        hashed_password=hash_password("password123"),
        is_active=True,
    )
    db_session.add(own_user)
    await db_session.commit()

    token = create_access_token({"sub": str(own_user.id)}, expires_delta=timedelta(hours=1))
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get(f"/documents/result/{job.id}", headers=headers)
    assert response.status_code == 404
