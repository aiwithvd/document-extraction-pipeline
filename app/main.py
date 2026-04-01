from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app import __version__
from app.api.routes import auth, documents, health
from app.core.config import settings
from app.core.logging import CorrelationIdMiddleware, configure_logging
from app.core.redis_client import close_redis, init_redis

configure_logging()
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Starting up", version=__version__, environment=settings.ENVIRONMENT)
    await init_redis()
    logger.info("Redis pool initialised")
    yield
    await close_redis()
    logger.info("Shutting down")


limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[f"{settings.RATE_LIMIT_PER_MINUTE}/minute"],
)

app = FastAPI(
    title="Document Extraction Pipeline",
    description="Extract structured data from invoices, legal documents, and ESG reports.",
    version=__version__,
    lifespan=lifespan,
    openapi_tags=[
        {"name": "auth", "description": "Authentication endpoints"},
        {"name": "documents", "description": "Document upload and extraction results"},
        {"name": "health", "description": "Service health checks"},
    ],
)

# ── Middleware ─────────────────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.ENVIRONMENT == "development" else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ────────────────────────────────────────────────────────────────────
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(documents.router, prefix="/documents", tags=["documents"])
app.include_router(health.router, prefix="/health", tags=["health"])


# ── Global exception handler ───────────────────────────────────────────────────
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception", path=request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected error occurred. Please try again later."},
    )
