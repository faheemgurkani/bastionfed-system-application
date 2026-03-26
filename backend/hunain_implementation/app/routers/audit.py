from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.auth.deps import AuthContext, require_read_auth
from app.models.api import AuditLogsResponse
from app.store.memory import state

router = APIRouter(tags=["audit"])


@router.get("/audit/verify")
def verify_audit_logs(_auth: Annotated[AuthContext, Depends(require_read_auth)]) -> dict[str, Any]:
    return state.verify_audit_chain()


@router.get("/audit/logs", response_model=AuditLogsResponse)
def list_audit_logs(
    _auth: Annotated[AuthContext, Depends(require_read_auth)],
    limit: int = 50,
    cursor: str | None = None,
    action: str | None = None,
    actor: str | None = None,
    date_from: str | None = Query(None, alias="from"),
    date_to: str | None = Query(None, alias="to"),
):
    items, next_cursor, total = state.list_audit_logs(
        limit=limit,
        cursor=cursor,
        action=action,
        actor=actor,
        date_from=date_from,
        date_to=date_to,
    )
    return AuditLogsResponse(items=items, next_cursor=next_cursor, total=total)
