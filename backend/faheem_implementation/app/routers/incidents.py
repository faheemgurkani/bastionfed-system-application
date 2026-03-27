from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.auth.deps import AuthContext, require_read_auth
from app.errors import api_error
from app.models.api import IncidentListResponse
from app.models.domain import Incident
from app.store.memory import state

router = APIRouter(tags=["incidents"])


@router.get("/incidents", response_model=IncidentListResponse)
def list_incidents(_auth: Annotated[AuthContext, Depends(require_read_auth)]):
    """PRD §6.1 — Kanban seed; pagination filters can extend later."""
    items = state.list_incidents()
    return IncidentListResponse(items=items, next_cursor=None, total=len(items))


@router.get("/incidents/{incident_id}", response_model=Incident)
def get_incident(
    incident_id: str,
    _auth: Annotated[AuthContext, Depends(require_read_auth)],
):
    inc = state.get_incident(incident_id)
    if not inc:
        raise api_error(status.HTTP_404_NOT_FOUND, "Incident not found", "INCIDENT_NOT_FOUND")
    return inc
