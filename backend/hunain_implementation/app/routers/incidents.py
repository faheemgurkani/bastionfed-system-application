from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.auth.deps import AuthContext, require_read_auth, require_user
from app.errors import api_error
from app.models.api import IncidentListResponse, PlaybookRunResponse
from app.models.domain import AuditAction
from app.store.memory import state

router = APIRouter(tags=["incidents"])


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
