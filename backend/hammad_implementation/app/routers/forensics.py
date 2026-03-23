from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from pydantic import BaseModel, Field

from app.auth.deps import AuthContext, require_read_auth, require_user
from app.errors import api_error
from app.models.domain import RCAReport
from app.store.memory import state

router = APIRouter(tags=["forensics"])


@router.post("/forensics/samples", status_code=status.HTTP_201_CREATED)
def upload_sample(
    file: UploadFile = File(...),
    device_id: str = Form(..., alias="deviceId"),
    notes: str | None = Form(None),
    _auth: Annotated[AuthContext, Depends(require_user)] = None,
):
    s = state.upload_malware_sample(file=file, device_id=device_id, notes=notes)
    return {
        "id": s.id,
        "sha256": s.sha256,
        "status": s.status,
        "uploadTime": s.upload_time,
    }


@router.get("/forensics/rca", response_model=dict)
def list_rca(_auth: Annotated[AuthContext, Depends(require_read_auth)]):
    items, total = state.list_rca_reports()
    return {"items": items, "total": total}


class GenerateRcaRequest(BaseModel):
    incident_id: str = Field(..., alias="incidentId")


@router.post("/forensics/rca", status_code=status.HTTP_201_CREATED, response_model=RCAReport)
def generate_rca(
    body: GenerateRcaRequest,
    _auth: Annotated[AuthContext, Depends(require_user)],
):
    r = state.generate_rca_report(incident_id=body.incident_id)
    if not r:
        raise api_error(status.HTTP_404_NOT_FOUND, "Incident not found", "INCIDENT_NOT_FOUND")
    return r


class BlockIPRequest(BaseModel):
    ip: str
    reason: str
    alert_id: str | None = Field(None, alias="alertId")


@router.post("/network/block-ip", response_model=dict)
def block_ip(
    body: BlockIPRequest,
    _auth: Annotated[AuthContext, Depends(require_user)],
):
    return state.block_ip(ip=body.ip, reason=body.reason, alert_id=body.alert_id)
