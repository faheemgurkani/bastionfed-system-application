from __future__ import annotations

import os

import httpx
import pytest


BASE_URL = os.getenv("LIVE_SERVER_URL")


pytestmark = pytest.mark.integration


@pytest.mark.skipif(not BASE_URL, reason="LIVE_SERVER_URL not set")
def test_live_bastionbot_chat_roundtrip():
    headers = {
        "Authorization": "Bearer test-token",
        "X-BastionFed-UID": "live-user-faheem",
        "Content-Type": "application/json",
    }

    with httpx.Client(base_url=BASE_URL, timeout=10.0) as client:
        chat = client.post(
            "/api/bastionbot/chat",
            headers=headers,
            json={"message": "Explain the audit verification feature."},
        )
        assert chat.status_code == 200
        body = chat.json()
        conversation_id = body["conversationId"]
        assert body["sources"]

        history = client.get(f"/api/bastionbot/conversations/{conversation_id}", headers=headers)
        assert history.status_code == 200
        messages = history.json()["messages"]
        assert len(messages) == 2
        assert messages[0]["role"] == "USER"
        assert messages[1]["role"] == "BOT"
