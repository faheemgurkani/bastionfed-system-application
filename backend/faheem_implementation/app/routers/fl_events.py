"""SSE stream for FL client patches (PRD §4.2). Same synthetic pattern as alert /api/events for phase-1 dev."""

import asyncio
import json
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.auth.deps import AuthContext, require_sse_auth
from app.store.memory import state

router = APIRouter(tags=["fl"])

_SSE_TICK_S = 0.25
_KEEPALIVE_EVERY_S = 15.0


@router.get("/fl-events")
async def fl_client_event_stream(_auth: Annotated[AuthContext, Depends(require_sse_auth)]):
    async def generate():
        yield ": keep-alive\n\n"
        ping_accum = 0.0
        while True:
            await asyncio.sleep(_SSE_TICK_S)
            ping_accum += _SSE_TICK_S
            if ping_accum >= _KEEPALIVE_EVERY_S:
                yield ": keep-alive\n\n"
                ping_accum = 0.0
            patch = state.next_streaming_fl_patch()
            yield f"data: {json.dumps(patch)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
