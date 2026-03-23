from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.auth.deps import AuthContext, require_read_auth
from app.store.memory import state

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard/kpis")
def dashboard_kpis(_auth: Annotated[AuthContext, Depends(require_read_auth)]) -> dict[str, Any]:
    return state.dashboard_kpis()
