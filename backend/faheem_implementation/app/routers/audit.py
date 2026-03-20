from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.auth.deps import AuthContext, require_read_auth
from app.store.memory import state

router = APIRouter(tags=["audit"])


@router.get("/audit/verify")
def verify_audit_logs(_auth: Annotated[AuthContext, Depends(require_read_auth)]) -> dict[str, Any]:
    return state.verify_audit_chain()
