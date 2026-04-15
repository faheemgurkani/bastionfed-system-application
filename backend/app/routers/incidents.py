from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel

from app.auth.deps import AuthContext, require_read_auth, require_user, scoped_fl_client_ids
from app.errors import api_error
from app.models.api import IncidentListResponse, PlaybookRunResponse
from app.models.domain import Incident, IncidentStatus, PlaybookStep
from app.store.tenant_store import tenant_store

router = APIRouter(tags=["incidents"])


@router.get("/incidents/{incident_id}", response_model=Incident)
def get_incident(
    incident_id: str,
    auth: Annotated[AuthContext, Depends(require_read_auth)],
):
    if not auth.tenant_id:
        raise api_error(status.HTTP_403_FORBIDDEN, "Tenant membership required", "TENANT_MEMBERSHIP_REQUIRED")
    inc = tenant_store.get_incident(auth.tenant_id, incident_id, fl_client_ids=scoped_fl_client_ids(auth))
    if not inc:
        raise api_error(status.HTTP_404_NOT_FOUND, "Incident not found", "INCIDENT_NOT_FOUND")
    return inc


@router.get("/incidents", response_model=IncidentListResponse)
def list_incidents(
    auth: Annotated[AuthContext, Depends(require_read_auth)],
    limit: int = 100,
    cursor: str | None = None,
):
    if not auth.tenant_id:
        raise api_error(status.HTTP_403_FORBIDDEN, "Tenant membership required", "TENANT_MEMBERSHIP_REQUIRED")
    items, next_cursor, total = tenant_store.list_incidents(
        auth.tenant_id, limit=limit, cursor=cursor, fl_client_ids=scoped_fl_client_ids(auth)
    )
    return IncidentListResponse(items=items, next_cursor=next_cursor, total=total)


@router.post("/incidents/{incident_id}/playbook/run", response_model=PlaybookRunResponse)
def run_playbook(
    incident_id: str,
    auth: Annotated[AuthContext, Depends(require_user)],
):
    if not auth.tenant_id:
        raise api_error(status.HTTP_403_FORBIDDEN, "Tenant membership required", "TENANT_MEMBERSHIP_REQUIRED")
    fl_scope = scoped_fl_client_ids(auth)
    if tenant_store.get_incident(auth.tenant_id, incident_id, fl_client_ids=fl_scope) is None:
        raise api_error(status.HTTP_404_NOT_FOUND, "Incident not found", "INCIDENT_NOT_FOUND")
    updated, current_step, now_iso = tenant_store.run_playbook(auth.tenant_id, incident_id, auth.uid or "unknown")
    if not updated:
        raise api_error(status.HTTP_404_NOT_FOUND, "Incident not found", "INCIDENT_NOT_FOUND")

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

    if not auth.tenant_id:
        raise api_error(status.HTTP_403_FORBIDDEN, "Tenant membership required", "TENANT_MEMBERSHIP_REQUIRED")
    fl_scope = scoped_fl_client_ids(auth)
    if tenant_store.get_incident(auth.tenant_id, incident_id, fl_client_ids=fl_scope) is None:
        raise api_error(status.HTTP_404_NOT_FOUND, "Incident not found", "INCIDENT_NOT_FOUND")
    updated = tenant_store.patch_incident_status(
        auth.tenant_id,
        incident_id=incident_id,
        status=new_status,
        assignee=body.assignee,
        notes=body.notes,
        actor_uid=auth.uid or "unknown",
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
    if not auth.tenant_id:
        raise api_error(status.HTTP_403_FORBIDDEN, "Tenant membership required", "TENANT_MEMBERSHIP_REQUIRED")
    fl_scope = scoped_fl_client_ids(auth)
    if tenant_store.get_incident(auth.tenant_id, incident_id, fl_client_ids=fl_scope) is None:
        raise api_error(status.HTTP_404_NOT_FOUND, "Incident not found", "INCIDENT_NOT_FOUND")
    updated = tenant_store.patch_playbook_step(
        auth.tenant_id,
        incident_id=incident_id,
        step_id=step_id,
        status=body.status,
        notes=body.notes,
        actor_uid=auth.uid or "unknown",
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
    if not auth.tenant_id:
        raise api_error(status.HTTP_403_FORBIDDEN, "Tenant membership required", "TENANT_MEMBERSHIP_REQUIRED")
    fl_scope = scoped_fl_client_ids(auth)
    if tenant_store.get_incident(auth.tenant_id, incident_id, fl_client_ids=fl_scope) is None:
        raise api_error(status.HTTP_404_NOT_FOUND, "Incident not found", "INCIDENT_NOT_FOUND")
    halted = tenant_store.halt_playbook(auth.tenant_id, incident_id=incident_id, reason=body.reason, actor_uid=auth.uid or "unknown")
    if not halted:
        raise api_error(status.HTTP_404_NOT_FOUND, "Incident not found", "INCIDENT_NOT_FOUND")
    return halted
