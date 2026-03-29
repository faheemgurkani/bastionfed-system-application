from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from pydantic import BaseModel, Field

from app.auth.deps import AuthContext, require_read_auth, require_user
from app.errors import api_error
from app.models.api import MalwareSampleListResponse
from app.models.domain import MalwareSample, RCAReport
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


@router.get("/forensics/samples", response_model=MalwareSampleListResponse)
def list_samples(
    _auth: Annotated[AuthContext, Depends(require_read_auth)],
    limit: int = 50,
    cursor: str | None = None,
    sample_status: str | None = Query(None, alias="status"),
    family: str | None = None,
):
    items, next_cursor, total = state.list_samples(
        limit=min(limit, 200),
        cursor=cursor,
        status=sample_status,
        family=family,
    )
    return MalwareSampleListResponse(items=items, next_cursor=next_cursor, total=total)


@router.get("/forensics/rca/{rca_id}", response_model=RCAReport)
def get_rca(
    rca_id: str,
    _auth: Annotated[AuthContext, Depends(require_read_auth)],
):
    r = state.get_rca(rca_id)
    if not r:
        raise api_error(status.HTTP_404_NOT_FOUND, "RCA report not found", "RCA_NOT_FOUND")
    return r


@router.get("/forensics/rca", response_model=dict)
def list_rca(_auth: Annotated[AuthContext, Depends(require_read_auth)]):
    items, total = state.list_rca_reports()
    return {"items": items, "total": total}


@router.get("/forensics/samples/{sample_id}", response_model=MalwareSample)
def get_sample(
    sample_id: str,
    _auth: Annotated[AuthContext, Depends(require_read_auth)],
):
    s = state.get_sample(sample_id)
    if not s:
        raise api_error(status.HTTP_404_NOT_FOUND, "Sample not found", "SAMPLE_NOT_FOUND")
    return s


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
