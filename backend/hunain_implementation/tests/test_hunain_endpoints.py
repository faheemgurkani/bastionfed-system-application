from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.store.memory import state
from app.main import app


def _detail_payload(res_json: dict[str, Any]) -> tuple[str | None, str | None]:
    d = res_json.get("detail")
    if isinstance(d, dict):
        return d.get("detail"), d.get("code")
    if isinstance(d, str):
        return d, None
    return None, None


@pytest.fixture
def seeded_ids() -> dict[str, str]:
    # state is reset per test by conftest
    return {
        "alert_id": state.alerts[0].id,
        "incident_id": state.incidents[0].id,
        "sample_id": state.malware_samples[0].id,
        "conversation_id": state.conversations[0].id,
    }


def test_openapi_only_hunain_paths(client: TestClient):
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
        "/api/bastionbot/chat",
        "/api/audit/logs",
    )

    for p in required:
        assert p in paths, f"missing OpenAPI path {p}"

    forbidden = (
        "/api/events",
        "/api/auth/session",
        "/api/dashboard/kpis",
        "/api/devices/{device_id}/quarantine",
        "/api/alerts",
        "/api/alerts/{alert_id}#PATCH",  # not a real OpenAPI key; just a guard for accidental regressions
        "/api/fl/status",
        "/api/fl/clients/{client_id}",
        "/api/forensics/samples",
        "/api/forensics/rca/{rca_id}",
        "/api/audit/verify",
        "/api/incidents/{incident_id}",
    )

    for p in forbidden:
        # Only check the ones that actually exist as real paths in OpenAPI.
        if "#" in p:
            continue
        assert p not in paths, f"found forbidden OpenAPI path {p}"


def test_read_endpoints_allow_guest(client: TestClient, seeded_ids: dict[str, str]):
    ids = seeded_ids
    assert client.get(f"/api/alerts/{ids['alert_id']}?guest=true").status_code == 200
    assert client.get("/api/incidents?guest=true").status_code == 200
    assert client.get("/api/fl/rounds?guest=true").status_code == 200
    assert client.get("/api/fl/clients?guest=true").status_code == 200
    assert client.get(f"/api/forensics/samples/{ids['sample_id']}?guest=true").status_code == 200
    assert client.get("/api/bastionbot/conversations?guest=true").status_code == 200
    assert client.get("/api/audit/logs?guest=true").status_code == 200


def test_sse_requires_auth(client: TestClient):
    assert client.get("/api/fl-events").status_code == 401


def test_mutations_require_user_auth(client: TestClient, seeded_ids: dict[str, str]):
    ids = seeded_ids
    # guest=true should be forbidden on mutations
    assert client.post(f"/api/alerts/{ids['alert_id']}/escalate?guest=true").status_code == 403
    assert client.post(f"/api/incidents/{ids['incident_id']}/playbook/run?guest=true").status_code == 403
    assert client.post("/api/fl/models/v4.2.1-DNN/activate?guest=true").status_code == 403
    assert (
        client.post(
            "/api/bastionbot/chat?guest=true",
            json={"message": "hi", "conversationId": ids["conversation_id"]},
        ).status_code
        == 403
    )


def test_bastionbot_chat_with_bearer(client: TestClient, auth_headers: dict[str, str], seeded_ids: dict[str, str]):
    ids = seeded_ids
    r = client.post(
        "/api/bastionbot/chat",
        headers=auth_headers,
        json={
            "message": "Hello",
            "conversationId": ids["conversation_id"],
            "context": {"alertId": ids["alert_id"]},
        },
    )
    assert r.status_code == 200
    j = r.json()
    assert "message" in j
    assert j["conversationId"] == ids["conversation_id"]
    assert j["message"]["role"] in ("USER", "BOT")


def test_escalate_creates_incident(client: TestClient, auth_headers: dict[str, str], seeded_ids: dict[str, str]):
    ids = seeded_ids
    r = client.post(
        f"/api/alerts/{ids['alert_id']}/escalate",
        headers=auth_headers,
    )
    assert r.status_code == 200
    j = r.json()
    assert "incident" in j
    assert j["incident"]["id"] is not None


