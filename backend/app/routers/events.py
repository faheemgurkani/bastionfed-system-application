import asyncio
import json
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.auth.deps import AuthContext, require_sse_auth
from app.store.memory import state

router = APIRouter(tags=["events"])

_KEEPALIVE_EVERY_S = 15.0
_FL_SSE_TICK_S = 0.25
_ALERT_SSE_TICK_S = 1.0
_ALERT_EVERY_S = 60.0


@router.get("/fl-events")
async def fl_event_stream(_auth: Annotated[AuthContext, Depends(require_sse_auth)]):
    async def generate():
        yield ": keep-alive\n\n"
        ping_accum = 0.0
        while True:
            await asyncio.sleep(_FL_SSE_TICK_S)
            ping_accum += _FL_SSE_TICK_S
            if ping_accum >= _KEEPALIVE_EVERY_S:
                yield ": keep-alive\n\n"
                ping_accum = 0.0
            patch = state.next_fl_client_patch()
            yield f"data: {json.dumps(patch)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/events")
async def alert_event_stream(_auth: Annotated[AuthContext, Depends(require_sse_auth)]):
    async def generate():
        yield ": keep-alive\n\n"
        ping_accum = 0.0
        alert_accum = 0.0
        while True:
            await asyncio.sleep(_ALERT_SSE_TICK_S)
            ping_accum += _ALERT_SSE_TICK_S
            alert_accum += _ALERT_SSE_TICK_S
            if ping_accum >= _KEEPALIVE_EVERY_S:
                yield ": keep-alive\n\n"
                ping_accum = 0.0
            if alert_accum >= _ALERT_EVERY_S:
                alert = state.next_streaming_alert()
                yield f"data: {alert.model_dump_json(by_alias=True)}\n\n"
                alert_accum = 0.0

    return StreamingResponse(generate(), media_type="text/event-stream")
