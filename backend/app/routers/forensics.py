from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from pydantic import BaseModel, Field

from app.auth.deps import AuthContext, require_read_auth, require_user, scoped_fl_client_ids
from app.config import settings
from app.errors import api_error
from app.models.api import MalwareSampleListResponse
from app.models.domain import MalwareSample, RCAReport
from app.services.supabase_storage import create_signed_download_url, parse_bucket_and_object
from app.ml.inference import LEGACY_GLOBAL_MODEL_NAMES
from app.store.tenant_store import PostgresTenantStore, model_registry_payload_visible_for_fl_scope, tenant_store

router = APIRouter(tags=["forensics"])


@router.post("/forensics/samples", status_code=status.HTTP_201_CREATED)
def upload_sample(
    file: UploadFile = File(...),
    device_id: str = Form(..., alias="deviceId"),
    notes: str | None = Form(None),
    auth: Annotated[AuthContext, Depends(require_user)] = None,
):
    if not auth or not auth.tenant_id:
        raise api_error(status.HTTP_403_FORBIDDEN, "Tenant membership required", "TENANT_MEMBERSHIP_REQUIRED")
    fl_scope = scoped_fl_client_ids(auth)
    if tenant_store.get_device(auth.tenant_id, device_id, fl_client_ids=fl_scope) is None:
        raise api_error(status.HTTP_404_NOT_FOUND, "Device not found", "DEVICE_NOT_FOUND")
    s = tenant_store.upload_sample(auth.tenant_id, file=file, device_id=device_id, notes=notes, actor_uid=auth.uid or "unknown")
    return {
        "id": s.id,
        "sha256": s.sha256,
        "status": s.status,
        "uploadTime": s.upload_time,
    }


@router.get("/forensics/samples", response_model=MalwareSampleListResponse)
def list_samples(
    auth: Annotated[AuthContext, Depends(require_read_auth)],
    limit: int = 50,
    cursor: str | None = None,
    sample_status: str | None = Query(None, alias="status"),
    family: str | None = None,
):
    if not auth.tenant_id:
        raise api_error(status.HTTP_403_FORBIDDEN, "Tenant membership required", "TENANT_MEMBERSHIP_REQUIRED")
    items, next_cursor, total = tenant_store.list_samples(
        auth.tenant_id,
        limit=min(limit, 200),
        cursor=cursor,
        status=sample_status,
        family=family,
        fl_client_ids=scoped_fl_client_ids(auth),
    )
    return MalwareSampleListResponse(items=items, next_cursor=next_cursor, total=total)


@router.get("/forensics/rca/{rca_id}", response_model=RCAReport)
def get_rca(
    rca_id: str,
    auth: Annotated[AuthContext, Depends(require_read_auth)],
):
    if not auth.tenant_id:
        raise api_error(status.HTTP_403_FORBIDDEN, "Tenant membership required", "TENANT_MEMBERSHIP_REQUIRED")
    r = tenant_store.get_rca(auth.tenant_id, rca_id, fl_client_ids=scoped_fl_client_ids(auth))
    if not r:
        raise api_error(status.HTTP_404_NOT_FOUND, "RCA report not found", "RCA_NOT_FOUND")
    return r


@router.get("/forensics/rca", response_model=dict)
def list_rca(auth: Annotated[AuthContext, Depends(require_read_auth)]):
    if not auth.tenant_id:
        raise api_error(status.HTTP_403_FORBIDDEN, "Tenant membership required", "TENANT_MEMBERSHIP_REQUIRED")
    items, total = tenant_store.list_rca_reports(auth.tenant_id, fl_client_ids=scoped_fl_client_ids(auth))
    return {"items": items, "total": total}


@router.get("/forensics/samples/{sample_id}", response_model=MalwareSample)
def get_sample(
    sample_id: str,
    auth: Annotated[AuthContext, Depends(require_read_auth)],
):
    if not auth.tenant_id:
        raise api_error(status.HTTP_403_FORBIDDEN, "Tenant membership required", "TENANT_MEMBERSHIP_REQUIRED")
    s = tenant_store.get_sample(auth.tenant_id, sample_id, fl_client_ids=scoped_fl_client_ids(auth))
    if not s:
        raise api_error(status.HTTP_404_NOT_FOUND, "Sample not found", "SAMPLE_NOT_FOUND")
    return s


