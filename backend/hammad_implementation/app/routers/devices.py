from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.auth.deps import AuthContext, require_read_auth
from app.errors import api_error
from app.models.domain import Device
from app.store.memory import state

router = APIRouter(tags=["devices"])


@router.get("/devices", response_model=dict)
def list_devices(
    _auth: Annotated[AuthContext, Depends(require_read_auth)],
    wing: str | None = Query(None),
    status: str | None = Query(None, alias="status"),
    type: str | None = Query(None),
):
    return {"items": state.list_devices(wing=wing, status=status, type=type)}


@router.get("/devices/{device_id}", response_model=Device)
def get_device(
    device_id: str,
    _auth: Annotated[AuthContext, Depends(require_read_auth)],
):
    dev = state.get_device(device_id)
    if not dev:
        raise api_error(status.HTTP_404_NOT_FOUND, "Device not found", "DEVICE_NOT_FOUND")
    return dev
