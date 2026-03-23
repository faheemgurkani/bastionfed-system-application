from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel

from app.auth.deps import AuthContext, require_user
from app.errors import api_error
from app.models.domain import Incident, IncidentStatus, PlaybookStep
from app.store.memory import state

router = APIRouter(tags=["incidents"])


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
