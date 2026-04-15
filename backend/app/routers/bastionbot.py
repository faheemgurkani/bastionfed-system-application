from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends

from app.auth.deps import AuthContext, require_bastionbot_user, scoped_fl_client_ids
from app.bastionbot import bastionbot_engine, bastionbot_store
from app.errors import api_error
from app.models.api import (
    BastionBotChatRequest,
    BastionBotChatResponse,
    ConversationHistoryResponse,
    ConversationListResponse,
)
from app.models.domain import AuditAction
from app.store.tenant_store import tenant_store

router = APIRouter(tags=["bastionbot"])


def _bastionbot_store_uid(auth: AuthContext) -> str:
    """Partition SQLite rows when an owner/admin uses single-client preview (X-Client-View-Ids)."""
    base = auth.uid or "unknown"
    if auth.mode == "user" and auth.admin_client_view_ids:
        ids = ",".join(sorted(auth.admin_client_view_ids))
        return f"{base}::flview:{ids}"
    return base


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _conversation_title(message: str) -> str:
    cleaned = " ".join(message.split())
    if not cleaned:
        return "New Conversation"
    return cleaned[:58].rstrip() + ("…" if len(cleaned) > 58 else "")


def _merge_topics(existing: list[str], incoming: list[str]) -> list[str]:
    merged: list[str] = []
    for item in [*incoming, *existing]:
        if item and item not in merged:
            merged.append(item)
    return merged[:10]


@router.get("/bastionbot/conversations", response_model=ConversationListResponse)
def list_bastionbot_conversations(
    auth: Annotated[AuthContext, Depends(require_bastionbot_user)],
):
    if not auth.tenant_id:
        raise api_error(403, "Tenant membership required", "TENANT_MEMBERSHIP_REQUIRED")
    return ConversationListResponse(
        conversations=bastionbot_store.list_conversations(auth.tenant_id, _bastionbot_store_uid(auth)),
    )


@router.get("/bastionbot/conversations/{conversation_id}", response_model=ConversationHistoryResponse)
def get_bastionbot_conversation(
    conversation_id: str,
    auth: Annotated[AuthContext, Depends(require_bastionbot_user)],
):
    if not auth.tenant_id:
        raise api_error(403, "Tenant membership required", "TENANT_MEMBERSHIP_REQUIRED")
    store_uid = _bastionbot_store_uid(auth)
    conversation = bastionbot_store.get_conversation(auth.tenant_id, store_uid, conversation_id)
    if conversation is None:
        raise api_error(404, "Conversation not found", "CONVERSATION_NOT_FOUND")
    messages = bastionbot_store.get_conversation_history(auth.tenant_id, store_uid, conversation_id) or []
    return ConversationHistoryResponse(conversation_id=conversation_id, conversation=conversation, messages=messages)


@router.post("/bastionbot/chat", response_model=BastionBotChatResponse)
def bastionbot_chat(
    body: BastionBotChatRequest,
    auth: Annotated[AuthContext, Depends(require_bastionbot_user)],
):
    if not auth.tenant_id:
        raise api_error(403, "Tenant membership required", "TENANT_MEMBERSHIP_REQUIRED")
    store_uid = _bastionbot_store_uid(auth)
    actor_uid = auth.uid or "unknown"
    now_iso = _now_iso()
    conversation_id = body.conversation_id

    if conversation_id:
        conversation = bastionbot_store.get_conversation(auth.tenant_id, store_uid, conversation_id)
        if conversation is None:
            raise api_error(404, "Conversation not found", "CONVERSATION_NOT_FOUND")
    else:
        conversation = bastionbot_store.create_conversation(
            tenant_id=auth.tenant_id,
            uid=store_uid,
            title=_conversation_title(body.message),
            preview=body.message,
            now_iso=now_iso,
        )
        conversation_id = conversation.id

    bastionbot_store.append_message(
        tenant_id=auth.tenant_id,
        uid=store_uid,
        conversation_id=conversation_id,
        role="USER",
        content=body.message,
        now_iso=now_iso,
        context=(body.context.model_dump(by_alias=True) if body.context else {}),
        title=_conversation_title(body.message),
        preview=body.message,
    )

    prior_messages = bastionbot_store.get_conversation_history(auth.tenant_id, store_uid, conversation_id) or []
    prior_user_history = [msg.content for msg in prior_messages if msg.role == "USER"][:-1]
    memory = bastionbot_store.get_user_memory(auth.tenant_id, store_uid)
    fl_scope = scoped_fl_client_ids(auth)
    audit_uid = auth.uid if auth.role == "client_user" else None
    ask = bastionbot_engine.answer(
        query=body.message,
        tenant_store=tenant_store,
        tenant_id=auth.tenant_id,
        memory=memory,
        history=prior_user_history,
        context=body.context,
        fl_client_ids=fl_scope,
        audit_scope_firebase_uid=audit_uid,
    )

    bot_msg = bastionbot_store.append_message(
        tenant_id=auth.tenant_id,
        uid=store_uid,
        conversation_id=conversation_id,
        role="BOT",
        content=ask.answer,
        now_iso=now_iso,
        sources=ask.sources,
        context={
            "classification": ask.topics[0] if ask.topics else "mixed",
            "memoryUsed": ask.memory_used,
        },
        title=_conversation_title(body.message),
        preview=ask.answer,
    )
    updated_conversation = bastionbot_store.get_conversation(auth.tenant_id, store_uid, conversation_id)
    if updated_conversation is None:
        raise api_error(500, "Conversation state unavailable after chat", "CONVERSATION_STATE_ERROR")

    existing_topics = memory.recent_topics if memory else []
    preferred_answer_style = memory.preferred_answer_style if memory else "concise"
    bastionbot_store.upsert_user_memory(
        tenant_id=auth.tenant_id,
        uid=store_uid,
        last_active_conversation_id=conversation_id,
        recent_topics=_merge_topics(existing_topics, ask.topics),
        preferred_answer_style=preferred_answer_style,
        now_iso=now_iso,
    )

    tenant_store.append_audit(
        auth.tenant_id,
        actor_uid=actor_uid,
        actor_label=auth.email or actor_uid,
        action=AuditAction.DETECTION_MADE,
        target_type="bastionbot_conversation",
        target_id=conversation_id,
        result="BastionBot ask-mode response generated",
        metadata={},
    )

    return BastionBotChatResponse(
        message=bot_msg,
        conversation_id=conversation_id,
        conversation=updated_conversation,
        sources=ask.sources,
        memory_used=ask.memory_used,
    )
