from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.auth.deps import AuthContext, require_read_auth
from app.errors import api_error
from app.models.domain import Incident
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
