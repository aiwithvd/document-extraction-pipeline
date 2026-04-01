from collections.abc import AsyncGenerator

import redis.asyncio as aioredis

from app.core.config import settings

_redis_pool: aioredis.Redis | None = None


async def init_redis() -> None:
    global _redis_pool
    _redis_pool = aioredis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
        max_connections=20,
    )


async def close_redis() -> None:
    global _redis_pool
    if _redis_pool:
        await _redis_pool.aclose()
        _redis_pool = None


def get_redis_pool() -> aioredis.Redis:
    if _redis_pool is None:
        raise RuntimeError("Redis pool is not initialised. Call init_redis() first.")
    return _redis_pool


async def get_redis() -> AsyncGenerator[aioredis.Redis, None]:
    yield get_redis_pool()


async def check_redis_connectivity() -> bool:
    try:
        pool = get_redis_pool()
        return await pool.ping()
    except Exception:
        return False
