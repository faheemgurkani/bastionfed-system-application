from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Annotated, Any, Literal

from fastapi import Depends, Header, HTTPException, Query, status

from app.auth.firebase import FirebaseAuthError, FirebaseTokenVerifier, VerifiedFirebaseToken
from app.config import settings
from app.store.tenant_store import tenant_store


_verifier: Any = FirebaseTokenVerifier()


def set_token_verifier(verifier: Any) -> None:
    global _verifier
    _verifier = verifier


@dataclass
class AuthContext:
    uid: str | None
    email: str | None
    tenant_id: str | None
    role: str | None
    token: str | None
    """Engineer/demo read-only access to the demo tenant when DEMO_MODE=1 (formerly guest)."""
    is_dev_mode: bool
    mode: Literal["user", "dev", "anonymous"]
    """When role is client_user, only these FL client IDs are visible; None means full tenant (non–client_user)."""
    fl_client_ids: frozenset[str] | None
    """Owner/admin only: scope API to these FL clients without changing membership (header X-Client-View-Ids)."""
    admin_client_view_ids: frozenset[str] | None = None


def _parse_bearer(authorization: str | None) -> str | None:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization[7:].strip()
    return token or None


def _truthy_query_flag(v: str | None) -> bool:
    if v is None:
        return False
    return v.lower() in ("true", "1", "yes")


def _dev_mode_query(guest: str | None, dev: str | None) -> bool:
    """Accept legacy ?guest=true and canonical ?dev=true."""
    return _truthy_query_flag(guest) or _truthy_query_flag(dev)


def _resolve_fl_client_scope(firebase_uid: str, tenant_id: str, role: str) -> frozenset[str] | None:
    if role != "client_user":
        return None
    ids = tenant_store.list_membership_fl_client_ids(tenant_id, firebase_uid)
    return frozenset(ids)


def _apply_client_view_override(auth: AuthContext, header_or_query: str | None) -> AuthContext:
    """Restrict owner/admin to explicit FL client IDs; ignored for other roles."""
    if auth.mode != "user" or not auth.tenant_id or auth.role not in ("owner", "admin"):
        return auth
    if not header_or_query or not header_or_query.strip():
        return auth
    ids = [s.strip() for s in header_or_query.split(",") if s.strip()]
    if not ids:
        return auth
    valid = {c.id for c in tenant_store.list_fl_clients(auth.tenant_id)}
    bad = [i for i in ids if i not in valid]
    if bad:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "detail": f"Unknown FL client ids in client view: {bad}",
                "code": "INVALID_CLIENT_VIEW_IDS",
            },
        )
    return replace(auth, admin_client_view_ids=frozenset(ids))


async def get_auth_context(
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    guest: Annotated[str | None, Query(alias="guest")] = None,
    dev: Annotated[str | None, Query(alias="dev")] = None,
    x_client_view_ids: Annotated[str | None, Header(alias="X-Client-View-Ids")] = None,
) -> AuthContext:
    token = _parse_bearer(authorization)
    if token:
        verified = _verify_or_401(token)
        membership = tenant_store.get_membership(verified.uid)
        tenant_id = membership[0] if membership else None
        role = membership[1] if membership else None
        fl_scope: frozenset[str] | None = None
        if tenant_id and role:
            fl_scope = _resolve_fl_client_scope(verified.uid, tenant_id, role)
        ctx = AuthContext(
            uid=verified.uid,
            email=verified.email,
            tenant_id=tenant_id,
            role=role,
            token=token,
            is_dev_mode=False,
            mode="user",
            fl_client_ids=fl_scope,
            admin_client_view_ids=None,
        )
        return _apply_client_view_override(ctx, x_client_view_ids)
    if _dev_mode_query(guest, dev):
        if not settings.demo_mode:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"detail": "Dev mode is only available when DEMO_MODE=1", "code": "DEV_MODE_DISABLED"},
            )
        tenant_store.ensure_demo_tenant()
        return AuthContext(
            uid=None,
            email=None,
            tenant_id=settings.demo_tenant_id,
            role="dev",
            token=None,
            is_dev_mode=True,
            mode="dev",
            fl_client_ids=None,
            admin_client_view_ids=None,
        )
    return AuthContext(
        uid=None,
        email=None,
        tenant_id=None,
        role=None,
        token=None,
        is_dev_mode=False,
        mode="anonymous",
        fl_client_ids=None,
        admin_client_view_ids=None,
    )