@router.get("/forensics/samples/{sample_id}/signed-download-url")
def get_sample_signed_download_url(
    sample_id: str,
    auth: Annotated[AuthContext, Depends(require_read_auth)],
):
    """Time-limited HTTPS URL for the raw object in Supabase Storage (private buckets)."""
    if not auth.tenant_id:
        raise api_error(status.HTTP_403_FORBIDDEN, "Tenant membership required", "TENANT_MEMBERSHIP_REQUIRED")
    s = tenant_store.get_sample(auth.tenant_id, sample_id, fl_client_ids=scoped_fl_client_ids(auth))
    if not s:
        raise api_error(status.HTTP_404_NOT_FOUND, "Sample not found", "SAMPLE_NOT_FOUND")
    if s.retention_status == "EXPIRED":
        raise api_error(
            status.HTTP_410_GONE,
            "Sample retention window has expired",
            "SAMPLE_EXPIRED",
        )
    if not s.storage_path:
        raise api_error(
            status.HTTP_404_NOT_FOUND,
            "Sample has no Storage object (upload may have skipped Storage)",
            "STORAGE_PATH_MISSING",
        )
    parsed = parse_bucket_and_object(s.storage_path)
    if not parsed:
        raise api_error(
            status.HTTP_400_BAD_REQUEST,
            "Invalid storage path on sample record",
            "STORAGE_PATH_INVALID",
        )
    bucket, object_key = parsed
    url = create_signed_download_url(bucket=bucket, object_key=object_key)
    if not url:
        raise api_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Could not create signed URL (check Supabase Storage and service key)",
            "SIGNED_URL_FAILED",
        )
    return {
        "signedUrl": url,
        "expiresIn": settings.storage_signed_url_expires_s,
    }


class GenerateRcaRequest(BaseModel):
    incident_id: str = Field(..., alias="incidentId")


@router.post("/forensics/rca", status_code=status.HTTP_201_CREATED, response_model=RCAReport)
def generate_rca(
    body: GenerateRcaRequest,
    auth: Annotated[AuthContext, Depends(require_user)],
):
    if not auth.tenant_id:
        raise api_error(status.HTTP_403_FORBIDDEN, "Tenant membership required", "TENANT_MEMBERSHIP_REQUIRED")
    r = tenant_store.generate_rca_report(
        auth.tenant_id, incident_id=body.incident_id, fl_client_ids=scoped_fl_client_ids(auth)
    )
    if not r:
        raise api_error(status.HTTP_404_NOT_FOUND, "Incident not found", "INCIDENT_NOT_FOUND")
    return r


@router.post("/forensics/samples/{sample_id}/scan", response_model=MalwareSample)
def scan_sample(
    sample_id: str,
    auth: Annotated[AuthContext, Depends(require_user)],
):
    if not auth.tenant_id:
        raise api_error(status.HTTP_403_FORBIDDEN, "Tenant membership required", "TENANT_MEMBERSHIP_REQUIRED")
    if tenant_store.get_sample(auth.tenant_id, sample_id, fl_client_ids=scoped_fl_client_ids(auth)) is None:
        raise api_error(status.HTTP_404_NOT_FOUND, "Sample not found", "SAMPLE_NOT_FOUND")
    sample = tenant_store.run_sample_scan(auth.tenant_id, sample_id=sample_id, actor_uid=auth.uid or "unknown")
    if not sample:
        raise api_error(status.HTTP_404_NOT_FOUND, "Sample not found", "SAMPLE_NOT_FOUND")
    return sample


