import asyncio
import time
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.auth.deps import AuthContext, require_sse_auth
from app.config import settings
from app.sse_bus import alert_channel, fl_channel, get_async_redis

router = APIRouter(tags=["events"])

_KEEPALIVE_EVERY_S = 15.0


async def _keepalive_stream():
    yield ": keep-alive\n\n"
    while True:
        await asyncio.sleep(_KEEPALIVE_EVERY_S)
        yield ": keep-alive\n\n"


async def _redis_stream(channel_name: str):
    r = await get_async_redis()
    if not r:
        async for chunk in _keepalive_stream():
            yield chunk
        return
    pubsub = r.pubsub()
    await pubsub.subscribe(channel_name)
    ping_accum = 0.0
    last_ping = time.monotonic()
    try:
        yield ": keep-alive\n\n"
        while True:
            msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            now = time.monotonic()
            ping_accum += now - last_ping
            last_ping = now
            if msg and msg.get("type") == "message" and msg.get("data"):
                yield f"data: {msg['data']}\n\n"
            if ping_accum >= _KEEPALIVE_EVERY_S:
                yield ": keep-alive\n\n"
                ping_accum = 0.0
    finally:
        await pubsub.unsubscribe(channel_name)
        await pubsub.close()


@router.get("/fl-events")
async def fl_event_stream(auth: Annotated[AuthContext, Depends(require_sse_auth)]):
    if settings.redis_enabled and auth.tenant_id:
        return StreamingResponse(_redis_stream(fl_channel(auth.tenant_id)), media_type="text/event-stream")
    return StreamingResponse(_keepalive_stream(), media_type="text/event-stream")


@router.get("/events")
async def alert_event_stream(auth: Annotated[AuthContext, Depends(require_sse_auth)]):
    if settings.redis_enabled and auth.tenant_id:
        return StreamingResponse(_redis_stream(alert_channel(auth.tenant_id)), media_type="text/event-stream")
    return StreamingResponse(_keepalive_stream(), media_type="text/event-stream")
