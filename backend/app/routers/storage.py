"""Supabase Storage catalog + client artifact uploads (single bucket, tenant/client/label paths)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status

from app.auth.deps import AuthContext, require_read_auth, require_user, scoped_fl_client_ids
from app.errors import api_error
from app.services.supabase_storage import list_storage_buckets
from app.store.tenant_store import PostgresTenantStore, tenant_store

router = APIRouter(tags=["storage"])


@router.get("/storage/buckets")
def list_buckets(auth: Annotated[AuthContext, Depends(require_read_auth)]) -> dict:
    """Return buckets visible to the Supabase service key (id, name, public, …)."""
    if auth.mode == "anonymous":
        raise api_error(status.HTTP_401_UNAUTHORIZED, "Authentication required", "AUTH_REQUIRED")
    return {"buckets": list_storage_buckets()}


def _ensure_postgres_artifacts() -> PostgresTenantStore:
    if not isinstance(tenant_store, PostgresTenantStore):
        raise api_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Client artifacts require Postgres persistence",
            "POSTGRES_REQUIRED",
        )
    return tenant_store


def _assert_fl_client_access(auth: AuthContext, fl_client_id: str) -> None:
    if auth.role == "client_user":
        allowed = auth.fl_client_ids or frozenset()
        if fl_client_id not in allowed:
            raise api_error(status.HTTP_403_FORBIDDEN, "Not allowed for this FL client", "FL_CLIENT_FORBIDDEN")
    elif auth.role not in ("owner", "admin"):
        raise api_error(status.HTTP_403_FORBIDDEN, "Owner or admin required", "TENANT_ADMIN_REQUIRED")


def _require_artifact_actor(auth: AuthContext) -> None:
    """Training artifacts (PNG/JSON): only tenant admins or scoped client users."""
    if auth.mode != "user" or not auth.uid or not auth.tenant_id:
        raise api_error(status.HTTP_403_FORBIDDEN, "Authentication required", "AUTH_REQUIRED")
    if auth.role not in ("client_user", "owner", "admin"):
        raise api_error(
            status.HTTP_403_FORBIDDEN,
            "Only tenant admins or client users may access training artifacts",
            "ARTIFACT_ROLE_FORBIDDEN",
        )


@router.post("/storage/client-artifacts", status_code=status.HTTP_201_CREATED)
async def upload_client_artifact(
    auth: Annotated[AuthContext, Depends(require_user)],
    fl_client_id: str = Form(..., alias="flClientId"),
    label: str = Form(...),
    file: UploadFile = File(...),
    notes: str | None = Form(None),
):
    if not auth.tenant_id:
        raise api_error(status.HTTP_403_FORBIDDEN, "Tenant membership required", "TENANT_MEMBERSHIP_REQUIRED")
    _require_artifact_actor(auth)
    if label not in ("benign", "malware"):
        raise api_error(status.HTTP_400_BAD_REQUEST, "label must be benign or malware", "INVALID_LABEL")
    _assert_fl_client_access(auth, fl_client_id)
    store = _ensure_postgres_artifacts()
    data = await file.read()
    fn = file.filename or "upload.bin"

    class _Buf:
        filename = fn

        def read(self) -> bytes:
            return data

    row = store.upload_client_artifact(
        auth.tenant_id,
        fl_client_id=fl_client_id,
        label=label,
        file=_Buf(),
        notes=notes,
        actor_uid=auth.uid or "unknown",
    )
    if not row:
        raise api_error(status.HTTP_404_NOT_FOUND, "FL client not found", "FL_CLIENT_NOT_FOUND")
    return row


@router.get("/storage/client-artifacts")
def list_client_artifacts(
    auth: Annotated[AuthContext, Depends(require_user)],
    fl_client_id: str | None = Query(None, alias="flClientId"),
    label: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    if not auth.tenant_id:
        raise api_error(status.HTTP_403_FORBIDDEN, "Tenant membership required", "TENANT_MEMBERSHIP_REQUIRED")
    _require_artifact_actor(auth)
    store = _ensure_postgres_artifacts()
    scope = scoped_fl_client_ids(auth)
    eff_ids: list[str] | None = None
    if fl_client_id:
        if scope is not None and fl_client_id not in scope:
            raise api_error(status.HTTP_403_FORBIDDEN, "Not allowed for this FL client", "FL_CLIENT_FORBIDDEN")
        _assert_fl_client_access(auth, fl_client_id)
        eff_ids = [fl_client_id]
    elif scope is not None:
        eff_ids = list(scope)
    items = store.list_client_artifacts(
        auth.tenant_id,
        fl_client_id=None,
        label=label,
        limit=limit,
        fl_client_ids=eff_ids,
    )
    return {"artifacts": items}
