from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from app.bastionbot import bastionbot_store
from app.store.memory import state


def _detail_payload(res_json: dict[str, Any]) -> tuple[str | None, str | None]:
    d = res_json.get("detail")
    if isinstance(d, dict):
        return d.get("detail"), d.get("code")
    if isinstance(d, str):
        return d, None
    return None, None


def _seeded_ids() -> dict[str, str]:
    return {
        "alert_id": state.alerts[0].id,
        "incident_id": state.incidents[0].id,
        "sample_id": state.malware_samples[0].id,
    }


def _create_chat(
    client: TestClient,
    headers: dict[str, str],
    *,
    message: str,
    conversation_id: str | None = None,
    context: dict[str, str | None] | None = None,
):
    payload: dict[str, Any] = {"message": message}
    if conversation_id is not None:
        payload["conversationId"] = conversation_id
    if context is not None:
        payload["context"] = context
    return client.post("/api/bastionbot/chat", headers=headers, json=payload)


def test_openapi_contains_unified_bastionbot_paths(client: TestClient):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    paths = r.json().get("paths", {})

    required = (
        "/api/alerts/{alert_id}",
        "/api/alerts/{alert_id}/escalate",
        "/api/incidents",
        "/api/incidents/{incident_id}/playbook/run",
        "/api/fl/rounds",
        "/api/fl/clients",
        "/api/fl-events",
        "/api/fl/models/{model_name}/activate",
        "/api/forensics/samples/{sample_id}",
        "/api/bastionbot/conversations",
        "/api/bastionbot/conversations/{conversation_id}",
        "/api/bastionbot/chat",
        "/api/audit/logs",
    )

    for p in required:
        assert p in paths, f"missing OpenAPI path {p}"


def test_guest_read_endpoints_still_work_for_non_bastionbot_routes(client: TestClient):
    ids = _seeded_ids()
    assert client.get(f"/api/alerts/{ids['alert_id']}?guest=true").status_code == 200
    assert client.get("/api/incidents?guest=true").status_code == 200
    assert client.get("/api/fl/rounds?guest=true").status_code == 200
    assert client.get("/api/fl/clients?guest=true").status_code == 200
    assert client.get(f"/api/forensics/samples/{ids['sample_id']}?guest=true").status_code == 200
    assert client.get("/api/audit/logs?guest=true").status_code == 200


def test_bastionbot_routes_require_signed_in_user(client: TestClient):
    assert client.get("/api/bastionbot/conversations").status_code == 401
    assert client.get("/api/bastionbot/conversations?guest=true").status_code == 403
    assert client.post("/api/bastionbot/chat?guest=true", json={"message": "hi"}).status_code == 403


def test_bastionbot_requires_uid_header(client: TestClient):
    r = client.post(
        "/api/bastionbot/chat",
        headers={"Authorization": "Bearer test-token"},
        json={"message": "Explain the alert workflow"},
    )
    assert r.status_code == 400
    assert _detail_payload(r.json())[1] == "BASTIONBOT_UID_REQUIRED"


