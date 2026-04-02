from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, status

from app.auth.deps import AuthContext, require_read_auth, require_user
from app.errors import api_error
from app.ml.drift import get_drift_report, get_per_client_drift
from app.ml.metrics import get_model_metrics
from app.models.api import FLClientsResponse, FLModelActivateResponse, FLRoundsResponse
from app.models.domain import AuditAction, FLClient
from app.store.memory import state

router = APIRouter(tags=["fl"])


@router.get("/fl/drift")
def fl_drift(_auth: Annotated[AuthContext, Depends(require_read_auth)]) -> dict:
    return get_drift_report()


@router.get("/fl/drift/clients")
def fl_client_drift(_auth: Annotated[AuthContext, Depends(require_read_auth)]) -> dict:
    return get_per_client_drift()


@router.get("/fl/status")
def fl_status(_auth: Annotated[AuthContext, Depends(require_read_auth)]) -> dict[str, Any]:
    return state.fl_status_dict()


@router.get("/fl/models/metrics")
def fl_model_metrics(_auth: Annotated[AuthContext, Depends(require_read_auth)]) -> dict[str, Any]:
    return get_model_metrics()


@router.get("/fl/clients/{client_id}", response_model=FLClient)
def get_fl_client(
    client_id: str,
    _auth: Annotated[AuthContext, Depends(require_read_auth)],
):
    c = state.get_fl_client(client_id)
    if not c:
        raise api_error(status.HTTP_404_NOT_FOUND, "Client not found", "FL_CLIENT_NOT_FOUND")
    return c


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
