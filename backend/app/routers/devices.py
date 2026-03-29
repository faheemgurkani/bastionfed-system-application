from datetime import datetime, timezone
from typing import Annotated
import time

from fastapi import APIRouter, Depends, status

from app.auth.deps import AuthContext, require_user
from app.errors import api_error
from app.models.api import QuarantineResponse
from app.models.domain import AuditAction, DeviceStatus
from app.store.memory import state

router = APIRouter(tags=["devices"])


@router.post("/devices/{device_id}/quarantine", response_model=QuarantineResponse)
def quarantine_device(
    device_id: str,
    auth: Annotated[AuthContext, Depends(require_user)],
):
    dev = state.get_device(device_id)
    if not dev:
        raise api_error(status.HTTP_404_NOT_FOUND, "Device not found", "DEVICE_NOT_FOUND")
    state.set_device_status(device_id, DeviceStatus.ISOLATED)
    state.sync_alert_devices_for_device_id(device_id)
    cmd_id = f"CMD-{int(time.time() * 1000)}"
    sent_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    actor = auth.uid or "unknown"
    state.append_audit(
        actor=actor,
        action=AuditAction.DEVICE_QUARANTINED,
        target=device_id,
        result=f"Isolation command {cmd_id} dispatched",
    )
    state.append_quarantine_to_open_incidents(
        device_id,
        f"Device {dev.name} quarantined ({device_id})",
    )
    return QuarantineResponse(device_id=device_id, status="ISOLATED", command_id=cmd_id, sent_at=sent_at)
