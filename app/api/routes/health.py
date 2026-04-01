from typing import Any

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.redis_client import check_redis_connectivity
from app.core.storage import storage_client

router = APIRouter()


@router.get(
    "",
    summary="Health check",
    tags=["health"],
)
async def health_check() -> JSONResponse:
    checks: dict[str, str] = {}
    healthy = True

    # Database check
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {exc}"
        healthy = False

    # Redis check
    try:
        ok = await check_redis_connectivity()
        checks["redis"] = "ok" if ok else "error: ping failed"
        if not ok:
            healthy = False
    except Exception as exc:
        checks["redis"] = f"error: {exc}"
        healthy = False

    # Storage check
    try:
        ok = await storage_client.check_connectivity()
        checks["storage"] = "ok" if ok else "error: bucket unreachable"
        if not ok:
            healthy = False
    except Exception as exc:
        checks["storage"] = f"error: {exc}"
        healthy = False

    http_status = status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(
        status_code=http_status,
        content={"status": "healthy" if healthy else "degraded", "checks": checks},
    )