def test_playbook_run(client: TestClient, auth_headers: dict[str, str], seeded_ids: dict[str, str]):
    ids = seeded_ids
    r = client.post(
        f"/api/incidents/{ids['incident_id']}/playbook/run",
        headers=auth_headers,
    )
    assert r.status_code == 200
    j = r.json()
    assert j["incidentId"] == ids["incident_id"]
    assert "playbookId" in j
    assert "startedAt" in j
    assert "currentStep" in j


def test_activate_model(client: TestClient, auth_headers: dict[str, str]):
    r = client.post(
        "/api/fl/models/v4.2.1-DNN/activate",
        headers=auth_headers,
    )
    assert r.status_code == 200
    j = r.json()
    assert j["activated"] == "v4.2.1-DNN"
    assert "previouslyActive" in j
    assert "switchedAt" in j


def test_audit_logs_shape(client: TestClient, seeded_ids: dict[str, str]):
    # guest is allowed on read endpoints
    r = client.get("/api/audit/logs?guest=true&limit=5")
    assert r.status_code == 200
    j = r.json()
    assert "items" in j
    assert isinstance(j["items"], list)
    assert "nextCursor" in j
    assert "total" in j


def test_read_endpoints_require_auth_without_guest(client: TestClient, seeded_ids: dict[str, str]):
    ids = seeded_ids
    assert client.get(f"/api/alerts/{ids['alert_id']}").status_code == 401
    assert client.get("/api/incidents").status_code == 401
    assert client.get("/api/fl/rounds").status_code == 401
    assert client.get("/api/fl/clients").status_code == 401
    assert client.get(f"/api/forensics/samples/{ids['sample_id']}").status_code == 401
    assert client.get("/api/bastionbot/conversations").status_code == 401
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
    b1 = first.json()
    assert len(b1["items"]) == 2
    assert b1["nextCursor"] is not None

    second = client.get(f"/api/incidents?guest=true&limit=2&cursor={b1['nextCursor']}")
    assert second.status_code == 200
    b2 = second.json()
    ids1 = {x["id"] for x in b1["items"]}
    ids2 = {x["id"] for x in b2["items"]}
    assert ids1.isdisjoint(ids2)


def test_audit_logs_filter_actor(client: TestClient):
    r = client.get("/api/audit/logs?guest=true&actor=BastionFed%20System")
    assert r.status_code == 200
    j = r.json()
    for item in j["items"]:
        assert item["actor"] == "BastionFed System"


def test_audit_logs_filter_action(client: TestClient):
    r = client.get("/api/audit/logs?guest=true&action=DETECTION_MADE")
    assert r.status_code == 200
    j = r.json()
    for item in j["items"]:
        assert item["action"] == "DETECTION_MADE"


def test_audit_logs_cursor_and_limit(client: TestClient):
    first = client.get("/api/audit/logs?guest=true&limit=3")
    assert first.status_code == 200
    b1 = first.json()
    assert len(b1["items"]) == 3
    assert b1["nextCursor"] is not None

    second = client.get(f"/api/audit/logs?guest=true&limit=3&cursor={b1['nextCursor']}")
    assert second.status_code == 200
    b2 = second.json()
    ids1 = {x["id"] for x in b1["items"]}
    ids2 = {x["id"] for x in b2["items"]}
    assert ids1.isdisjoint(ids2)


def test_escalate_404(client: TestClient, auth_headers: dict[str, str]):
    r = client.post("/api/alerts/ALT-NOT-REAL/escalate", headers=auth_headers)
    assert r.status_code == 404
    assert _detail_payload(r.json())[1] == "ALERT_NOT_FOUND"


def test_escalate_sets_alert_in_review(client: TestClient, auth_headers: dict[str, str], seeded_ids: dict[str, str]):
    alert_id = seeded_ids["alert_id"]
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


def test_chat_requires_bearer(client: TestClient, seeded_ids: dict[str, str]):
    r = client.post(
        "/api/bastionbot/chat",
        json={"message": "hello", "conversationId": seeded_ids["conversation_id"]},
    )
    assert r.status_code == 401


def test_chat_validation_error(client: TestClient, auth_headers: dict[str, str]):
    r = client.post("/api/bastionbot/chat", headers=auth_headers, json={"conversationId": "conv-1"})
    assert r.status_code == 422