def test_bastionbot_creates_new_conversation_when_id_omitted(client: TestClient, auth_headers: dict[str, str]):
    ids = _seeded_ids()
    r = _create_chat(
        client,
        auth_headers,
        message="What does this alert mean?",
        context={"alertId": ids["alert_id"], "incidentId": None},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["conversationId"].startswith("conv_")
    assert body["conversation"]["title"]
    assert body["conversation"]["messageCount"] == 2
    assert body["message"]["role"] == "BOT"
    assert "Groq-backed BastionBot answer" in body["message"]["content"]
    assert isinstance(body["sources"], list)
    assert "Sources:" in body["message"]["content"]


def test_bastionbot_history_append_and_order(client: TestClient, auth_headers: dict[str, str]):
    first = _create_chat(client, auth_headers, message="Explain the audit screen.")
    conversation_id = first.json()["conversationId"]

    second = _create_chat(client, auth_headers, message="What about verification?", conversation_id=conversation_id)
    assert second.status_code == 200
    assert second.json()["memoryUsed"] is True

    history = client.get(f"/api/bastionbot/conversations/{conversation_id}", headers=auth_headers)
    assert history.status_code == 200
    messages = history.json()["messages"]
    assert [m["role"] for m in messages] == ["USER", "BOT", "USER", "BOT"]
    assert messages[0]["content"] == "Explain the audit screen."
    assert messages[-1]["role"] == "BOT"


def test_bastionbot_conversation_list_is_user_scoped(client: TestClient, auth_headers: dict[str, str], other_auth_headers: dict[str, str]):
    created = _create_chat(client, auth_headers, message="Summarize the current incidents workflow.")
    conversation_id = created.json()["conversationId"]

    own_list = client.get("/api/bastionbot/conversations", headers=auth_headers)
    assert own_list.status_code == 200
    assert own_list.json()["conversations"][0]["id"] == conversation_id

    other_list = client.get("/api/bastionbot/conversations", headers=other_auth_headers)
    assert other_list.status_code == 200
    assert other_list.json()["conversations"] == []

    foreign_history = client.get(f"/api/bastionbot/conversations/{conversation_id}", headers=other_auth_headers)
    assert foreign_history.status_code == 404
    assert _detail_payload(foreign_history.json())[1] == "CONVERSATION_NOT_FOUND"


def test_bastionbot_sqlite_persists_across_state_reset(client: TestClient, auth_headers: dict[str, str]):
    created = _create_chat(client, auth_headers, message="How does FL Health work?")
    conversation_id = created.json()["conversationId"]

    state.reset()

    history = client.get(f"/api/bastionbot/conversations/{conversation_id}", headers=auth_headers)
    assert history.status_code == 200
    assert len(history.json()["messages"]) == 2


def test_bastionbot_live_data_grounding_for_alerts(client: TestClient, auth_headers: dict[str, str]):
    alert_id = _seeded_ids()["alert_id"]
    r = _create_chat(
        client,
        auth_headers,
        message=f"What is the current status of {alert_id}?",
        context={"alertId": alert_id, "incidentId": None},
    )
    assert r.status_code == 200
    body = r.json()
    assert alert_id in body["message"]["content"]
    assert any(source["sourceType"] == "live_data" for source in body["sources"])


def test_bastionbot_docs_grounding_for_product_help(client: TestClient, auth_headers: dict[str, str]):
    r = _create_chat(client, auth_headers, message="How does the audit verification feature work in BastionFed?")
    assert r.status_code == 200
    body = r.json()
    assert body["sources"]
    assert any(source["sourceType"] in ("doc", "ui", "api") for source in body["sources"])
    assert "Sources" in body["message"]["content"]


def test_bastionbot_unknown_query_returns_safe_fallback(client: TestClient, auth_headers: dict[str, str]):
    r = _create_chat(client, auth_headers, message="Explain the orbital strawberry compiler for quantum opera.")
    assert r.status_code == 200
    assert "could not ground" in r.json()["message"]["content"].lower()


def test_bastionbot_updates_user_memory_topics(client: TestClient, auth_headers: dict[str, str]):
    first = _create_chat(client, auth_headers, message="How does the incidents screen work?")
    assert first.status_code == 200

    second = _create_chat(
        client,
        auth_headers,
        message="What about playbook execution?",
        conversation_id=first.json()["conversationId"],
    )
    assert second.status_code == 200
    assert second.json()["memoryUsed"] is True

    memory = bastionbot_store.get_user_memory("user-faheem")
    assert memory is not None
    assert memory.last_active_conversation_id == first.json()["conversationId"]
    assert memory.recent_topics


def test_bastionbot_chat_requires_bearer(client: TestClient):
    r = client.post("/api/bastionbot/chat", json={"message": "hello"})
    assert r.status_code == 401


def test_bastionbot_chat_validation_error(client: TestClient, auth_headers: dict[str, str]):
    r = client.post("/api/bastionbot/chat", headers=auth_headers, json={"conversationId": "conv-1"})
    assert r.status_code == 422


def test_sse_requires_auth(client: TestClient):
    assert client.get("/api/fl-events").status_code == 401


def test_mutations_require_user_auth(client: TestClient):
    ids = _seeded_ids()
    assert client.post(f"/api/alerts/{ids['alert_id']}/escalate?guest=true").status_code == 403
    assert client.post(f"/api/incidents/{ids['incident_id']}/playbook/run?guest=true").status_code == 403
    assert client.post("/api/fl/models/v4.2.1-DNN/activate?guest=true").status_code == 403


def test_escalate_creates_incident(client: TestClient, auth_headers: dict[str, str]):
    alert_id = _seeded_ids()["alert_id"]
    r = client.post(f"/api/alerts/{alert_id}/escalate", headers=auth_headers)
    assert r.status_code == 200
    assert "incident" in r.json()


def test_playbook_run(client: TestClient, auth_headers: dict[str, str]):
    incident_id = _seeded_ids()["incident_id"]
    r = client.post(f"/api/incidents/{incident_id}/playbook/run", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["incidentId"] == incident_id


def test_activate_model(client: TestClient, auth_headers: dict[str, str]):
    r = client.post("/api/fl/models/v4.2.1-DNN/activate", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["activated"] == "v4.2.1-DNN"


def test_audit_logs_shape(client: TestClient):
    r = client.get("/api/audit/logs?guest=true&limit=5")
    assert r.status_code == 200
    j = r.json()
    assert "items" in j and isinstance(j["items"], list)
    assert "nextCursor" in j
    assert "total" in j


def test_read_endpoints_require_auth_without_guest(client: TestClient):
    ids = _seeded_ids()
    assert client.get(f"/api/alerts/{ids['alert_id']}").status_code == 401
    assert client.get("/api/incidents").status_code == 401
    assert client.get("/api/fl/rounds").status_code == 401
    assert client.get("/api/fl/clients").status_code == 401
    assert client.get(f"/api/forensics/samples/{ids['sample_id']}").status_code == 401
    assert client.get("/api/audit/logs").status_code == 401


def test_alert_detail_404(client: TestClient):
    r = client.get("/api/alerts/ALT-NOT-REAL?guest=true")
    assert r.status_code == 404
    assert _detail_payload(r.json())[1] == "ALERT_NOT_FOUND"


def test_sample_detail_404(client: TestClient):
    r = client.get("/api/forensics/samples/MAL-NOT-REAL?guest=true")
    assert r.status_code == 404
    assert _detail_payload(r.json())[1] == "SAMPLE_NOT_FOUND"


def test_incidents_pagination_and_cursor(client: TestClient):
    first = client.get("/api/incidents?guest=true&limit=2")
    assert first.status_code == 200
    body = first.json()
    assert len(body["items"]) == 2
    assert body["nextCursor"] is not None

    second = client.get(f"/api/incidents?guest=true&limit=2&cursor={body['nextCursor']}")
    assert second.status_code == 200
    ids1 = {x["id"] for x in body["items"]}
    ids2 = {x["id"] for x in second.json()["items"]}
    assert ids1.isdisjoint(ids2)


def test_audit_logs_filter_actor(client: TestClient):
    r = client.get("/api/audit/logs?guest=true&actor=BastionFed%20System")
    assert r.status_code == 200
    for item in r.json()["items"]:
        assert item["actor"] == "BastionFed System"


def test_audit_logs_filter_action(client: TestClient):
    r = client.get("/api/audit/logs?guest=true&action=DETECTION_MADE")
    assert r.status_code == 200
    for item in r.json()["items"]:
        assert item["action"] == "DETECTION_MADE"


def test_audit_logs_cursor_and_limit(client: TestClient):
    first = client.get("/api/audit/logs?guest=true&limit=3")
    assert first.status_code == 200
    body = first.json()
    assert len(body["items"]) == 3
    assert body["nextCursor"] is not None

    second = client.get(f"/api/audit/logs?guest=true&limit=3&cursor={body['nextCursor']}")
    assert second.status_code == 200
    ids1 = {x["id"] for x in body["items"]}
    ids2 = {x["id"] for x in second.json()["items"]}
    assert ids1.isdisjoint(ids2)


def test_escalate_404(client: TestClient, auth_headers: dict[str, str]):
    r = client.post("/api/alerts/ALT-NOT-REAL/escalate", headers=auth_headers)
    assert r.status_code == 404
    assert _detail_payload(r.json())[1] == "ALERT_NOT_FOUND"


def test_escalate_sets_alert_in_review(client: TestClient, auth_headers: dict[str, str]):
    alert_id = _seeded_ids()["alert_id"]
    r = client.post(f"/api/alerts/{alert_id}/escalate", headers=auth_headers)
    assert r.status_code == 200
    detail = client.get(f"/api/alerts/{alert_id}?guest=true")
    assert detail.status_code == 200
    assert detail.json()["status"] == "IN_REVIEW"


def test_playbook_run_404(client: TestClient, auth_headers: dict[str, str]):
    r = client.post("/api/incidents/INC-NOT-REAL/playbook/run", headers=auth_headers)
    assert r.status_code == 404
    assert _detail_payload(r.json())[1] == "INCIDENT_NOT_FOUND"


def test_activate_model_404(client: TestClient, auth_headers: dict[str, str]):
    r = client.post("/api/fl/models/does-not-exist/activate", headers=auth_headers)
    assert r.status_code == 404
    assert _detail_payload(r.json())[1] == "MODEL_NOT_FOUND"
