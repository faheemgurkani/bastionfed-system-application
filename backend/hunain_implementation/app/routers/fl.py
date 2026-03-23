from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.auth.deps import AuthContext, require_read_auth, require_user
from app.errors import api_error
from app.models.api import FLClientsResponse, FLModelActivateResponse, FLRoundsResponse
from app.models.domain import AuditAction
from app.store.memory import state

router = APIRouter(tags=["fl"])


@router.get("/fl/rounds", response_model=FLRoundsResponse)
def list_fl_rounds(_auth: Annotated[AuthContext, Depends(require_read_auth)]) -> FLRoundsResponse:
    return FLRoundsResponse(rounds=state.fl_rounds, session_id=state.fl_session_id)


@router.get("/fl/clients", response_model=FLClientsResponse)
def list_fl_clients(_auth: Annotated[AuthContext, Depends(require_read_auth)]) -> FLClientsResponse:
    return FLClientsResponse(clients=state.fl_clients)


@router.post("/fl/models/{model_name}/activate", response_model=FLModelActivateResponse)
def activate_fl_model(
    model_name: str,
    auth: Annotated[AuthContext, Depends(require_user)],
):
    now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    prev = state.activate_fl_model(model_name, now_iso)
    if prev is None:
        raise api_error(status.HTTP_404_NOT_FOUND, "Model not found", "MODEL_NOT_FOUND")

    state.append_audit(
        actor=auth.uid or "unknown",
        action=AuditAction.MODEL_UPDATED,
        target=model_name,
        result=f"Activated model {model_name}",
    )

    return FLModelActivateResponse(
        activated=model_name,
        previously_active=prev,
        switched_at=now_iso,
    )
