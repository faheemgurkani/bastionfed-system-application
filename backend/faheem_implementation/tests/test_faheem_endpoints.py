"""Tests for Faheem-owned API surface (contracts in docs/BACKEND_PRD.md)."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from app.store.memory import state


def _detail_payload(res_json: dict[str, Any]) -> tuple[str | None, str | None]:
    """Normalize FastAPI HTTPException body: detail may be str or nested dict."""
    d = res_json.get("detail")
    if isinstance(d, dict):
        return d.get("detail"), d.get("code")
    if isinstance(d, str):
        return d, None
    return None, None


def test_health(client: TestClient):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_openapi_contains_faheem_paths(client: TestClient):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    paths = r.json().get("paths", {})
    for p in (
        "/api/alerts",
        "/api/incidents/{incident_id}",
        "/api/fl/status",
        "/api/fl/clients/{client_id}",
        "/api/forensics/samples",
        "/api/forensics/rca/{rca_id}",
        "/api/dashboard/kpis",
        "/api/auth/session",
        "/api/events",
        "/api/devices/{device_id}/quarantine",
        "/api/audit/verify",
    ):
        assert p in paths, f"missing OpenAPI path {p}"


# --- Alerts ---


def test_alerts_guest(client: TestClient):
    r = client.get("/api/alerts?guest=true")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 20
    assert len(body["items"]) <= 50
    assert "nextCursor" in body
    assert body["items"][0]["deviceId"]


def test_alerts_requires_auth(client: TestClient):
    assert client.get("/api/alerts").status_code == 401


def test_alerts_filter_by_status_open(client: TestClient):
    r = client.get("/api/alerts?guest=true&status=OPEN")
    assert r.status_code == 200
    for item in r.json()["items"]:
        assert item["status"] == "OPEN"


def test_alerts_filter_by_severity_critical(client: TestClient):
    r = client.get("/api/alerts?guest=true&severity=CRITICAL")
    assert r.status_code == 200
    assert all(a["severity"] == "CRITICAL" for a in r.json()["items"])


def test_alerts_pagination_cursor(client: TestClient):
    first = client.get("/api/alerts?guest=true&limit=5")
    assert first.status_code == 200
    b1 = first.json()
    assert len(b1["items"]) == 5
    assert b1["nextCursor"] is not None
    second = client.get(f"/api/alerts?guest=true&limit=5&cursor={b1['nextCursor']}")
    assert second.status_code == 200
    b2 = second.json()
    ids1 = {x["id"] for x in b1["items"]}
    ids2 = {x["id"] for x in b2["items"]}
    assert ids1.isdisjoint(ids2)


def test_alerts_sort_severity_desc(client: TestClient):
    r = client.get("/api/alerts?guest=true&sort=severity_desc")
    assert r.status_code == 200
    items = r.json()["items"]
    order = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
    severities = [order[x["severity"]] for x in items]
    assert severities == sorted(severities, reverse=True)


def test_patch_alert(client: TestClient, auth_headers: dict[str, str]):
    first_id = client.get("/api/alerts", headers=auth_headers).json()["items"][0]["id"]
    before = len(state.audit_logs)
    r = client.patch(
        f"/api/alerts/{first_id}",
        headers={**auth_headers, "Content-Type": "application/json"},
        json={"status": "RESOLVED"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "RESOLVED"
    assert len(state.audit_logs) >= before + 1
    last = state.audit_logs[-1]
    assert last.target == first_id
    assert "RESOLVED" in last.result


def test_patch_alert_404(client: TestClient, auth_headers: dict[str, str]):
    r = client.patch(
        "/api/alerts/ALT-NOT-REAL",
        headers={**auth_headers, "Content-Type": "application/json"},
        json={"status": "RESOLVED"},
    )
    assert r.status_code == 404
    msg, code = _detail_payload(r.json())
    assert code == "ALERT_NOT_FOUND"


def test_patch_alert_invalid_status(client: TestClient, auth_headers: dict[str, str]):
    first_id = client.get("/api/alerts", headers=auth_headers).json()["items"][0]["id"]
    r = client.patch(
        f"/api/alerts/{first_id}",
        headers={**auth_headers, "Content-Type": "application/json"},
        json={"status": "NOT_A_STATUS"},
    )
    assert r.status_code == 400
    msg, code = _detail_payload(r.json())
    assert code == "INVALID_STATUS"


def test_patch_alert_guest_forbidden(client: TestClient):
    first_id = client.get("/api/alerts?guest=true").json()["items"][0]["id"]
    r = client.patch(
        f"/api/alerts/{first_id}?guest=true",
        json={"status": "RESOLVED"},
    )
    assert r.status_code == 403


def test_patch_alert_requires_bearer(client: TestClient):
    first_id = client.get("/api/alerts?guest=true").json()["items"][0]["id"]
    r = client.patch(
        f"/api/alerts/{first_id}",
        json={"status": "RESOLVED"},
    )
    assert r.status_code == 401


# --- Incidents ---


def test_incident_detail(client: TestClient):
    r = client.get("/api/incidents/INC-001?guest=true")
    assert r.status_code == 200
    j = r.json()
    assert j["id"] == "INC-001"
    assert "playbook" in j and "timeline" in j and "affectedDevices" in j


def test_incident_404(client: TestClient):
    r = client.get("/api/incidents/INC-999?guest=true")
    assert r.status_code == 404
    assert _detail_payload(r.json())[1] == "INCIDENT_NOT_FOUND"


# --- FL ---


def test_fl_status_shape(client: TestClient):
    r = client.get("/api/fl/status?guest=true")
    assert r.status_code == 200
    j = r.json()
    for key in (
        "currentRound",
        "totalRounds",
        "activeClients",
        "totalClients",
        "nextRoundIn",
        "aggregatorStatus",
        "latestAccuracy",
        "latestFpRate",
        "driftDetected",
    ):
        assert key in j, f"missing {key}"


def test_fl_client(client: TestClient):
    r = client.get("/api/fl/clients/Cardiology-FL-01?guest=true")
    assert r.status_code == 200
    assert r.json()["department"] == "Cardiology"


def test_fl_client_404(client: TestClient):
    r = client.get("/api/fl/clients/no-such-client?guest=true")
    assert r.status_code == 404
    assert _detail_payload(r.json())[1] == "FL_CLIENT_NOT_FOUND"


# --- Forensics ---


def test_forensics_samples(client: TestClient):
    r = client.get("/api/forensics/samples?guest=true")
    assert r.status_code == 200
    assert r.json()["total"] == 3


def test_forensics_samples_filter_status(client: TestClient):
    r = client.get("/api/forensics/samples?guest=true&status=ANALYZED")
    assert r.status_code == 200
    assert all(s["status"] == "ANALYZED" for s in r.json()["items"])


def test_forensics_samples_family_filter(client: TestClient):
    r = client.get("/api/forensics/samples?guest=true&family=LockBit%203.0")
    assert r.status_code == 200
    assert len(r.json()["items"]) >= 1
    assert all("LockBit" in s["family"] for s in r.json()["items"])


def test_rca_detail(client: TestClient):
    r = client.get("/api/forensics/rca/RCA-001?guest=true")
    assert r.status_code == 200
    j = r.json()
    assert "executiveSummary" in j
    assert j["incidentId"] == "INC-001"


def test_rca_404(client: TestClient):
    r = client.get("/api/forensics/rca/RCA-999?guest=true")
    assert r.status_code == 404
    assert _detail_payload(r.json())[1] == "RCA_NOT_FOUND"


# --- Dashboard & auth ---


def test_dashboard_kpis_shape(client: TestClient):
    r = client.get("/api/dashboard/kpis?guest=true")
    assert r.status_code == 200
    j = r.json()
    for key in (
        "activeThreats",
        "avgConfidence",
        "devicesUnderWatch",
        "flRound",
        "openIncidents",
        "criticalAlerts",
        "resolvedToday",
        "falsePositiveRate",
    ):
        assert key in j


def test_auth_session(client: TestClient, auth_headers: dict[str, str]):
    before = len(state.audit_logs)
    r = client.post(
        "/api/auth/session",
        headers={**auth_headers, "Content-Type": "application/json"},
        json={
            "uid": "test-user-1",
            "email": "a@b.org",
            "displayName": "Tester",
            "photoURL": None,
        },
    )
    assert r.status_code == 200
    j = r.json()
    assert j["uid"] == "test-user-1"
    assert "createdAt" in j and "lastLoginAt" in j
    assert len(state.audit_logs) >= before + 1


def test_auth_session_requires_bearer(client: TestClient):
    r = client.post(
        "/api/auth/session",
        json={"uid": "x", "email": "e@e.com", "displayName": "E", "photoURL": None},
    )
    assert r.status_code == 401


def test_auth_session_guest_forbidden(client: TestClient):
    r = client.post(
        "/api/auth/session?guest=true",
        json={"uid": "x", "email": None, "displayName": None, "photoURL": None},
    )
    assert r.status_code == 403


# --- Devices ---


def test_quarantine(client: TestClient, auth_headers: dict[str, str]):
    r = client.post("/api/devices/dev-03/quarantine", headers=auth_headers)
    assert r.status_code == 200
    j = r.json()
    assert j["status"] == "ISOLATED"
    assert j["deviceId"] == "dev-03"
    assert "commandId" in j and "sentAt" in j
    dev = client.get("/api/alerts", headers=auth_headers).json()["items"]
    for a in dev:
        if a["deviceId"] == "dev-03":
            assert a["device"]["status"] == "ISOLATED"
            break


def test_quarantine_404(client: TestClient, auth_headers: dict[str, str]):
    r = client.post("/api/devices/dev-999/quarantine", headers=auth_headers)
    assert r.status_code == 404
    assert _detail_payload(r.json())[1] == "DEVICE_NOT_FOUND"


def test_quarantine_appends_incident_timeline(client: TestClient, auth_headers: dict[str, str]):
    """INC-001 includes dev-02; quarantine should append QUARANTINE timeline event."""
    r = client.post("/api/devices/dev-02/quarantine", headers=auth_headers)
    assert r.status_code == 200
    inc = client.get("/api/incidents/INC-001?guest=true").json()
    assert any(e["type"] == "QUARANTINE" for e in inc["timeline"])


# --- Audit ---


def test_audit_verify(client: TestClient):
    r = client.get("/api/audit/verify?guest=true")
    assert r.status_code == 200
    b = r.json()
    assert b["valid"] is True
    assert "totalLogs" in b and "checkedAt" in b


def test_audit_verify_detects_tamper(client: TestClient):
    if state.audit_logs:
        log = state.audit_logs[0]
        state.audit_logs[0] = log.model_copy(update={"hash": "deadbeef"})
    r = client.get("/api/audit/verify?guest=true")
    assert r.status_code == 200
    body = r.json()
    assert body["valid"] is False
    assert "firstBreakAt" in body


# --- SSE ---
# Infinite streams are awkward under ASGI test clients (body draining / aread can hang across
# httpx/Starlette versions). We assert gated access here; OpenAPI registers `/api/events`.
# Manual smoke: `curl -N --max-time 2 'http://localhost:8000/api/events?guest=true'`


def test_events_unauthenticated(client: TestClient):
    assert client.get("/api/events").status_code == 401

