from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse

from app.auth.deps import AuthContext, require_read_auth, scoped_fl_client_ids
from app.models.api import AuditLogsResponse
from app.errors import api_error
from app.store.tenant_store import tenant_store

router = APIRouter(tags=["audit"])


@router.get("/audit/verify")
def verify_audit_logs(auth: Annotated[AuthContext, Depends(require_read_auth)]) -> dict[str, Any]:
    if not auth.tenant_id:
        raise api_error(403, "Tenant membership required", "TENANT_MEMBERSHIP_REQUIRED")
    fl_scope = scoped_fl_client_ids(auth)
    scope_uid = auth.uid if auth.role == "client_user" else None
    return tenant_store.verify_audit_chain(
        auth.tenant_id, fl_client_ids=fl_scope, scope_firebase_uid=scope_uid
    )


@router.get("/audit/logs", response_model=AuditLogsResponse)
def list_audit_logs(
    auth: Annotated[AuthContext, Depends(require_read_auth)],
    limit: int = 50,
    cursor: str | None = None,
    action: str | None = None,
    actor: str | None = None,
    date_from: str | None = Query(None, alias="from"),
    date_to: str | None = Query(None, alias="to"),
):
    if not auth.tenant_id:
        raise api_error(403, "Tenant membership required", "TENANT_MEMBERSHIP_REQUIRED")
    fl_scope = scoped_fl_client_ids(auth)
    scope_uid = auth.uid if auth.role == "client_user" else None
    items, next_cursor, total = tenant_store.list_audit_logs(
        auth.tenant_id,
        limit=limit,
        cursor=cursor,
        action=action,
        actor=actor,
        date_from=date_from,
        date_to=date_to,
        fl_client_ids=fl_scope,
        scope_firebase_uid=scope_uid,
    )
    return AuditLogsResponse(items=items, next_cursor=next_cursor, total=total)


@router.get("/audit/export", response_class=PlainTextResponse)
def export_audit_logs(
    auth: Annotated[AuthContext, Depends(require_read_auth)],
    format: str = "jsonl",
    date_from: str | None = Query(None, alias="from"),
    date_to: str | None = Query(None, alias="to"),
):
    if not auth.tenant_id:
        raise api_error(403, "Tenant membership required", "TENANT_MEMBERSHIP_REQUIRED")
    if format not in {"jsonl", "csv"}:
        raise api_error(400, "Unsupported export format", "INVALID_EXPORT_FORMAT")
    fl_scope = scoped_fl_client_ids(auth)
    scope_uid = auth.uid if auth.role == "client_user" else None
    payload = tenant_store.export_audit_logs(
        auth.tenant_id,
        format=format,
        date_from=date_from,
        date_to=date_to,
        fl_client_ids=fl_scope,
        scope_firebase_uid=scope_uid,
    )
    media_type = "text/csv" if format == "csv" else "application/x-ndjson"
    return PlainTextResponse(content=payload, media_type=media_type)
