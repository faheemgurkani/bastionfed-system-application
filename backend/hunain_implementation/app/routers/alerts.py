from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.auth.deps import AuthContext, require_read_auth, require_user
from app.errors import api_error
from datetime import datetime, timezone

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


@router.get("/alerts/{alert_id}", response_model=Alert)
def get_alert(
    alert_id: str,
    _auth: Annotated[AuthContext, Depends(require_read_auth)],
):
    a = state.get_alert(alert_id)
    if not a:
        raise api_error(status.HTTP_404_NOT_FOUND, "Alert not found", "ALERT_NOT_FOUND")
    return a


@router.post("/alerts/{alert_id}/escalate", response_model=EscalateAlertResponse)
def escalate_alert_to_incident(
    alert_id: str,
    auth: Annotated[AuthContext, Depends(require_user)],
):
    alert = state.get_alert(alert_id)
    if not alert:
        raise api_error(status.HTTP_404_NOT_FOUND, "Alert not found", "ALERT_NOT_FOUND")

    now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    inc_id = f"INC-{int(datetime.now(timezone.utc).timestamp() * 1000)}"

    sev_to_priority = {
        Severity.CRITICAL: "P1",
        Severity.HIGH: "P2",
        Severity.MEDIUM: "P3",
        Severity.LOW: "P4",
    }
    priority = sev_to_priority.get(alert.severity, "P3")

    incident = Incident(
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

    state.incidents.append(incident)

    updated_alert = state.update_alert_status(alert.id, AlertStatus.IN_REVIEW)
    if updated_alert:
        actor = auth.uid or "unknown"
        state.append_audit(
            actor=actor,
            action=AuditAction.RESPONSE_TRIGGERED,
            target=alert.id,
            result="Status changed to IN_REVIEW",
        )

    return EscalateAlertResponse(incident=incident)