@router.post("/forensics/samples/{sample_id}/quarantine", response_model=MalwareSample)
def quarantine_sample(
    sample_id: str,
    auth: Annotated[AuthContext, Depends(require_user)],
):
    if not auth.tenant_id:
        raise api_error(status.HTTP_403_FORBIDDEN, "Tenant membership required", "TENANT_MEMBERSHIP_REQUIRED")
    if tenant_store.get_sample(auth.tenant_id, sample_id, fl_client_ids=scoped_fl_client_ids(auth)) is None:
        raise api_error(status.HTTP_404_NOT_FOUND, "Sample not found", "SAMPLE_NOT_FOUND")
    sample = tenant_store.update_sample_disposition(
        auth.tenant_id,
        sample_id=sample_id,
        quarantine_status="QUARANTINED",
        actor_uid=auth.uid or "unknown",
        detail="Sample moved to quarantine",
    )
    if not sample:
        raise api_error(status.HTTP_404_NOT_FOUND, "Sample not found", "SAMPLE_NOT_FOUND")
    return sample


@router.post("/forensics/samples/{sample_id}/release", response_model=MalwareSample)
def release_sample(
    sample_id: str,
    auth: Annotated[AuthContext, Depends(require_user)],
):
    if not auth.tenant_id:
        raise api_error(status.HTTP_403_FORBIDDEN, "Tenant membership required", "TENANT_MEMBERSHIP_REQUIRED")
    if tenant_store.get_sample(auth.tenant_id, sample_id, fl_client_ids=scoped_fl_client_ids(auth)) is None:
        raise api_error(status.HTTP_404_NOT_FOUND, "Sample not found", "SAMPLE_NOT_FOUND")
    sample = tenant_store.update_sample_disposition(
        auth.tenant_id,
        sample_id=sample_id,
        quarantine_status="RELEASED",
        actor_uid=auth.uid or "unknown",
        detail="Sample released from quarantine",
    )
    if not sample:
        raise api_error(status.HTTP_404_NOT_FOUND, "Sample not found", "SAMPLE_NOT_FOUND")
    return sample


@router.post("/forensics/samples/{sample_id}/expire", response_model=MalwareSample)
def expire_sample(
    sample_id: str,
    auth: Annotated[AuthContext, Depends(require_user)],
):
    if not auth.tenant_id:
        raise api_error(status.HTTP_403_FORBIDDEN, "Tenant membership required", "TENANT_MEMBERSHIP_REQUIRED")
    if tenant_store.get_sample(auth.tenant_id, sample_id, fl_client_ids=scoped_fl_client_ids(auth)) is None:
        raise api_error(status.HTTP_404_NOT_FOUND, "Sample not found", "SAMPLE_NOT_FOUND")
    sample = tenant_store.update_sample_disposition(
        auth.tenant_id,
        sample_id=sample_id,
        retention_status="EXPIRED",
        actor_uid=auth.uid or "unknown",
        detail="Sample retention expired",
    )
    if not sample:
        raise api_error(status.HTTP_404_NOT_FOUND, "Sample not found", "SAMPLE_NOT_FOUND")
    return sample


