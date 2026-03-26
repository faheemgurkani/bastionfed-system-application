from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends

from app.auth.deps import AuthContext, require_read_auth, require_user
from app.models.api import (
    BastionBotChatRequest,
    BastionBotChatResponse,
    ConversationListResponse,
    AuthSessionRequest,
    AuthSessionResponse,
)
from app.models.domain import AuditAction
from app.store.memory import state

router = APIRouter(tags=["auth"])


@router.get("/bastionbot/conversations", response_model=ConversationListResponse)
def list_bastionbot_conversations(
    _auth: Annotated[AuthContext, Depends(require_read_auth)],
):
    return ConversationListResponse(conversations=state.list_conversations())


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
    return AuthSessionResponse(uid=body.uid, created_at=u.created_at, last_login_at=u.last_login_at)


@router.post("/bastionbot/chat", response_model=BastionBotChatResponse)
def bastionbot_chat(
    body: BastionBotChatRequest,
    auth: Annotated[AuthContext, Depends(require_user)],
):
    now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    # Store the user message + a stub bot response (keeps behavior deterministic without external calls).
    state.append_bot_message(
        conversation_id=body.conversation_id,
        role="USER",
        content=body.message,
        now_iso=now_iso,
    )

    context_bits: list[str] = []
    if body.context and body.context.alert_id:
        context_bits.append(f"alertId={body.context.alert_id}")
    if body.context and body.context.incident_id:
        context_bits.append(f"incidentId={body.context.incident_id}")
    context_str = f" ({', '.join(context_bits)})" if context_bits else ""

    bot_content = f"BastionBot stub: I received your message{context_str}. Next step: fetch relevant alert/incident data from the platform."
    bot_msg = state.append_bot_message(
        conversation_id=body.conversation_id,
        role="BOT",
        content=bot_content,
        now_iso=now_iso,
    )

    # Optionally record chat as audit activity.
    state.append_audit(
        actor=auth.uid or "unknown",
        action=AuditAction.DETECTION_MADE,
        target=body.conversation_id,
        result="BastionBot chat interaction",
    )

    return BastionBotChatResponse(message=bot_msg, conversation_id=body.conversation_id)
