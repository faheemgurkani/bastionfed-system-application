from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.auth.deps import AuthContext, require_read_auth, scoped_fl_client_ids
from app.errors import api_error
from app.store.tenant_store import tenant_store

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard/kpis")
def dashboard_kpis(auth: Annotated[AuthContext, Depends(require_read_auth)]) -> dict[str, Any]:
    if not auth.tenant_id:
        raise api_error(403, "Tenant membership required", "TENANT_MEMBERSHIP_REQUIRED")
    return tenant_store.dashboard_kpis(auth.tenant_id, fl_client_ids=scoped_fl_client_ids(auth))
