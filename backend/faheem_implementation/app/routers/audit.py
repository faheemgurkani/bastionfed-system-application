import base64
import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.auth.deps import AuthContext, require_read_auth
from app.models.api import AuditLogListResponse
from app.store.memory import state

router = APIRouter(tags=["audit"])


@router.get("/audit/verify")
def verify_audit_logs(_auth: Annotated[AuthContext, Depends(require_read_auth)]) -> dict[str, Any]:
    return state.verify_audit_chain()


@router.get("/audit/logs", response_model=AuditLogListResponse)
def get_audit_logs(
    _auth: Annotated[AuthContext, Depends(require_read_auth)],
    limit: int = 50,
    cursor: str | None = None,
):
    rows = list(state.audit_logs)
    rows.sort(key=lambda a: a.timestamp, reverse=True)

    total = len(rows)
    start = 0
    if cursor:
        try:
            raw = base64.urlsafe_b64decode(cursor.encode())
            start = int(json.loads(raw.decode())["i"])
        except Exception:
            start = 0

    chunk = rows[start : start + limit]
    next_cursor = None
    if start + limit < total:
        next_cursor = base64.urlsafe_b64encode(json.dumps({"i": start + limit}).encode()).decode()

    return AuditLogListResponse(items=chunk, next_cursor=next_cursor, total=total)
