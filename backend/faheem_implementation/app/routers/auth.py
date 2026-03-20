from typing import Annotated

from fastapi import APIRouter, Depends

from app.auth.deps import AuthContext, require_user
from app.models.api import AuthSessionRequest, AuthSessionResponse
from app.models.domain import AuditAction
from app.store.memory import state

router = APIRouter(tags=["auth"])


@router.post("/auth/session", response_model=AuthSessionResponse)
def auth_session(
    body: AuthSessionRequest,
    _auth: Annotated[AuthContext, Depends(require_user)],
):
    u = state.upsert_session_user(
        uid=body.uid,
        email=body.email,
        display_name=body.display_name,
        photo_url=body.photo_url,
    )
    state.append_audit(
        actor=body.email or body.uid,
        action=AuditAction.USER_LOGIN,
        target=body.uid,
        result="SUCCESS",
    )
    return AuthSessionResponse(uid=body.uid, createdAt=u.created_at, lastLoginAt=u.last_login_at)
