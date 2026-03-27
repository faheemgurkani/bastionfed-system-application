from typing import Annotated, Any

from fastapi import APIRouter, Depends, status

from app.auth.deps import AuthContext, require_read_auth
from app.errors import api_error
from app.models.api import FLClientsListResponse
from app.models.domain import FLClient
from app.store.memory import state

router = APIRouter(tags=["fl"])


@router.get("/fl/status")
def fl_status(_auth: Annotated[AuthContext, Depends(require_read_auth)]) -> dict[str, Any]:
    return state.fl_status_dict()


@router.get("/fl/clients", response_model=FLClientsListResponse)
def list_fl_clients(_auth: Annotated[AuthContext, Depends(require_read_auth)]):
    """PRD §8.3 — seed list for ClientGrid (same in-memory data as detail routes)."""
    return FLClientsListResponse(clients=[c.model_copy(deep=True) for c in state.fl_clients])


@router.get("/fl/clients/{client_id}", response_model=FLClient)
def get_fl_client(
    client_id: str,
    _auth: Annotated[AuthContext, Depends(require_read_auth)],
):
    c = state.get_fl_client(client_id)
    if not c:
        raise api_error(status.HTTP_404_NOT_FOUND, "Client not found", "FL_CLIENT_NOT_FOUND")
    return c
