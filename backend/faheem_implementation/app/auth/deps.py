from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Literal

from fastapi import Depends, Header, HTTPException, Query, status


@dataclass
class AuthContext:
    uid: str | None
    is_guest: bool
    mode: Literal["user", "guest", "anonymous"]


def _parse_bearer(authorization: str | None) -> str | None:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization[7:].strip()
    return token or None


def _truthy_guest(v: str | None) -> bool:
    if v is None:
        return False
    return v.lower() in ("true", "1", "yes")


async def get_auth_context(
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    guest: Annotated[str | None, Query(alias="guest")] = None,
) -> AuthContext:
    if _parse_bearer(authorization):
        return AuthContext(uid="firebase-user", is_guest=False, mode="user")
    if _truthy_guest(guest):
        return AuthContext(uid=None, is_guest=True, mode="guest")
    return AuthContext(uid=None, is_guest=False, mode="anonymous")


async def require_read_auth(ctx: Annotated[AuthContext, Depends(get_auth_context)]) -> AuthContext:
    if ctx.mode == "anonymous":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "detail": "Bearer token or ?guest=true required",
                "code": "AUTH_REQUIRED",
            },
        )
    return ctx


async def require_sse_auth(
    guest: Annotated[str | None, Query(alias="guest")] = None,
    token: Annotated[str | None, Query(alias="token")] = None,
) -> AuthContext:
    if _truthy_guest(guest):
        return AuthContext(uid=None, is_guest=True, mode="guest")
    if token:
        return AuthContext(uid="sse-token-user", is_guest=False, mode="user")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"detail": "Missing token or guest mode", "code": "SSE_AUTH_REQUIRED"},
    )


async def require_user(ctx: Annotated[AuthContext, Depends(get_auth_context)]) -> AuthContext:
    if ctx.mode == "guest":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"detail": "Guest mode cannot perform this action", "code": "GUEST_FORBIDDEN"},
        )
    if ctx.mode != "user" or not ctx.uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"detail": "Authentication required", "code": "AUTH_REQUIRED"},
        )
    return ctx
