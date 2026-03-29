from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel

from app.auth.deps import AuthContext, require_read_auth, require_user
from app.errors import api_error
from app.models.api import IncidentListResponse, PlaybookRunResponse
from app.models.domain import AuditAction, Incident, IncidentStatus, PlaybookStep
from app.store.memory import state

router = APIRouter(tags=["incidents"])


@router.get("/incidents/{incident_id}", response_model=Incident)
def get_incident(
    incident_id: str,
    _auth: Annotated[AuthContext, Depends(require_read_auth)],
):
    inc = state.get_incident(incident_id)
    if not inc:
        raise api_error(status.HTTP_404_NOT_FOUND, "Incident not found", "INCIDENT_NOT_FOUND")
    return inc


@router.get("/incidents", response_model=IncidentListResponse)
def list_incidents(
    _auth: Annotated[AuthContext, Depends(require_read_auth)],
    limit: int = 100,
    cursor: str | None = None,
):
    items, next_cursor, total = state.list_incidents(limit=limit, cursor=cursor)
    return IncidentListResponse(items=items, next_cursor=next_cursor, total=total)


@router.post("/incidents/{incident_id}/playbook/run", response_model=PlaybookRunResponse)
def run_playbook(
    incident_id: str,
    auth: Annotated[AuthContext, Depends(require_user)],
):
    now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    updated, current_step = state.run_playbook(incident_id, now_iso)
    if not updated:
        raise api_error(status.HTTP_404_NOT_FOUND, "Incident not found", "INCIDENT_NOT_FOUND")

    state.append_audit(
        actor=auth.uid or "unknown",
        action=AuditAction.RESPONSE_TRIGGERED,
        target=incident_id,
        result=f"Playbook run started (step {current_step})",
    )

    return PlaybookRunResponse(
        incident_id=updated.id,
        playbook_id=updated.playbook.id,
        started_at=now_iso,
        current_step=current_step or 1,
    )


class IncidentPatchRequest(BaseModel):
    status: str
    assignee: str
    notes: str | None = None


@router.patch("/incidents/{incident_id}", response_model=Incident)
def patch_incident(
    incident_id: str,
    body: IncidentPatchRequest,
    auth: Annotated[AuthContext, Depends(require_user)],
):
    try:
        new_status = IncidentStatus(body.status)
    except ValueError:
        raise api_error(status.HTTP_400_BAD_REQUEST, "Invalid incident status", "INVALID_STATUS")

    updated = state.patch_incident_status(
        incident_id=incident_id,
        status=new_status,
        assignee=body.assignee,
        notes=body.notes,
        actor=auth.uid or "unknown",
    )
    if not updated:
        raise api_error(status.HTTP_404_NOT_FOUND, "Incident not found", "INCIDENT_NOT_FOUND")
    return updated


class PlaybookStepPatchRequest(BaseModel):
    status: str
    notes: str | None = None


@router.patch("/incidents/{incident_id}/playbook/steps/{step_id}", response_model=PlaybookStep)
def patch_playbook_step(
    incident_id: str,
    step_id: str,
    body: PlaybookStepPatchRequest,
    auth: Annotated[AuthContext, Depends(require_user)],
):
    updated = state.patch_playbook_step(
        incident_id=incident_id,
        step_id=step_id,
        status=body.status,
        notes=body.notes,
        actor=auth.uid or "unknown",
    )
    if not updated:
        raise api_error(status.HTTP_404_NOT_FOUND, "Step not found", "PLAYBOOK_STEP_NOT_FOUND")
    return updated


class HaltPlaybookRequest(BaseModel):
    reason: str


@router.post("/incidents/{incident_id}/playbook/halt", response_model=dict)
def halt_playbook(
    incident_id: str,
    body: HaltPlaybookRequest,
    auth: Annotated[AuthContext, Depends(require_user)],
):
    halted = state.halt_playbook(incident_id=incident_id, reason=body.reason, actor=auth.uid or "unknown")
    if not halted:
        raise api_error(status.HTTP_404_NOT_FOUND, "Incident not found", "INCIDENT_NOT_FOUND")
    return halted
