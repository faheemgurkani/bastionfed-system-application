from typing import Annotated

from fastapi import APIRouter, Depends

from app.auth.deps import AuthContext, require_user
from app.models.api import AuthBootstrapResponse, AuthSessionRequest, AuthSessionResponse
from app.store.tenant_store import tenant_store

router = APIRouter(tags=["auth"])


@router.get("/auth/bootstrap", response_model=AuthBootstrapResponse)
def auth_bootstrap(auth: Annotated[AuthContext, Depends(require_user)]):
    """Membership probe for first sign-in UX (no tenant auto-create)."""
    m = tenant_store.get_membership(auth.uid or "")
    if not m:
        return AuthBootstrapResponse(has_membership=False, tenant_id=None, role=None)
    tid, role = m
    return AuthBootstrapResponse(has_membership=True, tenant_id=tid, role=role)


@router.post("/auth/session", response_model=AuthSessionResponse)
def auth_session(
    body: AuthSessionRequest,
    auth: Annotated[AuthContext, Depends(require_user)],
):
    session = tenant_store.ensure_session_user(
        firebase_uid=auth.uid or body.uid,
        email=auth.email or body.email,
        display_name=body.display_name,
        photo_url=body.photo_url,
        account_type=body.account_type,
    )
    return AuthSessionResponse(
        uid=session.uid,
        created_at=session.created_at,
        last_login_at=session.last_login_at,
        tenant_id=session.tenant_id,
        role=session.role,
        is_new_tenant=session.is_new_tenant,
        needs_client_invite=session.needs_client_invite,
    )
