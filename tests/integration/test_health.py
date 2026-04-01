from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_returns_200(client: AsyncClient):
    with patch("app.api.routes.health.AsyncSessionLocal") as mock_db_cls, \
         patch("app.api.routes.health.check_redis_connectivity", new_callable=AsyncMock) as mock_redis, \
         patch("app.api.routes.health.storage_client") as mock_storage:

        # Set up async context manager for DB
        mock_conn = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=None)
        mock_conn.execute = AsyncMock()
        mock_db_cls.return_value = mock_conn

        mock_redis.return_value = True
        mock_storage.check_connectivity = AsyncMock(return_value=True)

        response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["checks"]["redis"] == "ok"
    assert data["checks"]["storage"] == "ok"


@pytest.mark.asyncio
async def test_health_returns_503_when_redis_down(client: AsyncClient):
    with patch("app.api.routes.health.AsyncSessionLocal") as mock_db_cls, \
         patch("app.api.routes.health.check_redis_connectivity", new_callable=AsyncMock) as mock_redis, \
         patch("app.api.routes.health.storage_client") as mock_storage:

        mock_conn = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=None)
        mock_conn.execute = AsyncMock()
        mock_db_cls.return_value = mock_conn

        mock_redis.return_value = False
        mock_storage.check_connectivity = AsyncMock(return_value=True)

        response = await client.get("/health")

    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "degraded"
