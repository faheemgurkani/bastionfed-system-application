from __future__ import annotations

from app.bastionbot import bastionbot_engine, bastionbot_store
from app.config import settings
from app.store.memory import state


def _chat(client, headers: dict[str, str], *, message: str, conversation_id: str | None = None):
    payload: dict[str, str] = {"message": message}
    if conversation_id:
        payload["conversationId"] = conversation_id
    return client.post("/api/bastionbot/chat", headers=headers, json=payload)


def test_bastionbot_bot_history_preserves_sources(client, auth_headers: dict[str, str]):
    response = _chat(client, auth_headers, message="How does the audit verification feature work?")
    assert response.status_code == 200
    conversation_id = response.json()["conversationId"]

    history = client.get(f"/api/bastionbot/conversations/{conversation_id}", headers=auth_headers)
    assert history.status_code == 200

    messages = history.json()["messages"]
    assert len(messages) == 2
    assert messages[1]["role"] == "BOT"
    assert messages[1]["sources"]
    assert messages[1]["sources"] == response.json()["sources"]


def test_bastionbot_updated_conversation_moves_to_top_of_sidebar(
    client,
    auth_headers: dict[str, str],
):
    first = _chat(client, auth_headers, message="Explain the alerts workflow.")
    second = _chat(client, auth_headers, message="Explain the incidents workflow.")

    assert first.status_code == 200
    assert second.status_code == 200

    first_conversation_id = first.json()["conversationId"]
    second_conversation_id = second.json()["conversationId"]

    listed = client.get("/api/bastionbot/conversations", headers=auth_headers)
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["conversations"][:2]] == [
        second_conversation_id,
        first_conversation_id,
    ]

    follow_up = _chat(
        client,
        auth_headers,
        message="What should I inspect next on alerts?",
        conversation_id=first_conversation_id,
    )
    assert follow_up.status_code == 200

    relisted = client.get("/api/bastionbot/conversations", headers=auth_headers)
    assert relisted.status_code == 200
    assert relisted.json()["conversations"][0]["id"] == first_conversation_id


def test_bastionbot_memory_and_history_survive_store_reconfigure(client, auth_headers: dict[str, str]):
    created = _chat(client, auth_headers, message="How does FL Health work?")
    assert created.status_code == 200
    conversation_id = created.json()["conversationId"]

    follow_up = _chat(
        client,
        auth_headers,
        message="What should I look at next for federated learning?",
        conversation_id=conversation_id,
    )
    assert follow_up.status_code == 200

    db_path = settings.bastionbot_db_path
    bastionbot_store.configure(db_path)

    memory = bastionbot_store.get_user_memory("user-faheem")
    history = bastionbot_store.get_conversation_history("user-faheem", conversation_id)

    assert memory is not None
    assert memory.last_active_conversation_id == conversation_id
    assert memory.recent_topics
    assert history is not None
    assert [message.role for message in history] == ["USER", "BOT", "USER", "BOT"]


def test_bastionbot_chat_writes_audit_log_entry(client, auth_headers: dict[str, str]):
    before = len(state.audit_logs)

    response = _chat(client, auth_headers, message="Summarize the current audit workflow.")
    assert response.status_code == 200

    after = len(state.audit_logs)
    latest = state.audit_logs[-1]

    assert after == before + 1
    assert latest.actor == "user-faheem"
    assert latest.target == response.json()["conversationId"]
    assert "BastionBot ask-mode response generated" in latest.result


def test_bastionbot_engine_uses_local_fallback_when_groq_key_missing():
    original_key = settings.groq_api_key
    settings.groq_api_key = ""
    try:
        result = bastionbot_engine.answer(
            query="How does the audit verification feature work?",
            state=state,
            memory=None,
            history=[],
            context=None,
        )
    finally:
        settings.groq_api_key = original_key

    assert result.sources
    assert "grounded" in result.answer.lower()
    assert "**Sources**" in result.answer

