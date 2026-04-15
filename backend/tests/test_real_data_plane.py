from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import settings
from app.store.tenant_store import tenant_store


def _demo_device_id() -> str:
    return tenant_store.list_devices(settings.demo_tenant_id)[0].id


def _move_user_to_private_tenant(firebase_uid: str) -> str:
    memberships = getattr(tenant_store, "memberships", None)
    assert isinstance(memberships, list)
    target = f"tenant-{firebase_uid}"
    for membership in memberships:
        if membership["firebase_uid"] == firebase_uid:
            membership["is_default"] = membership["tenant_id"] == target
    return target


def test_ingest_source_admin_and_idempotent_ingest(client: TestClient, auth_headers: dict[str, str]):
    create = client.post(
        "/api/ingest/sources",
        headers=auth_headers,
        json={"name": "Primary SIEM", "sourceType": "siem", "connectorKind": "webhook"},
    )
    assert create.status_code == 201
    payload = create.json()
    source_id = payload["source"]["id"]
    secret = payload["secret"]
    assert secret

    event = {
        "sourceId": source_id,
        "externalId": "evt-001",
        "eventType": "alert",
        "payload": {
            "alertId": "ALT-ING-001",
            "deviceId": "DEV-ING-001",
            "deviceName": "SIEM Edge Node",
            "ip": "10.10.10.5",
            "severity": "HIGH",
            "summary": "Suspicious outbound beacon",
        },
    }
    first = client.post("/api/ingest/events", headers={"X-BastionFed-Ingest-Key": secret}, json=event)
    assert first.status_code == 202
    assert first.json()["result"]["parseStatus"] == "ACCEPTED"

    second = client.post("/api/ingest/events", headers={"X-BastionFed-Ingest-Key": secret}, json=event)
    assert second.status_code == 202
    assert second.json()["result"]["parseStatus"] == "DUPLICATE"

    alerts = client.get("/api/alerts", headers=auth_headers)
    assert alerts.status_code == 200
    ingested = next(item for item in alerts.json()["items"] if item["id"] == "ALT-ING-001")
    assert ingested["sourceType"] == "SIEM"
    assert ingested["isDemo"] is False


def test_cross_tenant_ingest_isolated(client: TestClient, auth_headers: dict[str, str], other_auth_headers: dict[str, str]):
    other_tenant_id = _move_user_to_private_tenant("user-hunain")

    create = client.post(
        "/api/ingest/sources",
        headers=other_auth_headers,
        json={"name": "Other Tenant EDR", "sourceType": "edr", "connectorKind": "webhook"},
    )
    assert create.status_code == 201
    source_id = create.json()["source"]["id"]
    secret = create.json()["secret"]

    event = {
        "sourceId": source_id,
        "externalId": "evt-other-001",
        "eventType": "alert",
        "payload": {"alertId": "ALT-OTHER-001", "deviceId": "DEV-OTHER-001", "severity": "MEDIUM"},
    }
    accepted = client.post("/api/ingest/events", headers={"X-BastionFed-Ingest-Key": secret}, json=event)
    assert accepted.status_code == 202

    demo_alerts = client.get("/api/alerts", headers=auth_headers)
    assert all(item["id"] != "ALT-OTHER-001" for item in demo_alerts.json()["items"])

    other_alerts = client.get("/api/alerts", headers=other_auth_headers)
    assert other_alerts.status_code == 200
    assert any(item["id"] == "ALT-OTHER-001" for item in other_alerts.json()["items"])
    assert accepted.json()["result"]["tenantId"] == other_tenant_id


def test_forensics_lifecycle_and_expired_download_block(client: TestClient, auth_headers: dict[str, str]):
    upload = client.post(
        "/api/forensics/samples",
        headers=auth_headers,
        data={"deviceId": _demo_device_id()},
        files={"file": ("probe.bin", b"malware-bytes", "application/octet-stream")},
    )
    assert upload.status_code == 201
    sample_id = upload.json()["id"]

    scanned = client.post(f"/api/forensics/samples/{sample_id}/scan", headers=auth_headers)
    assert scanned.status_code == 200
    assert scanned.json()["scanStatus"] == "SCANNED"

    quarantined = client.post(f"/api/forensics/samples/{sample_id}/quarantine", headers=auth_headers)
    assert quarantined.status_code == 200
    assert quarantined.json()["quarantineStatus"] == "QUARANTINED"

    released = client.post(f"/api/forensics/samples/{sample_id}/release", headers=auth_headers)
    assert released.status_code == 200
    assert released.json()["quarantineStatus"] == "RELEASED"

    expired = client.post(f"/api/forensics/samples/{sample_id}/expire", headers=auth_headers)
    assert expired.status_code == 200
    assert expired.json()["retentionStatus"] == "EXPIRED"

    denied = client.get(f"/api/forensics/samples/{sample_id}/signed-download-url", headers=auth_headers)
    assert denied.status_code == 410
    assert denied.json()["detail"]["code"] == "SAMPLE_EXPIRED"


def test_audit_export_and_fl_honesty_labels(client: TestClient):
    export = client.get("/api/audit/export?dev=true&format=jsonl")
    assert export.status_code == 200
    assert "DETECTION_MADE" in export.text or "USER_LOGIN" in export.text

    drift = client.get("/api/fl/drift?dev=true")
    assert drift.status_code == 200
    assert drift.json()["scope"] == "DEMO_RESEARCH"

    clients = client.get("/api/fl/drift/clients?dev=true")
    assert clients.status_code == 200
    assert clients.json()["scope"] == "DEMO_RESEARCH"
    assert clients.json()["message"]
