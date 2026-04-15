from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.auth.deps import AuthContext, require_read_auth, require_user, scoped_fl_client_ids
from app.errors import api_error
from datetime import datetime, timezone
import anyio

from app.models.api import AlertListResponse, AlertPatchRequest, EscalateAlertResponse
from app.models.domain import (
    Alert,
    AlertStatus,
    AuditAction,
    Severity,
    Incident,
    IncidentEvent,
    IncidentStatus,
    Playbook,
)
from app.store.tenant_store import tenant_store
from app.sse_bus import publish_alert

router = APIRouter(tags=["alerts"])


def _build_incident_from_alert(alert: Alert) -> Incident:
    now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    inc_id = f"INC-{int(datetime.now(timezone.utc).timestamp() * 1000)}"
    sev_to_priority = {
        Severity.CRITICAL: "P1",
        Severity.HIGH: "P2",
        Severity.MEDIUM: "P3",
        Severity.LOW: "P4",
    }
    priority = sev_to_priority.get(alert.severity, "P3")
    return Incident(
        id=inc_id,
        title=f"Escalated Incident — {alert.type}",
        severity=alert.severity,
        status=IncidentStatus.NEW,
        affected_devices=[alert.device.model_copy(deep=True)],
        time_open="0m",
        analyst_initials="NA",
        timeline=[
            IncidentEvent(
                id=f"e-{int(datetime.now(timezone.utc).timestamp() * 1000)}",
                timestamp=now_iso,
                type="DETECTION",
                description=f"Alert {alert.id} escalated to incident",
            )
        ],
        playbook=Playbook(
            id=f"pb-{alert.id}",
            name="Escalation Playbook",
            trigger_condition=alert.tactic,
            last_run=now_iso,
            executions=0,
            status="ACTIVE",
            steps=[],
        ),
        ticket_id=inc_id,
        reporter="BastionFed SOAR",
        assignee="Unassigned",
        priority=priority,
        created=now_iso,
        labels=[alert.tactic],
    )


@router.get("/alerts", response_model=AlertListResponse)
def list_alerts(
    auth: Annotated[AuthContext, Depends(require_read_auth)],
    limit: int = 50,
    cursor: str | None = None,
    severity: str | None = None,
    tactic: str | None = None,
    alert_status: str | None = Query(None, alias="status"),
    date_from: str | None = Query(None, alias="from"),
    date_to: str | None = Query(None, alias="to"),
    sort: str = "timestamp_desc",
):
    if not auth.tenant_id:
        raise api_error(status.HTTP_403_FORBIDDEN, "Tenant membership required", "TENANT_MEMBERSHIP_REQUIRED")
    fl_scope = scoped_fl_client_ids(auth)
    items, next_cursor, total = tenant_store.list_alerts(
        auth.tenant_id,
        limit=min(limit, 200),
        cursor=cursor,
        severity=severity,
        tactic=tactic,
        status=alert_status,
        date_from=date_from,
        date_to=date_to,
        sort=sort,
        fl_client_ids=fl_scope,
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

    if not auth.tenant_id:
        raise api_error(status.HTTP_403_FORBIDDEN, "Tenant membership required", "TENANT_MEMBERSHIP_REQUIRED")
    fl_scope = scoped_fl_client_ids(auth)
    if tenant_store.get_alert(auth.tenant_id, alert_id, fl_client_ids=fl_scope) is None:
        raise api_error(status.HTTP_404_NOT_FOUND, "Alert not found", "ALERT_NOT_FOUND")
    updated = tenant_store.update_alert_status(auth.tenant_id, alert_id, new_status, auth.uid or "unknown")
    if not updated:
        raise api_error(status.HTTP_404_NOT_FOUND, "Alert not found", "ALERT_NOT_FOUND")
    anyio.from_thread.run(publish_alert, auth.tenant_id, updated.model_dump(by_alias=True, mode="json"))
    return updated


@router.get("/alerts/{alert_id}", response_model=Alert)
def get_alert(
    alert_id: str,
    auth: Annotated[AuthContext, Depends(require_read_auth)],
):
    if not auth.tenant_id:
        raise api_error(status.HTTP_403_FORBIDDEN, "Tenant membership required", "TENANT_MEMBERSHIP_REQUIRED")
    a = tenant_store.get_alert(auth.tenant_id, alert_id, fl_client_ids=scoped_fl_client_ids(auth))
    if not a:
        raise api_error(status.HTTP_404_NOT_FOUND, "Alert not found", "ALERT_NOT_FOUND")
    return a


@router.post("/alerts/{alert_id}/escalate", response_model=EscalateAlertResponse)
def escalate_alert_to_incident(
    alert_id: str,
    auth: Annotated[AuthContext, Depends(require_user)],
):
    if not auth.tenant_id:
        raise api_error(status.HTTP_403_FORBIDDEN, "Tenant membership required", "TENANT_MEMBERSHIP_REQUIRED")
    incident = tenant_store.escalate_alert(
        auth.tenant_id, alert_id, auth.uid or "unknown", fl_client_ids=scoped_fl_client_ids(auth)
    )
    if not incident:
        raise api_error(status.HTTP_404_NOT_FOUND, "Alert not found", "ALERT_NOT_FOUND")
    return EscalateAlertResponse(incident=incident)
