"""Tenant-scoped Upstash / Redis pub/sub helpers for SSE."""

from __future__ import annotations

import json

from app.config import settings

_redis_client = None


def alert_channel(tenant_id: str) -> str:
    return f"bastionfed:tenant:{tenant_id}:alerts"


def fl_channel(tenant_id: str) -> str:
    return f"bastionfed:tenant:{tenant_id}:fl"


async def get_async_redis():
    global _redis_client
    if _redis_client is None and settings.redis_enabled:
        import redis.asyncio as redis_async

        _redis_client = redis_async.from_url(
            settings.redis_url or "",
            decode_responses=True,
        )
    return _redis_client


async def close_redis() -> None:
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None


async def publish_alert(tenant_id: str, payload: dict) -> None:
    r = await get_async_redis()
    if not r:
        return
    await r.publish(alert_channel(tenant_id), json.dumps(payload))


async def publish_fl(tenant_id: str, payload: dict) -> None:
    r = await get_async_redis()
    if not r:
        return
    await r.publish(fl_channel(tenant_id), json.dumps(payload))
