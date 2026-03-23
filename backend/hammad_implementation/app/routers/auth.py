from typing import Annotated

from fastapi import APIRouter, Depends

from app.auth.deps import AuthContext, require_read_auth
from app.models.domain import BotMessage
from app.store.memory import state

router = APIRouter(tags=["bastionbot"])


@router.get("/bastionbot/conversations/{conversation_id}")
def get_conversation_history(
    conversation_id: str,
    _auth: Annotated[AuthContext, Depends(require_read_auth)],
):
    messages: list[BotMessage] = state.get_conversation_history(conversation_id)
    return {"conversationId": conversation_id, "messages": messages}