@router.post("/forensics/analyze", response_model=dict)
async def analyze_file(
    auth: Annotated[AuthContext, Depends(require_read_auth)],
    file: UploadFile | None = File(None),
    fv_file: UploadFile | None = File(None),
    model: str = Query(default="fl-meta-v1"),
):
    from app.ml.inference import predict_from_image
    from app.sse_bus import publish_alert
    import json

    if not auth.tenant_id:
        raise api_error(status.HTTP_403_FORBIDDEN, "Tenant membership required", "TENANT_MEMBERSHIP_REQUIRED")

    image_bytes = await file.read() if file else None
    filename = file.filename if file else None
    feature_vector = None
    if fv_file:
        raw = await fv_file.read()
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            feature_vector = [float(x) for x in parsed]
        elif isinstance(parsed, dict) and "features" in parsed:
            feature_vector = [float(x) for x in parsed["features"]]

    fl_scope = scoped_fl_client_ids(auth)
    inference_tenant_id: str | None = auth.tenant_id if isinstance(tenant_store, PostgresTenantStore) else None
    row: dict | None = None
    if isinstance(tenant_store, PostgresTenantStore):
        row = tenant_store.get_model_registry_payload_by_name(auth.tenant_id, model)
        if row is None:
            if model not in LEGACY_GLOBAL_MODEL_NAMES:
                raise api_error(status.HTTP_404_NOT_FOUND, "Unknown model", "MODEL_NOT_FOUND")
        elif auth.role not in ("owner", "admin") and not model_registry_payload_visible_for_fl_scope(row, fl_scope):
            raise api_error(status.HTTP_403_FORBIDDEN, "Model not allowed for this principal", "MODEL_NOT_ALLOWED")

    inference_fl_client_id: str | None = None
    if row and row.get("flClientId"):
        inference_fl_client_id = str(row["flClientId"])
    elif fl_scope:
        inference_fl_client_id = sorted(fl_scope)[0]
    else:
        devs = tenant_store.list_devices(auth.tenant_id)
        inference_fl_client_id = devs[0].fl_client_id if devs else None

    result = predict_from_image(
        image_bytes=image_bytes,
        feature_vector=feature_vector,
        model_name=model,
        fl_client_id=inference_fl_client_id,
        tenant_id=inference_tenant_id,
    )
    result["sha256"] = None
    result["alertId"] = None
    result["incidentId"] = None
    result["alertSkippedReason"] = None

    if result["prediction"] == "MALWARE" and inference_fl_client_id:
        alert_id, incident_id, forensic_device_id, forensic_device_name = tenant_store.create_forensic_alert(
            auth.tenant_id,
            fl_client_id=inference_fl_client_id,
            confidence=result["confidence"],
            threat_score=result["threatScore"],
            model_used=model,
            actor_uid=auth.uid or "unknown",
            filename=filename,
        )
        result["alertId"] = alert_id or None
        result["incidentId"] = incident_id
        if forensic_device_id:
            result["deviceId"] = forensic_device_id
        if forensic_device_name:
            result["deviceName"] = forensic_device_name
        if not alert_id:
            result["alertSkippedReason"] = (
                "Model predicted MALWARE but no alert row was stored (tenant has no device to attach)."
            )
        else:
            sse_payload = {
                "type": "FORENSIC_ALERT",
                "alertId": alert_id,
                "incidentId": incident_id,
                "prediction": result["prediction"],
                "threatScore": result["threatScore"],
                "modelUsed": model,
                "flClientId": inference_fl_client_id,
            }
            if forensic_device_id:
                sse_payload["deviceId"] = forensic_device_id
            if forensic_device_name:
                sse_payload["deviceName"] = forensic_device_name
            await publish_alert(auth.tenant_id, sse_payload)
    elif result["prediction"] == "MALWARE" and not inference_fl_client_id:
        result["alertSkippedReason"] = (
            "MALWARE verdict but no FL client could be attached (missing scope). "
            "Use client-scoped access or admin client view with a selected FL client."
        )
    else:
        result["alertSkippedReason"] = (
            f"No alert: sample classified as {result['prediction']}. "
            "Alerts are only created for MALWARE (malware probability ≥ 50%). "
            "Drift scores on FL Health measure embedding shift vs training; they are not the malware verdict."
        )

    return result


class BlockIPRequest(BaseModel):
    ip: str
    reason: str
    alert_id: str | None = Field(None, alias="alertId")


@router.post("/network/block-ip", response_model=dict)
def block_ip(
    body: BlockIPRequest,
    auth: Annotated[AuthContext, Depends(require_user)],
):
    if not auth.tenant_id:
        raise api_error(status.HTTP_403_FORBIDDEN, "Tenant membership required", "TENANT_MEMBERSHIP_REQUIRED")
    fl_scope = scoped_fl_client_ids(auth)
    if body.alert_id and tenant_store.get_alert(auth.tenant_id, body.alert_id, fl_client_ids=fl_scope) is None:
        raise api_error(status.HTTP_404_NOT_FOUND, "Alert not found", "ALERT_NOT_FOUND")
    return tenant_store.block_ip(auth.tenant_id, ip=body.ip, reason=body.reason, alert_id=body.alert_id)
