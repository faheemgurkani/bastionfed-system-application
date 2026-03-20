from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.auth.deps import AuthContext, require_read_auth, require_user
from app.errors import api_error
from app.models.api import AlertListResponse, AlertPatchRequest
from app.models.domain import Alert, AlertStatus, AuditAction
from app.store.memory import state

router = APIRouter(tags=["alerts"])


@router.get("/alerts", response_model=AlertListResponse)
def list_alerts(
    _auth: Annotated[AuthContext, Depends(require_read_auth)],
    limit: int = 50,
    cursor: str | None = None,
    severity: str | None = None,
    tactic: str | None = None,
    alert_status: str | None = Query(None, alias="status"),
    date_from: str | None = Query(None, alias="from"),
    date_to: str | None = Query(None, alias="to"),
    sort: str = "timestamp_desc",
):
    items, next_cursor, total = state.list_alerts(
        limit=min(limit, 200),
        cursor=cursor,
        severity=severity,
        tactic=tactic,
        status=alert_status,
        date_from=date_from,
        date_to=date_to,
        sort=sort,
    )
    return AlertListResponse(items=items, next_cursor=next_cursor, total=total)


@router.patch("/alerts/{alert_id}", response_model=Alert)
def patch_alert(
    alert_id: str,
    body: AlertPatchRequest,
    auth: Annotated[AuthContext, Depends(require_user)],
):
    try:
        new_status = AlertStatus(body.status)
    except ValueError:
        raise api_error(status.HTTP_400_BAD_REQUEST, "Invalid status", "INVALID_STATUS")
    updated = state.update_alert_status(alert_id, new_status)
    if not updated:
        raise api_error(status.HTTP_404_NOT_FOUND, "Alert not found", "ALERT_NOT_FOUND")
    actor = auth.uid or "unknown"
    state.append_audit(
        actor=actor,
        action=AuditAction.RESPONSE_TRIGGERED,
        target=alert_id,
        result=f"Status changed to {new_status.value}",
    )
    return updated
