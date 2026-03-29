from typing import Annotated

from fastapi import APIRouter, Depends

from app.auth.deps import AuthContext, require_user
from app.errors import api_error
from app.models.domain import BotMessage
from app.store.memory import state

router = APIRouter(tags=["bastionbot"])


@router.get("/bastionbot/conversations/{conversation_id}")
def get_conversation_history(
    conversation_id: str,
    _auth: Annotated[AuthContext, Depends(require_user)],
):
    messages: list[BotMessage] = state.get_conversation_history(conversation_id)
    if not messages:
        raise api_error(404, "Conversation not found", "CONVERSATION_NOT_FOUND")
    return {"conversationId": conversation_id, "messages": messages}
