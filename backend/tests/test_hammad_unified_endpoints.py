from __future__ import annotations

import io

from fastapi.testclient import TestClient


def test_openapi_contains_hammad_paths_in_unified_backend(client: TestClient):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    paths = r.json().get("paths", {})

    must_have = (
        "/api/bastionbot/conversations/{conversation_id}",
        "/api/devices",
        "/api/devices/{device_id}",
        "/api/fl/drift",
        "/api/fl/models",
        "/api/forensics/rca",
        "/api/forensics/samples",
        "/api/incidents/{incident_id}",
        "/api/incidents/{incident_id}/playbook/steps/{step_id}",
        "/api/incidents/{incident_id}/playbook/halt",
        "/api/network/block-ip",
    )

    for p in must_have:
        assert p in paths, f"missing OpenAPI path {p}"


def test_hammad_get_endpoints_work_in_unified_backend(client: TestClient, auth_headers: dict[str, str]):
    assert client.get("/api/devices?dev=true").status_code == 200
    assert client.get("/api/devices/dev-01?dev=true").status_code == 200
    assert client.get("/api/fl/drift?dev=true").status_code == 200
    assert client.get("/api/fl/models?dev=true").status_code == 200
    assert client.get("/api/forensics/rca?dev=true").status_code == 200

    history = client.get("/api/bastionbot/conversations/conv-does-not-exist", headers=auth_headers)
    assert history.status_code == 404
    assert history.json()["detail"]["code"] == "CONVERSATION_NOT_FOUND"


def test_hammad_mutations_require_user_auth_in_unified_backend(client: TestClient, auth_headers: dict[str, str]):
    r = client.patch(
        "/api/incidents/INC-001?dev=true",
        json={"status": "RESPONDING", "assignee": "JP", "notes": "test"},
    )
    assert r.status_code == 403

    r2 = client.patch(
        "/api/incidents/INC-001",
        json={"status": "RESPONDING", "assignee": "JP", "notes": "test"},
    )
    assert r2.status_code == 401

    r3 = client.patch(
        "/api/incidents/INC-001",
        headers={**auth_headers, "Content-Type": "application/json"},
        json={"status": "RESPONDING", "assignee": "JP", "notes": "Escalated after confirmed lateral movement."},
    )
    assert r3.status_code == 200
    j = r3.json()
    assert j["status"] == "RESPONDING"
    assert j["assignee"] == "JP"


def test_patch_playbook_step_in_unified_backend(client: TestClient, auth_headers: dict[str, str]):
    r = client.patch(
        "/api/incidents/INC-001/playbook/steps/s6",
        headers={**auth_headers, "Content-Type": "application/json"},
        json={"status": "COMPLETED", "notes": "Test step completion"},
    )
    assert r.status_code == 200
    j = r.json()
    assert j["id"] == "s6"
    assert j["status"] == "COMPLETED"


def test_halt_playbook_stops_running_step_in_unified_backend(client: TestClient, auth_headers: dict[str, str]):
    client.post("/api/incidents/INC-001/playbook/run", headers=auth_headers)

    r = client.post(
        "/api/incidents/INC-001/playbook/halt",
        headers={**auth_headers, "Content-Type": "application/json"},
        json={"reason": "Manual override by analyst JP"},
    )
    assert r.status_code == 200
    j = r.json()
    assert j["halted"] is True
    assert j["stoppedAt"] == "s6"
    assert "haltedAt" in j


def test_forensics_upload_sample_in_unified_backend(client: TestClient, auth_headers: dict[str, str]):
    file_bytes = b"hello-forensics"
    files = {"file": ("sample.bin", io.BytesIO(file_bytes), "application/octet-stream")}
    r = client.post(
        "/api/forensics/samples",
        headers=auth_headers,
        files=files,
        data={"deviceId": "dev-02", "notes": "LockBit 3.0"},
    )
    assert r.status_code == 201
    j = r.json()
    assert j["sha256"]
    assert j["status"] in ("PENDING", "ANALYZING", "ANALYZED", "QUEUED")
    assert j["uploadTime"]


def test_forensics_generate_rca_in_unified_backend(client: TestClient, auth_headers: dict[str, str]):
    r = client.post(
        "/api/forensics/rca",
        headers={**auth_headers, "Content-Type": "application/json"},
        json={"incidentId": "INC-001"},
    )
    assert r.status_code == 201
    j = r.json()
    assert j["incidentId"] == "INC-001"
    assert "executiveSummary" in j


def test_block_ip_in_unified_backend(client: TestClient, auth_headers: dict[str, str]):
    r = client.post(
        "/api/network/block-ip",
        headers={**auth_headers, "Content-Type": "application/json"},
        json={"ip": "185.15.2.1", "reason": "Test block", "alertId": "ALT-0001"},
    )
    assert r.status_code == 200
    j = r.json()
    assert j["ip"] == "185.15.2.1"
    assert j["ruleId"].startswith("FW-RULE-")
    assert j["appliedAt"]


def test_devices_filters_in_unified_backend(client: TestClient):
    by_wing = client.get("/api/devices?dev=true&wing=ICU")
    assert by_wing.status_code == 200
    assert by_wing.json()["items"]
    assert all(d["wing"] == "ICU" for d in by_wing.json()["items"])

    by_status = client.get("/api/devices?dev=true&status=NORMAL")
    assert by_status.status_code == 200
    assert all(d["status"] == "NORMAL" for d in by_status.json()["items"])

    by_type = client.get("/api/devices?dev=true&type=MRI")
    assert by_type.status_code == 200
    assert all(d["type"] == "MRI" for d in by_type.json()["items"])


def test_fl_drift_and_models_shape_in_unified_backend(client: TestClient):
    drift = client.get("/api/fl/drift?dev=true")
    assert drift.status_code == 200
    body = drift.json()
    assert body.get("driftMethod") == "ROUND_ACCURACY_HEURISTIC"
    assert "driftMethodDescription" in body and body["documentationRef"]
    entries = body["entries"]
    assert isinstance(entries, list)
    assert entries
    for key in ("clientId", "department", "roundsAgo", "driftScore", "baselineAccuracy", "currentAccuracy", "flagged"):
        assert key in entries[0]

    models = client.get("/api/fl/models?dev=true")
    assert models.status_code == 200
    active = [m for m in models.json()["models"] if m["active"]]
    assert len(active) == 1
