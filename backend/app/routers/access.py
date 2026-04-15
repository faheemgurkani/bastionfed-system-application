from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.auth.deps import AuthContext, require_tenant_admin, require_user
from app.errors import api_error
from app.models.api import (
    AuthSessionResponse,
    ClientUserInviteAcceptRequest,
    ClientUserInviteCreateRequest,
    ClientUserInviteCreateResponse,
    ClientUserInviteItem,
    ClientUserInvitesListResponse,
)
from app.models.domain import FLClientType
from app.store.tenant_store import tenant_store

router = APIRouter(tags=["access"])


@router.get("/access/invites/client", response_model=ClientUserInvitesListResponse)
def list_client_invites(auth: Annotated[AuthContext, Depends(require_tenant_admin)]):
    if not auth.tenant_id:
        raise api_error(status.HTTP_403_FORBIDDEN, "Tenant membership required", "TENANT_MEMBERSHIP_REQUIRED")
    raw = tenant_store.list_client_user_invites(auth.tenant_id)
    invites = [ClientUserInviteItem.model_validate(r) for r in raw]
    return ClientUserInvitesListResponse(invites=invites)


@router.post("/access/invites/client", response_model=ClientUserInviteCreateResponse)
def create_client_invite(
    body: ClientUserInviteCreateRequest,
    auth: Annotated[AuthContext, Depends(require_tenant_admin)],
):
    if not auth.tenant_id or not auth.uid:
        raise api_error(status.HTTP_403_FORBIDDEN, "Tenant membership required", "TENANT_MEMBERSHIP_REQUIRED")
    if not body.fl_client_ids:
        raise api_error(status.HTTP_400_BAD_REQUEST, "At least one FL client id is required", "FL_CLIENT_IDS_REQUIRED")
    by_id = {c.id: c for c in tenant_store.list_fl_clients(auth.tenant_id)}
    for cid in body.fl_client_ids:
        if cid not in by_id:
            raise api_error(status.HTTP_404_NOT_FOUND, f"Unknown FL client id: {cid}", "FL_CLIENT_NOT_FOUND")
    needs_email = any(by_id[cid].client_type == FLClientType.PERSON for cid in body.fl_client_ids)
    if needs_email and (not body.email or not str(body.email).strip()):
        raise api_error(
            status.HTTP_400_BAD_REQUEST,
            "Email is required when inviting person-operated FL clients",
            "INVITE_EMAIL_REQUIRED",
        )
    invite_id, token = tenant_store.create_client_user_invite(
        auth.tenant_id,
        email=body.email,
        fl_client_ids=body.fl_client_ids,
        expires_in_days=body.expires_in_days,
        created_by_firebase_uid=auth.uid,
    )
    return ClientUserInviteCreateResponse(invite_id=invite_id, token=token, expires_in_days=body.expires_in_days)


@router.post("/access/invites/client/accept", response_model=AuthSessionResponse)
def accept_client_invite(
    body: ClientUserInviteAcceptRequest,
    auth: Annotated[AuthContext, Depends(require_user)],
):
    if not auth.uid:
        raise api_error(status.HTTP_401_UNAUTHORIZED, "Authentication required", "AUTH_REQUIRED")
    try:
        session = tenant_store.accept_client_user_invite(
            firebase_uid=auth.uid,
            email=auth.email,
            token=body.token.strip(),
        )
    except ValueError as e:
        code = str(e)
        mapping = {
            "INVALID_INVITE_TOKEN": (404, "Invalid or unknown invite token"),
            "INVITE_ALREADY_USED": (409, "This invite has already been used"),
            "INVITE_EXPIRED": (410, "This invite has expired"),
            "INVITE_EMAIL_MISMATCH": (403, "Signed-in email does not match the invite"),
        }
        if code in mapping:
            status_code, msg = mapping[code]
            raise api_error(status_code, msg, code)
        raise
    return AuthSessionResponse(
        uid=session.uid,
        created_at=session.created_at,
        last_login_at=session.last_login_at,
        tenant_id=session.tenant_id,
        role=session.role,
        is_new_tenant=session.is_new_tenant,
        needs_client_invite=session.needs_client_invite,
    )