async def require_read_auth(ctx: Annotated[AuthContext, Depends(get_auth_context)]) -> AuthContext:
    if ctx.mode == "anonymous":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "detail": "Bearer token or ?dev=true (or legacy ?guest=true) required",
                "code": "AUTH_REQUIRED",
            },
        )
    return ctx


async def require_sse_auth(
    guest: Annotated[str | None, Query(alias="guest")] = None,
    dev: Annotated[str | None, Query(alias="dev")] = None,
    token: Annotated[str | None, Query(alias="token")] = None,
    client_view_ids: Annotated[str | None, Query(alias="clientViewIds")] = None,
) -> AuthContext:
    if _dev_mode_query(guest, dev):
        if not settings.demo_mode:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"detail": "Dev mode is only available when DEMO_MODE=1", "code": "DEV_MODE_DISABLED"},
            )
        tenant_store.ensure_demo_tenant()
        return AuthContext(
            uid=None,
            email=None,
            tenant_id=settings.demo_tenant_id,
            role="dev",
            token=None,
            is_dev_mode=True,
            mode="dev",
            fl_client_ids=None,
            admin_client_view_ids=None,
        )
    if token:
        verified = _verify_or_401(token)
        membership = tenant_store.get_membership(verified.uid)
        if membership is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"detail": "No tenant membership found for this user", "code": "TENANT_MEMBERSHIP_REQUIRED"},
            )
        tid, role = membership
        fl_scope = _resolve_fl_client_scope(verified.uid, tid, role)
        ctx = AuthContext(
            uid=verified.uid,
            email=verified.email,
            tenant_id=tid,
            role=role,
            token=token,
            is_dev_mode=False,
            mode="user",
            fl_client_ids=fl_scope,
            admin_client_view_ids=None,
        )
        return _apply_client_view_override(ctx, client_view_ids)
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"detail": "Missing token or dev mode", "code": "SSE_AUTH_REQUIRED"},
    )


async def require_user(ctx: Annotated[AuthContext, Depends(get_auth_context)]) -> AuthContext:
    if ctx.mode == "dev":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"detail": "Dev mode cannot perform this action", "code": "DEV_MODE_FORBIDDEN"},
        )
    if ctx.mode != "user" or not ctx.uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"detail": "Authentication required", "code": "AUTH_REQUIRED"},
        )
    return ctx


async def require_tenant_admin(ctx: Annotated[AuthContext, Depends(require_user)]) -> AuthContext:
    if not ctx.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"detail": "Tenant membership required", "code": "TENANT_MEMBERSHIP_REQUIRED"},
        )
    if ctx.role not in {"owner", "admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"detail": "Owner or admin role required", "code": "TENANT_ADMIN_REQUIRED"},
        )
    return ctx


async def require_bastionbot_user(ctx: Annotated[AuthContext, Depends(require_user)]) -> AuthContext:
    return ctx


def _verify_or_401(token: str) -> VerifiedFirebaseToken:
    try:
        return _verifier.verify(token)
    except FirebaseAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"detail": str(exc), "code": "INVALID_FIREBASE_TOKEN"},
        ) from exc


def scoped_fl_client_ids(auth: AuthContext) -> list[str] | None:
    """None = full tenant (or dev mode). Non-empty list = scoped to those FL clients."""
    if auth.mode == "dev":
        return None
    if auth.admin_client_view_ids is not None:
        return sorted(auth.admin_client_view_ids)
    if auth.fl_client_ids is None:
        return None
    return sorted(auth.fl_client_ids)


def alert_list_fl_scope(auth: AuthContext) -> list[str] | None:
    """FL scope for /api/alerts: owner/admin see full tenant (ignore X-Client-View-Ids); client_user only their FL clients."""
    if auth.mode == "dev":
        return None
    if auth.role in ("owner", "admin"):
        return None
    if auth.role == "client_user":
        ids = auth.fl_client_ids
        if not ids:
            return []
        return sorted(ids)
    if auth.fl_client_ids is None:
        return None
    return sorted(auth.fl_client_ids)
