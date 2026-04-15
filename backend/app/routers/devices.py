from datetime import datetime, timezone
from typing import Annotated
import time

from fastapi import APIRouter, Depends, Query, status

from app.auth.deps import AuthContext, require_read_auth, require_user, scoped_fl_client_ids
from app.errors import api_error
from app.models.api import QuarantineResponse
from app.models.domain import Device
from app.store.tenant_store import tenant_store

router = APIRouter(tags=["devices"])


@router.get("/devices", response_model=dict)
def list_devices(
    auth: Annotated[AuthContext, Depends(require_read_auth)],
    wing: str | None = Query(None),
    status: str | None = Query(None, alias="status"),
    type: str | None = Query(None),
):
    if not auth.tenant_id:
        raise api_error(status.HTTP_403_FORBIDDEN, "Tenant membership required", "TENANT_MEMBERSHIP_REQUIRED")
    return {
        "items": tenant_store.list_devices(
            auth.tenant_id, wing=wing, status=status, type=type, fl_client_ids=scoped_fl_client_ids(auth)
        )
    }


@router.get("/devices/{device_id}", response_model=Device)
def get_device(
    device_id: str,
    auth: Annotated[AuthContext, Depends(require_read_auth)],
):
    if not auth.tenant_id:
        raise api_error(status.HTTP_403_FORBIDDEN, "Tenant membership required", "TENANT_MEMBERSHIP_REQUIRED")
    dev = tenant_store.get_device(auth.tenant_id, device_id, fl_client_ids=scoped_fl_client_ids(auth))
    if not dev:
        raise api_error(status.HTTP_404_NOT_FOUND, "Device not found", "DEVICE_NOT_FOUND")
    return dev


@router.post("/devices/{device_id}/quarantine", response_model=QuarantineResponse)
def quarantine_device(
    device_id: str,
    auth: Annotated[AuthContext, Depends(require_user)],
):
    if not auth.tenant_id:
        raise api_error(status.HTTP_403_FORBIDDEN, "Tenant membership required", "TENANT_MEMBERSHIP_REQUIRED")
    fl_scope = scoped_fl_client_ids(auth)
    if tenant_store.get_device(auth.tenant_id, device_id, fl_client_ids=fl_scope) is None:
        raise api_error(status.HTTP_404_NOT_FOUND, "Device not found", "DEVICE_NOT_FOUND")
    result = tenant_store.quarantine_device(auth.tenant_id, device_id, auth.uid or "unknown")
    if not result:
        raise api_error(status.HTTP_404_NOT_FOUND, "Device not found", "DEVICE_NOT_FOUND")
    return QuarantineResponse.model_validate(result)
