from __future__ import annotations

import base64
import hashlib
import json
import random
import secrets
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Json

from app.config import settings
from app.db.connect_params import pg_app_connect_kwargs
from app.models.domain import (
    Alert,
    AlertStatus,
    AuditAction,
    AuditLog,
    AffectedNode,
    Device,
    DeviceStatus,
    DynamicAnalysis,
    FLClient,
    FLClientStatus,
    FLClientType,
    FLRound,
    IngestEventResult,
    IngestSource,
    Incident,
    IncidentEvent,
    IncidentStatus,
    MalwareSample,
    Playbook,
    RCAReport,
    SampleAnalysis,
    Severity,
    StaticAnalysis,
    TimelineNode,
    UserRecord,
)
from app.services.forensics_pipeline import scan_sample as scan_forensics_sample
from app.services.supabase_storage import upload_forensics_bytes
from app.store import seed_data
from app.store.memory import AppState


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _camel_enum_str(value: Any) -> str:
    """CamelModel sets use_enum_values=True; enum fields are often plain str on instances."""
    if isinstance(value, str):
        return value
    return str(getattr(value, "value", value))


def _fl_drift_semantics_overlay() -> dict[str, Any]:
    """Unified runtime drift is round-accuracy heuristic, not Hunain z-score FV drift; see docs/ML_DRIFT_SEMANTICS.md."""
    return {
        "driftMethod": "ROUND_ACCURACY_HEURISTIC",
        "driftMethodDescription": (
            "Per-client driftScore uses federated round accuracy delta (baseline vs latest, with a six-round "
            "lookback when available) plus a small heuristic offset; clients in DEGRADED or POISONING_SUSPECT "
            "status receive a larger bump. This is not z-score feature-vector drift against a reference distribution."
        ),
        "zScoreFvDriftNote": (
            "Mean |z-score| style FV drift exists only in the optional Hunain reference implementation "
            "(backend/hunain_implementation/app/ml/drift.py), not in this unified API runtime."
        ),
        "documentationRef": "docs/ML_DRIFT_SEMANTICS.md",
    }


def _norm_iso(ts: str) -> datetime:
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return datetime.fromisoformat(ts)


def _encode_cursor(index: int) -> str:
    return base64.urlsafe_b64encode(json.dumps({"i": index}).encode()).decode()


def _decode_cursor(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        raw = base64.urlsafe_b64decode(cursor.encode())
        return int(json.loads(raw.decode())["i"])
    except Exception:
        return 0


def _audit_hash(prev: str, created_at: str, actor: str, action: str, target: str, result: str) -> str:
    raw = f"{prev}{created_at}{actor}{action}{target}{result}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _tenant_slug(uid: str) -> str:
    return f"{uid[:24]}-workspace"


def _secret_hash(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


@dataclass
class SessionInfo:
    uid: str
    email: str | None
    display_name: str | None
    photo_url: str | None
    tenant_id: str | None
    role: str | None
    is_new_tenant: bool
    needs_client_invite: bool
    created_at: str
    last_login_at: str


class TenantStore(Protocol):
    def ensure_demo_tenant(self) -> None: ...
    def ensure_session_user(
        self,
        *,
        firebase_uid: str,
        email: str | None,
        display_name: str | None,
        photo_url: str | None,
        account_type: str | None = None,
    ) -> SessionInfo: ...
    def get_membership(self, firebase_uid: str) -> tuple[str, str] | None: ...
    def list_membership_fl_client_ids(self, tenant_id: str, firebase_uid: str) -> list[str]: ...
    def create_client_user_invite(
        self,
        tenant_id: str,
        *,
        email: str | None,
        fl_client_ids: list[str],
        expires_in_days: int,
        created_by_firebase_uid: str,
    ) -> tuple[str, str]: ...
    def accept_client_user_invite(self, *, firebase_uid: str, email: str | None, token: str) -> SessionInfo: ...
    def create_fl_client(
        self,
        tenant_id: str,
        *,
        client_id: str,
        node_name: str,
        department: str,
        client_type: Any,
        email: str | None,
        firebase_uid: str | None,
        created_by_uid: str,
    ) -> Any: ...
    def provision_client_user_access(
        self,
        tenant_id: str,
        firebase_uid: str,
        email: str | None,
        display_name: str | None,
        fl_client_ids: list[str],
    ) -> None: ...
    def get_tenant_name(self, tenant_id: str) -> str | None: ...
    def count_fl_clients_by_creator(self, tenant_id: str, firebase_uid: str) -> int: ...
    def list_alerts(self, tenant_id: str, *, limit: int = 50, cursor: str | None = None, severity: str | None = None, tactic: str | None = None, status: str | None = None, date_from: str | None = None, date_to: str | None = None, sort: str = "timestamp_desc") -> tuple[list[Alert], str | None, int]: ...


class MemoryTenantStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.users: dict[str, UserRecord] = {}
        self.tenants: dict[str, dict[str, Any]] = {}
        self.memberships: list[dict[str, str | bool]] = []
        self.membership_client_scopes: list[dict[str, str]] = []
        self.client_user_invites: list[dict[str, Any]] = []
        self.snapshots: dict[str, AppState] = {}
        self.ingest_sources: dict[str, IngestSource] = {}
        self.ingest_source_secrets: dict[str, str] = {}
        self.ingest_events: list[dict[str, Any]] = []
        self.ingest_event_results: dict[tuple[str, str, str], dict[str, Any]] = {}

    def list_membership_fl_client_ids(self, tenant_id: str, firebase_uid: str) -> list[str]:
        with self._lock:
            return sorted(
                {
                    str(row["fl_client_id"])
                    for row in self.membership_client_scopes
                    if str(row["tenant_id"]) == tenant_id and str(row["firebase_uid"]) == firebase_uid
                }
            )

    def create_client_user_invite(
        self,
        tenant_id: str,
        *,
        email: str | None,
        fl_client_ids: list[str],
        expires_in_days: int,
        created_by_firebase_uid: str,
    ) -> tuple[str, str]:
        token = secrets.token_urlsafe(32)
        invite_id = f"inv-{int(time.time() * 1000)}"
        exp = datetime.now(timezone.utc).timestamp() + max(1, expires_in_days) * 86400
        expires_at = datetime.fromtimestamp(exp, tz=timezone.utc).isoformat().replace("+00:00", "Z")
        with self._lock:
            self.client_user_invites.append(
                {
                    "id": invite_id,
                    "tenant_id": tenant_id,
                    "invite_token": token,
                    "email": (email or "").lower() or None,
                    "fl_client_ids": list(fl_client_ids),
                    "expires_at": expires_at,
                    "created_by_firebase_uid": created_by_firebase_uid,
                    "created_at": _now_iso(),
                    "consumed_at": None,
                    "consumed_by_firebase_uid": None,
                }
            )
        return invite_id, token

    def accept_client_user_invite(self, *, firebase_uid: str, email: str | None, token: str) -> SessionInfo:
        now = _now_iso()
        em = (email or "").lower() or None
        with self._lock:
            inv = next((i for i in self.client_user_invites if str(i["invite_token"]) == token), None)
            if inv is None:
                raise ValueError("INVALID_INVITE_TOKEN")
            if inv.get("consumed_at"):
                raise ValueError("INVITE_ALREADY_USED")
            exp = inv["expires_at"]
            if exp.endswith("Z"):
                exp_dt = datetime.fromisoformat(exp.replace("Z", "+00:00"))
            else:
                exp_dt = datetime.fromisoformat(exp)
            if datetime.now(timezone.utc) > exp_dt:
                raise ValueError("INVITE_EXPIRED")
            req_email = inv.get("email")
            if req_email and em and req_email != em:
                raise ValueError("INVITE_EMAIL_MISMATCH")
            tenant_id = str(inv["tenant_id"])
            fl_ids: list[str] = list(inv["fl_client_ids"])
            inv["consumed_at"] = now
            inv["consumed_by_firebase_uid"] = firebase_uid
            existing = self.users.get(firebase_uid)
            created_at = existing.created_at if existing else now
            user = UserRecord(
                uid=firebase_uid,
                email=email if email is not None else (existing.email if existing else None),
                display_name=existing.display_name if existing else None,
                photo_url=existing.photo_url if existing else None,
                created_at=created_at,
                last_login_at=now,
            )
            self.users[firebase_uid] = user
            self.memberships = [m for m in self.memberships if not (m["firebase_uid"] == firebase_uid and m["tenant_id"] == tenant_id)]
            self.memberships.append(
                {"tenant_id": tenant_id, "firebase_uid": firebase_uid, "role": "client_user", "is_default": True}
            )
            for m in self.memberships:
                if m["firebase_uid"] == firebase_uid:
                    m["is_default"] = m["tenant_id"] == tenant_id
            self.membership_client_scopes = [
                m
                for m in self.membership_client_scopes
                if not (m["firebase_uid"] == firebase_uid and m["tenant_id"] == tenant_id)
            ]
            for cid in fl_ids:
                self.membership_client_scopes.append({"tenant_id": tenant_id, "firebase_uid": firebase_uid, "fl_client_id": cid})
            return SessionInfo(
                uid=user.uid,
                email=user.email,
                display_name=user.display_name,
                photo_url=user.photo_url,
                tenant_id=tenant_id,
                role="client_user",
                is_new_tenant=False,
                needs_client_invite=False,
                created_at=user.created_at,
                last_login_at=user.last_login_at,
            )

    def ensure_demo_tenant(self) -> None:
        if not settings.demo_mode:
            return
        if settings.demo_tenant_id in self.tenants:
            return
        self.tenants[settings.demo_tenant_id] = {
            "id": settings.demo_tenant_id,
            "slug": "demo",
            "name": settings.demo_tenant_name,
            "is_demo": True,
        }
        snap = AppState()
        snap.reset()
        self.snapshots[settings.demo_tenant_id] = snap

    def ensure_session_user(
        self,
        *,
        firebase_uid: str,
        email: str | None,
        display_name: str | None,
        photo_url: str | None,
        account_type: str | None = None,
    ) -> SessionInfo:
        at = (account_type or "SYSTEM_OWNER").upper().replace("-", "_")
        with self._lock:
            now = _now_iso()
            existing = self.users.get(firebase_uid)
            created_at = existing.created_at if existing else now
            user = UserRecord(
                uid=firebase_uid,
                email=email if email is not None else (existing.email if existing else None),
                display_name=display_name if display_name is not None else (existing.display_name if existing else None),
                photo_url=photo_url if photo_url is not None else (existing.photo_url if existing else None),
                created_at=created_at,
                last_login_at=now,
            )
            self.users[firebase_uid] = user
            membership = self.get_membership(firebase_uid)
            is_new_tenant = False
            if membership is None:
                if at == "CLIENT_USER":
                    return SessionInfo(
                        uid=user.uid,
                        email=user.email,
                        display_name=user.display_name,
                        photo_url=user.photo_url,
                        tenant_id=None,
                        role=None,
                        is_new_tenant=False,
                        needs_client_invite=True,
                        created_at=user.created_at,
                        last_login_at=user.last_login_at,
                    )
                tenant_id = f"tenant-{firebase_uid}"
                self.tenants[tenant_id] = {
                    "id": tenant_id,
                    "slug": _tenant_slug(firebase_uid),
                    "name": display_name or email or firebase_uid,
                    "is_demo": False,
                }
                self.memberships.append(
                    {
                        "tenant_id": tenant_id,
                        "firebase_uid": firebase_uid,
                        "role": "owner",
                        "is_default": True,
                    }
                )
                self.snapshots[tenant_id] = AppState()
                membership = (tenant_id, "owner")
                is_new_tenant = True

            tenant_id, role = membership
            return SessionInfo(
                uid=user.uid,
                email=user.email,
                display_name=user.display_name,
                photo_url=user.photo_url,
                tenant_id=tenant_id,
                role=role,
                is_new_tenant=is_new_tenant,
                needs_client_invite=False,
                created_at=user.created_at,
                last_login_at=user.last_login_at,
            )

    def get_membership(self, firebase_uid: str) -> tuple[str, str] | None:
        for row in self.memberships:
            if row["firebase_uid"] == firebase_uid and bool(row["is_default"]):
                return str(row["tenant_id"]), str(row["role"])
        for row in self.memberships:
            if row["firebase_uid"] == firebase_uid:
                return str(row["tenant_id"]), str(row["role"])
        return None

    def _snapshot(self, tenant_id: str) -> AppState:
        snap = self.snapshots.get(tenant_id)
        if snap is None:
            snap = AppState()
            self.snapshots[tenant_id] = snap
        return snap

    def _is_demo_tenant(self, tenant_id: str) -> bool:
        return bool(self.tenants.get(tenant_id, {}).get("is_demo"))

    def _decorate_device(self, tenant_id: str, device: Device, *, source_type: str | None = None, source_ref: str | None = None, ingested_at: str | None = None) -> Device:
        return device.model_copy(
            update={
                "source_type": source_type if source_type is not None else getattr(device, "source_type", None),
                "source_ref": source_ref if source_ref is not None else getattr(device, "source_ref", None),
                "ingested_at": ingested_at if ingested_at is not None else getattr(device, "ingested_at", None),
                "is_demo": bool(getattr(device, "is_demo", self._is_demo_tenant(tenant_id))),
            }
        )

    def _decorate_alert(self, tenant_id: str, alert: Alert, *, source_type: str | None = None, source_ref: str | None = None, ingested_at: str | None = None) -> Alert:
        return alert.model_copy(
            update={
                "device": self._decorate_device(tenant_id, alert.device, source_type=source_type, source_ref=source_ref, ingested_at=ingested_at),
                "source_type": source_type if source_type is not None else getattr(alert, "source_type", None),
                "source_ref": source_ref if source_ref is not None else getattr(alert, "source_ref", None),
                "ingested_at": ingested_at if ingested_at is not None else getattr(alert, "ingested_at", None),
                "is_demo": bool(getattr(alert, "is_demo", self._is_demo_tenant(tenant_id))),
            }
        )

    def _decorate_incident(self, tenant_id: str, incident: Incident, *, source_type: str | None = None, source_ref: str | None = None, ingested_at: str | None = None) -> Incident:
        return incident.model_copy(
            update={
                "affected_devices": [self._decorate_device(tenant_id, device, source_type=source_type, source_ref=source_ref, ingested_at=ingested_at) for device in incident.affected_devices],
                "source_type": source_type if source_type is not None else getattr(incident, "source_type", None),
                "source_ref": source_ref if source_ref is not None else getattr(incident, "source_ref", None),
                "ingested_at": ingested_at if ingested_at is not None else getattr(incident, "ingested_at", None),
                "is_demo": bool(getattr(incident, "is_demo", self._is_demo_tenant(tenant_id))),
            }
        )

    def _decorate_sample(self, tenant_id: str, sample: MalwareSample) -> MalwareSample:
        updates = {
            "scan_status": getattr(sample, "scan_status", "NOT_SCANNED"),
            "quarantine_status": getattr(sample, "quarantine_status", "NONE"),
            "retention_status": getattr(sample, "retention_status", "ACTIVE"),
            "chain_of_custody": getattr(sample, "chain_of_custody", []),
            "scanner_verdict": getattr(sample, "scanner_verdict", None),
            "is_demo": bool(getattr(sample, "is_demo", self._is_demo_tenant(tenant_id))),
        }
        return sample.model_copy(update=updates)

    def get_user(self, firebase_uid: str) -> UserRecord | None:
        return self.users.get(firebase_uid)

    def list_alerts(self, tenant_id: str, **kwargs: Any) -> tuple[list[Alert], str | None, int]:
        fl_ids = kwargs.pop("fl_client_ids", None)
        if fl_ids is not None:
            if not fl_ids:
                return [], None, 0
            allow = set(fl_ids)
            wide = {**kwargs, "limit": 10_000, "cursor": None}
            items, _, _ = self._snapshot(tenant_id).list_alerts(**wide)
            decorated = [self._decorate_alert(tenant_id, item) for item in items if item.device.fl_client_id in allow]
            total = len(decorated)
            start = _decode_cursor(kwargs.get("cursor"))
            limit = min(int(kwargs.get("limit", 50) or 50), 200)
            page = decorated[start : start + limit]
            next_cursor = _encode_cursor(start + limit) if (start + limit) < total else None
            return page, next_cursor, total
        items, next_cursor, total = self._snapshot(tenant_id).list_alerts(**kwargs)
        return [self._decorate_alert(tenant_id, item) for item in items], next_cursor, total

    def get_alert(self, tenant_id: str, alert_id: str, *, fl_client_ids: list[str] | None = None) -> Alert | None:
        alert = self._snapshot(tenant_id).get_alert(alert_id)
        if not alert:
            return None
        out = self._decorate_alert(tenant_id, alert)
        if fl_client_ids is not None:
            if not fl_client_ids or out.device.fl_client_id not in fl_client_ids:
                return None
        return out

    def update_alert_status(self, tenant_id: str, alert_id: str, status: AlertStatus, actor_uid: str | None = None) -> Alert | None:
        updated = self._snapshot(tenant_id).update_alert_status(alert_id, status)
        if updated and actor_uid:
            self._snapshot(tenant_id).append_audit(
                actor=actor_uid,
                action=AuditAction.RESPONSE_TRIGGERED,
                target=alert_id,
                result=f"Status changed to {status.value}",
            )
        return updated

    def list_devices(self, tenant_id: str, **kwargs: Any) -> list[Device]:
        fl_ids = kwargs.pop("fl_client_ids", None)
        if fl_ids is not None and not fl_ids:
            return []
        devices = self._snapshot(tenant_id).list_devices(**kwargs)
        snap = self._snapshot(tenant_id)
        # Only return devices whose fl_client is DEVICE-type (not PERSON)
        device_client_ids = {
            c.id for c in snap.fl_clients
            if str(getattr(c.client_type, "value", c.client_type)) == "DEVICE"
        }
        devices = [d for d in devices if d.fl_client_id in device_client_ids]
        if fl_ids:
            allow = set(fl_ids)
            devices = [d for d in devices if d.fl_client_id in allow]
        return [self._decorate_device(tenant_id, device) for device in devices]

    def get_device(self, tenant_id: str, device_id: str, *, fl_client_ids: list[str] | None = None) -> Device | None:
        device = self._snapshot(tenant_id).get_device(device_id)
        if not device:
            return None
        if fl_client_ids is not None:
            if not fl_client_ids or device.fl_client_id not in fl_client_ids:
                return None
        return self._decorate_device(tenant_id, device)

    def quarantine_device(self, tenant_id: str, device_id: str, actor_uid: str) -> dict[str, Any] | None:
        snap = self._snapshot(tenant_id)
        dev = snap.get_device(device_id)
        if not dev:
            return None
        snap.set_device_status(device_id, DeviceStatus.ISOLATED)
        snap.sync_alert_devices_for_device_id(device_id)
        cmd_id = f"CMD-{int(time.time() * 1000)}"
        sent_at = _now_iso()
        snap.append_audit(
            actor=actor_uid,
            action=AuditAction.DEVICE_QUARANTINED,
            target=device_id,
            result=f"Isolation command {cmd_id} dispatched",
        )
        snap.append_quarantine_to_open_incidents(device_id, f"Device {dev.name} quarantined ({device_id})")
        return {"deviceId": device_id, "status": "ISOLATED", "commandId": cmd_id, "sentAt": sent_at}

    def list_incidents(self, tenant_id: str, **kwargs: Any) -> tuple[list[Incident], str | None, int]:
        fl_ids = kwargs.pop("fl_client_ids", None)
        if fl_ids is not None:
            if not fl_ids:
                return [], None, 0
            allow = set(fl_ids)
            wide = {**kwargs, "limit": 10_000, "cursor": None}
            items, _, _ = self._snapshot(tenant_id).list_incidents(**wide)
            decorated = [
                self._decorate_incident(tenant_id, item)
                for item in items
                if any(d.fl_client_id in allow for d in item.affected_devices)
            ]
            total = len(decorated)
            start = _decode_cursor(kwargs.get("cursor"))
            limit = min(int(kwargs.get("limit", 100) or 100), 500)
            page = decorated[start : start + limit]
            next_cursor = _encode_cursor(start + limit) if (start + limit) < total else None
            return page, next_cursor, total
        items, next_cursor, total = self._snapshot(tenant_id).list_incidents(**kwargs)
        return [self._decorate_incident(tenant_id, item) for item in items], next_cursor, total

    def get_incident(self, tenant_id: str, incident_id: str, *, fl_client_ids: list[str] | None = None) -> Incident | None:
        incident = self._snapshot(tenant_id).get_incident(incident_id)
        if not incident:
            return None
        out = self._decorate_incident(tenant_id, incident)
        if fl_client_ids is not None:
            if not fl_client_ids or not any(d.fl_client_id in fl_client_ids for d in out.affected_devices):
                return None
        return out

    def run_playbook(self, tenant_id: str, incident_id: str, actor_uid: str) -> tuple[Incident | None, int | None, str]:
        snap = self._snapshot(tenant_id)
        now_iso = _now_iso()
        updated, current_step = snap.run_playbook(incident_id, now_iso)
        if updated:
            snap.append_audit(
                actor=actor_uid,
                action=AuditAction.RESPONSE_TRIGGERED,
                target=incident_id,
                result=f"Playbook run started (step {current_step})",
            )
        return updated, current_step, now_iso

    def patch_incident_status(self, tenant_id: str, *, incident_id: str, status: IncidentStatus, assignee: str, notes: str | None, actor_uid: str) -> Incident | None:
        return self._snapshot(tenant_id).patch_incident_status(
            incident_id=incident_id,
            status=status,
            assignee=assignee,
            notes=notes,
            actor=actor_uid,
        )

    def patch_playbook_step(self, tenant_id: str, *, incident_id: str, step_id: str, status: str, notes: str | None, actor_uid: str) -> Any | None:
        return self._snapshot(tenant_id).patch_playbook_step(
            incident_id=incident_id,
            step_id=step_id,
            status=status,
            notes=notes,
            actor=actor_uid,
        )

    def halt_playbook(self, tenant_id: str, *, incident_id: str, reason: str, actor_uid: str) -> dict[str, Any] | None:
        return self._snapshot(tenant_id).halt_playbook(incident_id=incident_id, reason=reason, actor=actor_uid)

    def fl_status_dict(self, tenant_id: str, fl_client_ids: list[str] | None = None) -> dict[str, Any]:
        snap = self._snapshot(tenant_id)
        clients = snap.fl_clients
        if fl_client_ids is not None:
            if not fl_client_ids:
                clients = []
            else:
                allow = set(fl_client_ids)
                clients = [c for c in clients if c.id in allow]
        rounds, session_id = snap.fl_rounds, snap.fl_session_id
        current = rounds[-1].round if rounds else 0
        latest = rounds[-1] if rounds else None
        active_clients = sum(1 for c in clients if c.status == FLClientStatus.ACTIVE)
        poison = any(c.status == FLClientStatus.POISONING_SUSPECT for c in clients)
        md = snap.fl_models_dict()
        zoo = sorted({str(m["name"]) for m in md.get("models", [])})
        payload = {
            "currentRound": current,
            "totalRounds": max(current, 100),
            "activeClients": active_clients,
            "totalClients": len(clients),
            "nextRoundIn": 180,
            "aggregatorStatus": "AGGREGATING" if session_id else "IDLE",
            "latestAccuracy": round(latest.accuracy, 1) if latest else 0.0,
            "latestFpRate": round(latest.fp_rate, 1) if latest else 0.0,
            "driftDetected": poison,
            "activeModel": snap.active_model_name,
            "modelZoo": zoo,
            "federationScope": "DEMO_RESEARCH" if self._is_demo_tenant(tenant_id) else "LOCAL_RUNTIME_ONLY",
        }
        return payload

    def get_fl_client(self, tenant_id: str, client_id: str, *, fl_client_ids: list[str] | None = None) -> FLClient | None:
        cl = self._snapshot(tenant_id).get_fl_client(client_id)
        if not cl:
            return None
        if fl_client_ids is not None:
            if not fl_client_ids or cl.id not in fl_client_ids:
                return None
        return cl

    def list_fl_rounds(self, tenant_id: str) -> tuple[list[FLRound], str]:
        snap = self._snapshot(tenant_id)
        return snap.fl_rounds, snap.fl_session_id

    def list_fl_clients(self, tenant_id: str, fl_client_ids: list[str] | None = None) -> list[FLClient]:
        clients = list(self._snapshot(tenant_id).fl_clients)
        if fl_client_ids is not None:
            if not fl_client_ids:
                return []
            allow = set(fl_client_ids)
            clients = [c for c in clients if c.id in allow]
        return clients

    def patch_fl_client(self, tenant_id: str, client_id: str, *, client_type: FLClientType) -> FLClient | None:
        with self._lock:
            snap = self._snapshot(tenant_id)
            for i, c in enumerate(snap.fl_clients):
                if c.id == client_id:
                    updated = c.model_copy(update={"client_type": client_type})
                    snap.fl_clients[i] = updated
                    return updated.model_copy(deep=True)
        return None

    def create_fl_client(
        self,
        tenant_id: str,
        *,
        client_id: str,
        node_name: str,
        department: str,
        client_type: FLClientType,
        email: str | None,
        firebase_uid: str | None,
        created_by_uid: str,
    ) -> FLClient:
        ct = client_type.value if hasattr(client_type, "value") else str(client_type)
        client = FLClient(
            id=client_id,
            department=department,
            participation_pct=0.0,
            last_round=0,
            dp_epsilon=1.0,
            model_version="",
            status=FLClientStatus.OFFLINE,
            client_type=ct,
            node_name=node_name,
            created_by_firebase_uid=created_by_uid,
        )
        with self._lock:
            snap = self._snapshot(tenant_id)
            # Avoid duplicates
            if not any(c.id == client_id for c in snap.fl_clients):
                snap.fl_clients.append(client)
        return client.model_copy(deep=True)

    def provision_client_user_access(
        self,
        tenant_id: str,
        firebase_uid: str,
        email: str | None,
        display_name: str | None,
        fl_client_ids: list[str],
    ) -> None:
        now = _now_iso()
        with self._lock:
            existing = self.users.get(firebase_uid)
            self.users[firebase_uid] = UserRecord(
                uid=firebase_uid,
                email=email if email is not None else (existing.email if existing else None),
                display_name=display_name or (existing.display_name if existing else None),
                photo_url=existing.photo_url if existing else None,
                created_at=existing.created_at if existing else now,
                last_login_at=now,
            )
            self.memberships = [
                m for m in self.memberships
                if not (str(m["firebase_uid"]) == firebase_uid and str(m["tenant_id"]) == tenant_id)
            ]
            self.memberships.append(
                {"tenant_id": tenant_id, "firebase_uid": firebase_uid, "role": "client_user", "is_default": True}
            )
            self.membership_client_scopes = [
                m for m in self.membership_client_scopes
                if not (str(m["firebase_uid"]) == firebase_uid and str(m["tenant_id"]) == tenant_id)
            ]
            for cid in fl_client_ids:
                self.membership_client_scopes.append(
                    {"tenant_id": tenant_id, "firebase_uid": firebase_uid, "fl_client_id": cid}
                )

    def get_tenant_name(self, tenant_id: str) -> str | None:
        tenant = self.tenants.get(tenant_id)
        return str(tenant["name"]) if tenant and tenant.get("name") else None

    def count_fl_clients_by_creator(self, tenant_id: str, firebase_uid: str) -> int:
        with self._lock:
            snap = self._snapshot(tenant_id)
        return sum(
            1
            for c in snap.fl_clients
            if getattr(c, "created_by_firebase_uid", None) == firebase_uid
        )

    def list_client_user_invites(self, tenant_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = [dict(r) for r in self.client_user_invites if str(r["tenant_id"]) == tenant_id]
        rows.sort(key=lambda r: str(r.get("created_at") or r.get("id") or ""), reverse=True)
        out: list[dict[str, Any]] = []
        for r in rows:
            created = r.get("created_at")
            if created is None:
                created = _now_iso()
            out.append(
                {
                    "invite_id": str(r["id"]),
                    "email": r.get("email"),
                    "fl_client_ids": list(r.get("fl_client_ids") or []),
                    "expires_at": str(r.get("expires_at") or ""),
                    "created_at": str(created),
                    "consumed_at": r.get("consumed_at"),
                }
            )
        return out

    def fl_drift_dict(self, tenant_id: str, fl_client_ids: list[str] | None = None) -> dict[str, Any]:
        payload = self._snapshot(tenant_id).fl_drift_dict()
        entries = list(payload.get("entries", []))
        if fl_client_ids is not None:
            if not fl_client_ids:
                entries = []
            else:
                allow = set(fl_client_ids)
                entries = [e for e in entries if str(e.get("clientId")) in allow]
        payload.update(
            {
                "available": True,
                "driftScores": [
                    {
                        "model": "Per-client drift overlay",
                        "score": max((float(item.get("driftScore", 0.0)) for item in entries), default=0.0),
                        "peakScore": max((float(item.get("driftScore", 0.0)) for item in entries), default=0.0),
                        "status": "DEMO_RESEARCH",
                        "samples": len(entries),
                        "lastEvent": "External client telemetry not connected",
                    }
                ],
                "overallDrift": max((float(item.get("driftScore", 0.0)) for item in entries), default=0.0),
                "overallStatus": "DEMO_RESEARCH",
                "driftDetected": any(bool(item.get("flagged")) for item in entries),
                "nReferenceImages": 0,
                "samplesAnalyzed": len(entries),
                "checkedAt": _now_iso(),
                "scope": "DEMO_RESEARCH",
                "operatorUse": "Do not treat per-client drift as operational telemetry without external client instrumentation.",
            }
        )
        payload.update(_fl_drift_semantics_overlay())
        return payload

    def fl_models_dict(self, tenant_id: str, **kwargs: Any) -> dict[str, Any]:
        return self._snapshot(tenant_id).fl_models_dict(**kwargs)

    def activate_fl_model(self, tenant_id: str, model_name: str, actor_uid: str, **kwargs: Any) -> tuple[str | None, str, bool]:
        if kwargs.get("fl_client_id"):
            return None, _now_iso(), False
        snap = self._snapshot(tenant_id)
        now_iso = _now_iso()
        if model_name not in snap.model_zoo_names:
            return None, now_iso, False
        previous = snap.activate_fl_model(model_name, now_iso)
        snap.append_audit(
            actor=actor_uid,
            action=AuditAction.MODEL_UPDATED,
            target=model_name,
            result=f"Activated model {model_name}",
        )
        return previous, now_iso, True

    def escalate_alert(
        self, tenant_id: str, alert_id: str, actor_uid: str, *, fl_client_ids: list[str] | None = None
    ) -> Incident | None:
        alert = self.get_alert(tenant_id, alert_id, fl_client_ids=fl_client_ids)
        if not alert:
            return None
        snap = self._snapshot(tenant_id)
        from app.routers.alerts import _build_incident_from_alert  # local import to avoid cycle at module load

        incident = _build_incident_from_alert(alert)
        snap.incidents.append(incident)
        self.update_alert_status(tenant_id, alert_id, AlertStatus.IN_REVIEW, actor_uid)
        return self._decorate_incident(tenant_id, incident)

    def list_samples(self, tenant_id: str, **kwargs: Any) -> tuple[list[MalwareSample], str | None, int]:
        fl_ids = kwargs.pop("fl_client_ids", None)
        if fl_ids is not None:
            if not fl_ids:
                return [], None, 0
            allow = set(fl_ids)
            wide = {**kwargs, "limit": 10_000, "cursor": None}
            items, _, _ = self._snapshot(tenant_id).list_samples(**wide)
            decorated = []
            for item in items:
                dev = self._snapshot(tenant_id).get_device(item.device_id)
                if dev and dev.fl_client_id in allow:
                    decorated.append(self._decorate_sample(tenant_id, item))
            total = len(decorated)
            start = _decode_cursor(kwargs.get("cursor"))
            limit = min(int(kwargs.get("limit", 50) or 50), 200)
            page = decorated[start : start + limit]
            next_cursor = _encode_cursor(start + limit) if (start + limit) < total else None
            return page, next_cursor, total
        items, next_cursor, total = self._snapshot(tenant_id).list_samples(**kwargs)
        return [self._decorate_sample(tenant_id, item) for item in items], next_cursor, total

    def get_sample(self, tenant_id: str, sample_id: str, *, fl_client_ids: list[str] | None = None) -> MalwareSample | None:
        sample = self._snapshot(tenant_id).get_sample(sample_id)
        if not sample:
            return None
        if fl_client_ids is not None:
            if not fl_client_ids:
                return None
            dev = self._snapshot(tenant_id).get_device(sample.device_id)
            if not dev or dev.fl_client_id not in fl_client_ids:
                return None
        return self._decorate_sample(tenant_id, sample)

    def upload_sample(self, tenant_id: str, *, file: Any, device_id: str, notes: str | None, actor_uid: str) -> MalwareSample:
        snap = self._snapshot(tenant_id)
        sample = snap.upload_malware_sample(file=file, device_id=device_id, notes=notes)
        custody = [
            {
                "timestamp": sample.upload_time,
                "actor": actor_uid,
                "action": "UPLOADED",
                "detail": f"Sample uploaded for device {device_id}",
            },
            {
                "timestamp": sample.upload_time,
                "actor": "system",
                "action": "QUEUED_FOR_SCAN",
                "detail": "Queued for scanner review",
            },
        ]
        sample = sample.model_copy(
            update={
                "status": "QUEUED",
                "scan_status": "QUEUED",
                "quarantine_status": "NONE",
                "retention_status": "ACTIVE",
                "chain_of_custody": custody,
                "scanner_verdict": None,
                "is_demo": self._is_demo_tenant(tenant_id),
            }
        )
        snap.malware_samples = [sample.model_copy(deep=True) if existing.id == sample.id else existing for existing in snap.malware_samples]
        snap.append_audit(
            actor=actor_uid,
            action=AuditAction.DETECTION_MADE,
            target=sample.id,
            result="Malware sample uploaded",
        )
        return sample

    def run_sample_scan(self, tenant_id: str, *, sample_id: str, actor_uid: str) -> MalwareSample | None:
        snap = self._snapshot(tenant_id)
        sample = snap.get_sample(sample_id)
        if not sample:
            return None
        result = scan_forensics_sample(sample_id=sample.id, filename=sample.filename, sha256=sample.sha256)
        now = _now_iso()
        custody = list(getattr(sample, "chain_of_custody", []))
        custody.append({"timestamp": now, "actor": actor_uid, "action": "SCANNED", "detail": result.summary})
        updated = sample.model_copy(
            update={
                "status": "SCANNED",
                "scan_status": "SCANNED",
                "scanner_verdict": {"engine": result.engine, "verdict": result.verdict, "confidence": result.confidence, "summary": result.summary},
                "chain_of_custody": custody,
                "is_demo": self._is_demo_tenant(tenant_id),
            }
        )
        snap.malware_samples = [updated if existing.id == sample_id else existing for existing in snap.malware_samples]
        snap.append_audit(actor=actor_uid, action=AuditAction.RESPONSE_TRIGGERED, target=sample_id, result=f"Sample scanned: {result.verdict}")
        return updated

    def update_sample_disposition(self, tenant_id: str, *, sample_id: str, quarantine_status: str | None = None, retention_status: str | None = None, actor_uid: str, detail: str | None = None) -> MalwareSample | None:
        snap = self._snapshot(tenant_id)
        sample = snap.get_sample(sample_id)
        if not sample:
            return None
        now = _now_iso()
        custody = list(getattr(sample, "chain_of_custody", []))
        action = quarantine_status or retention_status or "UPDATED"
        custody.append({"timestamp": now, "actor": actor_uid, "action": action, "detail": detail or action})
        updates: dict[str, Any] = {"chain_of_custody": custody, "is_demo": self._is_demo_tenant(tenant_id)}
        if quarantine_status:
            updates["quarantine_status"] = quarantine_status
            updates["status"] = "QUARANTINED" if quarantine_status == "QUARANTINED" else "RELEASED"
        if retention_status:
            updates["retention_status"] = retention_status
            if retention_status == "EXPIRED":
                updates["status"] = "EXPIRED"
        updated = sample.model_copy(update=updates)
        snap.malware_samples = [updated if existing.id == sample_id else existing for existing in snap.malware_samples]
        snap.append_audit(actor=actor_uid, action=AuditAction.RESPONSE_TRIGGERED, target=sample_id, result=detail or action)
        return updated

    def list_rca_reports(self, tenant_id: str, fl_client_ids: list[str] | None = None) -> tuple[list[RCAReport], int]:
        items, total = self._snapshot(tenant_id).list_rca_reports()
        if fl_client_ids is not None:
            if not fl_client_ids:
                return [], 0
            allow = set(fl_client_ids)
            filtered: list[RCAReport] = []
            for r in items:
                inc = self._snapshot(tenant_id).get_incident(r.incident_id)
                if inc and any(d.fl_client_id in allow for d in inc.affected_devices):
                    filtered.append(r)
            return filtered, len(filtered)
        return items, total

    def get_rca(self, tenant_id: str, rca_id: str, *, fl_client_ids: list[str] | None = None) -> RCAReport | None:
        r = self._snapshot(tenant_id).get_rca(rca_id)
        if not r:
            return None
        if fl_client_ids is not None:
            if not fl_client_ids:
                return None
            inc = self._snapshot(tenant_id).get_incident(r.incident_id)
            if not inc or not any(d.fl_client_id in fl_client_ids for d in inc.affected_devices):
                return None
        return r

    def generate_rca_report(self, tenant_id: str, incident_id: str, *, fl_client_ids: list[str] | None = None) -> RCAReport | None:
        if fl_client_ids is not None:
            if not fl_client_ids:
                return None
            inc = self.get_incident(tenant_id, incident_id, fl_client_ids=fl_client_ids)
            if not inc:
                return None
        return self._snapshot(tenant_id).generate_rca_report(incident_id=incident_id)

    def block_ip(self, tenant_id: str, *, ip: str, reason: str, alert_id: str | None) -> dict[str, Any] | None:
        return self._snapshot(tenant_id).block_ip(ip=ip, reason=reason, alert_id=alert_id)

    def list_audit_logs(self, tenant_id: str, **kwargs: Any) -> tuple[list[AuditLog], str | None, int]:
        kwargs.pop("fl_client_ids", None)
        kwargs.pop("scope_firebase_uid", None)
        return self._snapshot(tenant_id).list_audit_logs(**kwargs)

    def verify_audit_chain(self, tenant_id: str, fl_client_ids: list[str] | None = None, scope_firebase_uid: str | None = None) -> dict[str, Any]:
        _ = fl_client_ids
        _ = scope_firebase_uid
        return self._snapshot(tenant_id).verify_audit_chain()

    def dashboard_kpis(self, tenant_id: str, fl_client_ids: list[str] | None = None) -> dict[str, Any]:
        snap = self._snapshot(tenant_id)
        from app.store.memory import _enum_primitive, _norm_iso  # reuse memory helpers

        alerts = list(snap.alerts)
        devices = list(snap.devices)
        incidents = list(snap.incidents)
        if fl_client_ids is not None:
            if not fl_client_ids:
                alerts, devices, incidents = [], [], []
            else:
                allow = set(fl_client_ids)
                alerts = [a for a in alerts if a.device.fl_client_id in allow]
                devices = [d for d in devices if d.fl_client_id in allow]
                incidents = [i for i in incidents if any(d.fl_client_id in allow for d in i.affected_devices)]
        open_alerts = [a for a in alerts if _enum_primitive(a.status) == "OPEN"]
        critical = [
            a
            for a in alerts
            if _enum_primitive(a.severity) == "CRITICAL" and _enum_primitive(a.status) == "OPEN"
        ]
        avg_conf = sum(a.confidence for a in alerts) / len(alerts) if alerts else 0.0
        watch_statuses = {"SUSPICIOUS", "COMPROMISED", "ISOLATED"}
        under_watch = sum(1 for d in devices if _enum_primitive(d.status) in watch_statuses)
        fl_round = snap.fl_rounds[-1].round if snap.fl_rounds else 0
        open_inc = sum(1 for i in incidents if _enum_primitive(i.status) not in ("RESOLVED", "POST_MORTEM"))
        today = datetime.now(timezone.utc).date()
        resolved_today = sum(
            1
            for a in alerts
            if _enum_primitive(a.status) == "RESOLVED" and _norm_iso(a.timestamp).date() == today
        )
        fp_count = sum(1 for a in alerts if _enum_primitive(a.status) == "FALSE_POSITIVE")
        fp_rate = (fp_count / len(alerts) * 100) if alerts else 0.0
        payload = {
            "activeThreats": len(open_alerts),
            "avgConfidence": round(avg_conf, 1),
            "devicesUnderWatch": under_watch,
            "flRound": fl_round,
            "openIncidents": open_inc,
            "criticalAlerts": len(critical),
            "resolvedToday": resolved_today,
            "falsePositiveRate": round(fp_rate, 1),
        }
        tenant_sources = [source for source in self.ingest_sources.values() if source.tenant_id == tenant_id]
        tenant_events = [event for event in self.ingest_events if event["tenant_id"] == tenant_id]
        payload.update(
            {
                "liveDataConnected": bool(tenant_events),
                "ingestSourcesConfigured": len(tenant_sources),
                "ingestEventsReceived": len(tenant_events),
                "demoMode": self._is_demo_tenant(tenant_id),
            }
        )
        return payload

    def list_ingest_sources(self, tenant_id: str) -> list[IngestSource]:
        return [source for source in self.ingest_sources.values() if source.tenant_id == tenant_id]

    def create_ingest_source(self, tenant_id: str, *, name: str, source_type: str, connector_kind: str, actor_uid: str) -> tuple[IngestSource, str]:
        now = _now_iso()
        source_id = f"src-{int(time.time() * 1000)}"
        secret = secrets.token_urlsafe(24)
        source = IngestSource(
            id=source_id,
            tenant_id=tenant_id,
            name=name,
            source_type=source_type.upper(),
            connector_kind=connector_kind.upper(),
            secret_last_rotated_at=now,
            created_at=now,
            updated_at=now,
        )
        self.ingest_sources[source_id] = source
        self.ingest_source_secrets[source_id] = _secret_hash(secret)
        self.append_audit(tenant_id, actor_uid=actor_uid, actor_label=actor_uid, action=AuditAction.CONFIG_CHANGED, target_type="ingest_source", target_id=source_id, result=f"Created ingest source {name}", metadata={"sourceType": source_type, "connectorKind": connector_kind})
        return source, secret

    def rotate_ingest_source_secret(self, tenant_id: str, *, source_id: str, actor_uid: str) -> tuple[IngestSource | None, str | None]:
        source = self.ingest_sources.get(source_id)
        if not source or source.tenant_id != tenant_id:
            return None, None
        now = _now_iso()
        secret = secrets.token_urlsafe(24)
        self.ingest_source_secrets[source_id] = _secret_hash(secret)
        updated = source.model_copy(update={"secret_last_rotated_at": now, "updated_at": now})
        self.ingest_sources[source_id] = updated
        self.append_audit(tenant_id, actor_uid=actor_uid, actor_label=actor_uid, action=AuditAction.CONFIG_CHANGED, target_type="ingest_source", target_id=source_id, result="Rotated ingest source secret", metadata={})
        return updated, secret

    def ingest_event(self, *, source_id: str, source_secret: str, external_id: str, event_type: str, payload: dict[str, Any], occurred_at: str | None = None) -> IngestEventResult | None:
        source = self.ingest_sources.get(source_id)
        if not source or self.ingest_source_secrets.get(source_id) != _secret_hash(source_secret):
            return None
        tenant_id = source.tenant_id
        dedupe_key = (tenant_id, source_id, external_id)
        existing = self.ingest_event_results.get(dedupe_key)
        if existing:
            result = IngestEventResult.model_validate(existing)
            return result.model_copy(update={"parse_status": "DUPLICATE"})

        result = self._ingest_memory_event(source=source, external_id=external_id, event_type=event_type, payload=payload, occurred_at=occurred_at)
        self.ingest_events.append({"tenant_id": tenant_id, "source_id": source_id, "external_id": external_id, "result": result.model_dump(mode="json")})
        self.ingest_event_results[dedupe_key] = result.model_dump(mode="json")
        return result

    def export_audit_logs(
        self,
        tenant_id: str,
        *,
        format: str = "jsonl",
        date_from: str | None = None,
        date_to: str | None = None,
        fl_client_ids: list[str] | None = None,
        scope_firebase_uid: str | None = None,
    ) -> str:
        items, _, _ = self.list_audit_logs(
            tenant_id,
            limit=1000,
            date_from=date_from,
            date_to=date_to,
            fl_client_ids=fl_client_ids,
            scope_firebase_uid=scope_firebase_uid,
        )
        if format == "csv":
            lines = ["id,timestamp,actor,action,targetType,target,result,hash"]
            for item in items:
                lines.append(f'{item.id},{item.timestamp},{item.actor},{item.action},{item.target_type or ""},{item.target},{item.result},{item.hash}')
            return "\n".join(lines)
        return "\n".join(json.dumps(item.model_dump(by_alias=True, mode="json")) for item in items)

    def _ingest_memory_event(self, *, source: IngestSource, external_id: str, event_type: str, payload: dict[str, Any], occurred_at: str | None) -> IngestEventResult:
        tenant_id = source.tenant_id
        snap = self._snapshot(tenant_id)
        received_at = _now_iso()
        normalized_targets: list[dict[str, str]] = []
        event_type_norm = event_type.lower()
        device_id = str(payload.get("deviceId") or payload.get("device_id") or f"dev-ingest-{len(snap.devices)+1:03d}")
        existing_device = snap.get_device(device_id)
        if existing_device is None:
            device = Device(
                id=device_id,
                name=str(payload.get("deviceName") or payload.get("device_name") or device_id),
                ip=str(payload.get("ip") or "0.0.0.0"),
                type=str(payload.get("deviceType") or payload.get("type") or "UNKNOWN"),
                wing=str(payload.get("wing") or "INGEST"),
                criticality=int(payload.get("criticality") or 3),
                fl_client_id=str(payload.get("flClientId") or "client-ingest"),
                status=DeviceStatus(str(payload.get("deviceStatus") or payload.get("status") or DeviceStatus.SUSPICIOUS.value)),
                source_type=source.source_type,
                source_ref=external_id,
                ingested_at=received_at,
                is_demo=False,
            )
            snap.devices.append(device)
            normalized_targets.append({"type": "device", "id": device.id})
        if event_type_norm == "alert":
            alert_id = str(payload.get("alertId") or payload.get("id") or f"ALT-{int(time.time() * 1000)}")
            device = snap.get_device(device_id)
            if device is None:
                raise ValueError("Device was not available for ingested alert")
            alert = Alert(
                id=alert_id,
                timestamp=str(occurred_at or received_at),
                device_id=device.id,
                device=self._decorate_device(tenant_id, device, source_type=source.source_type, source_ref=external_id, ingested_at=received_at),
                type=str(payload.get("alertType") or payload.get("type") or "External Alert"),
                tactic=str(payload.get("tactic") or "Execution"),
                technique={"id": str(payload.get("techniqueId") or "T1204"), "tactic": str(payload.get("tactic") or "Execution"), "name": str(payload.get("techniqueName") or "User Execution")},
                severity=Severity(str(payload.get("severity") or Severity.HIGH.value)),
                confidence=float(payload.get("confidence") or 0.8),
                status=AlertStatus.OPEN,
                model_version=str(payload.get("modelVersion") or source.connector_kind),
                threat_intel=[],
                cve_reference=payload.get("cveReference"),
                feature_summary=str(payload.get("summary") or "Ingested from external source"),
                source_type=source.source_type,
                source_ref=external_id,
                ingested_at=received_at,
                is_demo=False,
            )
            snap.alerts.insert(0, alert)
            normalized_targets.append({"type": "alert", "id": alert.id})
        elif event_type_norm == "ticket":
            incident_id = str(payload.get("incidentId") or payload.get("ticketId") or f"INC-{int(time.time() * 1000)}")
            device = snap.get_device(device_id)
            if device is None:
                raise ValueError("Device was not available for ingested ticket")
            incident = Incident(
                id=incident_id,
                title=str(payload.get("title") or "External Incident"),
                severity=Severity(str(payload.get("severity") or Severity.MEDIUM.value)),
                status=IncidentStatus(str(payload.get("incidentStatus") or IncidentStatus.NEW.value)),
                affected_devices=[self._decorate_device(tenant_id, device, source_type=source.source_type, source_ref=external_id, ingested_at=received_at)],
                time_open="0m",
                analyst_initials=str(payload.get("analystInitials") or "EX"),
                timeline=[IncidentEvent(id=f"evt-{int(time.time() * 1000)}", timestamp=str(occurred_at or received_at), type="ALERT", description=str(payload.get("summary") or "Ingested ticket event"))],
                playbook=Playbook(id=f"pb-{incident_id}", name="External Ticket", trigger_condition=source.source_type, last_run=received_at, executions=0, status="DRAFT", steps=[]),
                ticket_id=str(payload.get("ticketId") or incident_id),
                reporter=str(payload.get("reporter") or source.name),
                assignee=str(payload.get("assignee") or "Unassigned"),
                priority=str(payload.get("priority") or "P3"),
                created=str(occurred_at or received_at),
                labels=list(payload.get("labels") or [source.source_type]),
                source_type=source.source_type,
                source_ref=external_id,
                ingested_at=received_at,
                is_demo=False,
            )
            snap.incidents.insert(0, incident)
            normalized_targets.append({"type": "incident", "id": incident.id})
        self.append_audit(tenant_id, actor_uid="connector", actor_label=f"{source.name} connector", action=AuditAction.DETECTION_MADE, target_type=event_type_norm, target_id=external_id, result=f"Ingested {event_type_norm} event", metadata={"sourceId": source.id})
        return IngestEventResult(event_id=f"ing-{int(time.time() * 1000)}", tenant_id=tenant_id, source_id=source.id, external_id=external_id, parse_status="ACCEPTED", normalized_targets=normalized_targets, received_at=received_at)

    def append_audit(self, tenant_id: str, *, actor_uid: str, actor_label: str, action: AuditAction, target_type: str, target_id: str, result: str, metadata: dict[str, Any] | None = None) -> None:
        self._snapshot(tenant_id).append_audit(
            actor=actor_label,
            action=action,
            target=target_id,
            result=result,
        )


class PostgresTenantStore:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def _connect(self):
        return psycopg.connect(
            self.database_url,
            **pg_app_connect_kwargs(application_name="bastionfed_tenant_store"),
            row_factory=dict_row,
        )

    def ensure_demo_tenant(self) -> None:
        if not settings.demo_mode:
            return
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tenants (id, slug, name, is_demo)
                VALUES (%s, %s, %s, TRUE)
                ON CONFLICT (id) DO NOTHING
                """,
                (settings.demo_tenant_id, "demo", settings.demo_tenant_name),
            )
            cur.execute("SELECT EXISTS(SELECT 1 FROM devices WHERE tenant_id = %s)", (settings.demo_tenant_id,))
            seeded = bool(cur.fetchone()["exists"])
            if not seeded:
                self._seed_demo_tenant(cur, settings.demo_tenant_id)
            conn.commit()

    def ensure_session_user(
        self,
        *,
        firebase_uid: str,
        email: str | None,
        display_name: str | None,
        photo_url: str | None,
        account_type: str | None = None,
    ) -> SessionInfo:
        at = (account_type or "SYSTEM_OWNER").upper().replace("-", "_")
        now = _now_iso()
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (firebase_uid, email, display_name, photo_url, created_at, last_login_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (firebase_uid) DO UPDATE SET
                    email = COALESCE(EXCLUDED.email, users.email),
                    display_name = COALESCE(EXCLUDED.display_name, users.display_name),
                    photo_url = COALESCE(EXCLUDED.photo_url, users.photo_url),
                    last_login_at = EXCLUDED.last_login_at
                RETURNING firebase_uid, email, display_name, photo_url, created_at, last_login_at
                """,
                (firebase_uid, email, display_name, photo_url, now, now),
            )
            user = cur.fetchone()
            cur.execute(
                """
                SELECT tenant_id, role
                FROM memberships
                WHERE firebase_uid = %s
                ORDER BY is_default DESC, created_at ASC
                LIMIT 1
                """,
                (firebase_uid,),
            )
            membership = cur.fetchone()
            is_new_tenant = False
            if membership is None:
                if at == "CLIENT_USER":
                    conn.commit()
                    return SessionInfo(
                        uid=str(user["firebase_uid"]),
                        email=user["email"],
                        display_name=user["display_name"],
                        photo_url=user["photo_url"],
                        tenant_id=None,
                        role=None,
                        is_new_tenant=False,
                        needs_client_invite=True,
                        created_at=str(user["created_at"]),
                        last_login_at=str(user["last_login_at"]),
                    )
                tenant_id = f"tenant-{firebase_uid}"
                cur.execute(
                    """
                    INSERT INTO tenants (id, slug, name, is_demo)
                    VALUES (%s, %s, %s, FALSE)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (tenant_id, _tenant_slug(firebase_uid), display_name or email or firebase_uid),
                )
                cur.execute(
                    """
                    INSERT INTO memberships (tenant_id, firebase_uid, role, is_default, created_at)
                    VALUES (%s, %s, 'owner', TRUE, %s)
                    ON CONFLICT (tenant_id, firebase_uid) DO UPDATE SET
                        role = EXCLUDED.role,
                        is_default = TRUE
                    """,
                    (tenant_id, firebase_uid, now),
                )
                membership = {"tenant_id": tenant_id, "role": "owner"}
                is_new_tenant = True
            conn.commit()
            return SessionInfo(
                uid=str(user["firebase_uid"]),
                email=user["email"],
                display_name=user["display_name"],
                photo_url=user["photo_url"],
                tenant_id=str(membership["tenant_id"]),
                role=str(membership["role"]),
                is_new_tenant=is_new_tenant,
                needs_client_invite=False,
                created_at=str(user["created_at"]),
                last_login_at=str(user["last_login_at"]),
            )

    def list_membership_fl_client_ids(self, tenant_id: str, firebase_uid: str) -> list[str]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT fl_client_id FROM membership_client_scopes
                WHERE tenant_id = %s AND firebase_uid = %s
                ORDER BY fl_client_id ASC
                """,
                (tenant_id, firebase_uid),
            )
            rows = cur.fetchall()
        return [str(r["fl_client_id"]) for r in rows]

    def create_client_user_invite(
        self,
        tenant_id: str,
        *,
        email: str | None,
        fl_client_ids: list[str],
        expires_in_days: int,
        created_by_firebase_uid: str,
    ) -> tuple[str, str]:
        invite_id = f"inv-{secrets.token_hex(8)}"
        token = secrets.token_urlsafe(32)
        days = max(1, min(expires_in_days, 365))
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO client_user_invites
                    (id, tenant_id, invite_token, email, fl_client_ids, expires_at, created_by_firebase_uid)
                VALUES (%s, %s, %s, %s, %s, NOW() + (%s::INTEGER * INTERVAL '1 day'), %s)
                """,
                (
                    invite_id,
                    tenant_id,
                    token,
                    (email or "").lower() or None,
                    list(fl_client_ids),
                    days,
                    created_by_firebase_uid,
                ),
            )
            conn.commit()
        return invite_id, token

    def accept_client_user_invite(self, *, firebase_uid: str, email: str | None, token: str) -> SessionInfo:
        now = _now_iso()
        em = (email or "").lower() or None
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM client_user_invites WHERE invite_token = %s FOR UPDATE
                """,
                (token,),
            )
            inv = cur.fetchone()
            if inv is None:
                raise ValueError("INVALID_INVITE_TOKEN")
            if inv.get("consumed_at"):
                raise ValueError("INVITE_ALREADY_USED")
            req_email = inv.get("email")
            if req_email and em and str(req_email).lower() != em:
                raise ValueError("INVITE_EMAIL_MISMATCH")
            tenant_id = str(inv["tenant_id"])
            fl_ids = list(inv["fl_client_ids"] or [])
            cur.execute(
                "UPDATE memberships SET is_default = FALSE WHERE firebase_uid = %s",
                (firebase_uid,),
            )
            cur.execute(
                """
                INSERT INTO memberships (tenant_id, firebase_uid, role, is_default, created_at)
                VALUES (%s, %s, 'client_user', TRUE, %s)
                ON CONFLICT (tenant_id, firebase_uid) DO UPDATE SET
                    role = 'client_user',
                    is_default = EXCLUDED.is_default
                """,
                (tenant_id, firebase_uid, now),
            )
            cur.execute(
                "DELETE FROM membership_client_scopes WHERE tenant_id = %s AND firebase_uid = %s",
                (tenant_id, firebase_uid),
            )
            for cid in fl_ids:
                cur.execute(
                    """
                    INSERT INTO membership_client_scopes (tenant_id, firebase_uid, fl_client_id)
                    VALUES (%s, %s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (tenant_id, firebase_uid, cid),
                )
            cur.execute(
                """
                UPDATE client_user_invites
                SET consumed_at = NOW(), consumed_by_firebase_uid = %s
                WHERE id = %s
                """,
                (firebase_uid, str(inv["id"])),
            )
            conn.commit()
        return self.ensure_session_user(
            firebase_uid=firebase_uid,
            email=email,
            display_name=None,
            photo_url=None,
            account_type="CLIENT_USER",
        )

    def get_membership(self, firebase_uid: str) -> tuple[str, str] | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT tenant_id, role
                FROM memberships
                WHERE firebase_uid = %s
                ORDER BY is_default DESC, created_at ASC
                LIMIT 1
                """,
                (firebase_uid,),
            )
            row = cur.fetchone()
        if not row:
            return None
        return str(row["tenant_id"]), str(row["role"])

    def list_alerts(
        self,
        tenant_id: str,
        *,
        limit: int = 50,
        cursor: str | None = None,
        severity: str | None = None,
        tactic: str | None = None,
        status: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        sort: str = "timestamp_desc",
        fl_client_ids: list[str] | None = None,
    ) -> tuple[list[Alert], str | None, int]:
        order_by = "a.timestamp DESC"
        if sort == "timestamp_asc":
            order_by = "a.timestamp ASC"
        elif sort == "severity_desc":
            order_by = (
                "CASE a.severity WHEN 'CRITICAL' THEN 4 WHEN 'HIGH' THEN 3 WHEN 'MEDIUM' THEN 2 ELSE 1 END DESC, a.timestamp DESC"
            )

        clauses = ["a.tenant_id = %s"]
        params: list[Any] = [tenant_id]
        if severity:
            clauses.append("a.severity = %s")
            params.append(severity)
        if tactic:
            clauses.append("a.tactic = %s")
            params.append(tactic)
        if status:
            clauses.append("a.status = %s")
            params.append(status)
        if date_from:
            clauses.append("a.timestamp >= %s")
            params.append(date_from)
        if date_to:
            clauses.append("a.timestamp <= %s")
            params.append(date_to)
        if fl_client_ids is not None:
            if not fl_client_ids:
                clauses.append("FALSE")
            else:
                clauses.append(
                    """EXISTS (
                    SELECT 1 FROM devices d
                    WHERE d.tenant_id = a.tenant_id AND d.id = a.device_id AND d.fl_client_id = ANY(%s)
                )"""
                )
                params.append(fl_client_ids)

        where_sql = " AND ".join(clauses)
        start = _decode_cursor(cursor)
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) AS total FROM alerts a WHERE {where_sql}", params)
            total = int(cur.fetchone()["total"])
            cur.execute(
                f"""
                SELECT a.* FROM alerts a
                WHERE {where_sql}
                ORDER BY {order_by}
                OFFSET %s LIMIT %s
                """,
                [*params, start, min(limit, 200)],
            )
            rows = cur.fetchall()
            device_ids = [str(row["device_id"]) for row in rows]
            devices = self._devices_map(cur, tenant_id, device_ids)
        items = [self._alert_from_row(row, devices[str(row["device_id"])]) for row in rows]
        next_cursor = _encode_cursor(start + limit) if (start + limit) < total else None
        return items, next_cursor, total

    def get_alert(self, tenant_id: str, alert_id: str, *, fl_client_ids: list[str] | None = None) -> Alert | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM alerts WHERE tenant_id = %s AND id = %s", (tenant_id, alert_id))
            row = cur.fetchone()
            if not row:
                return None
            device = self._get_device(cur, tenant_id, str(row["device_id"]))
        alert = self._alert_from_row(row, device)
        if fl_client_ids is not None:
            if not fl_client_ids or alert.device.fl_client_id not in fl_client_ids:
                return None
        return alert

    def update_alert_status(self, tenant_id: str, alert_id: str, status: AlertStatus, actor_uid: str | None = None) -> Alert | None:
        now = _now_iso()
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE alerts
                SET status = %s, updated_at = %s
                WHERE tenant_id = %s AND id = %s
                RETURNING *
                """,
                (status.value, now, tenant_id, alert_id),
            )
            row = cur.fetchone()
            if not row:
                return None
            device = self._get_device(cur, tenant_id, str(row["device_id"]))
            if actor_uid:
                self._append_audit(
                    cur,
                    tenant_id=tenant_id,
                    actor_firebase_uid=actor_uid,
                    actor_label=actor_uid,
                    action=AuditAction.RESPONSE_TRIGGERED.value,
                    target_type="alert",
                    target_id=alert_id,
                    result=f"Status changed to {status.value}",
                    metadata={"status": status.value},
                )
            conn.commit()
        return self._alert_from_row(row, device)

    def list_devices(
        self,
        tenant_id: str,
        *,
        wing: str | None = None,
        status: str | None = None,
        type: str | None = None,
        fl_client_ids: list[str] | None = None,
    ) -> list[Device]:
        if fl_client_ids is not None and not fl_client_ids:
            return []
        clauses = ["d.tenant_id = %s"]
        params: list[Any] = [tenant_id]
        if wing:
            clauses.append("d.wing = %s")
            params.append(wing)
        if status:
            clauses.append("d.status = %s")
            params.append(status)
        if type:
            clauses.append("d.type = %s")
            params.append(type)
        if fl_client_ids is not None:
            clauses.append("d.fl_client_id = ANY(%s)")
            params.append(fl_client_ids)
        # Only return devices whose fl_client is DEVICE-type — PERSON clients have no IoT devices
        clauses.append(
            "EXISTS (SELECT 1 FROM fl_clients fc WHERE fc.tenant_id = d.tenant_id AND fc.id = d.fl_client_id AND fc.client_type = 'DEVICE')"
        )
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT d.* FROM devices d WHERE {' AND '.join(clauses)} ORDER BY d.id ASC",
                params,
            )
            rows = cur.fetchall()
        return [self._device_from_row(row) for row in rows]

    def get_device(self, tenant_id: str, device_id: str, *, fl_client_ids: list[str] | None = None) -> Device | None:
        with self._connect() as conn, conn.cursor() as cur:
            dev = self._get_device(cur, tenant_id, device_id)
            if not dev:
                return None
            # Reject devices belonging to PERSON-type fl_clients
            cur.execute(
                "SELECT client_type FROM fl_clients WHERE tenant_id = %s AND id = %s",
                (tenant_id, dev.fl_client_id),
            )
            fc_row = cur.fetchone()
            if not fc_row or str(fc_row["client_type"]) == "PERSON":
                return None
        if fl_client_ids is not None:
            if not fl_client_ids or dev.fl_client_id not in fl_client_ids:
                return None
        return dev

    def quarantine_device(self, tenant_id: str, device_id: str, actor_uid: str) -> dict[str, Any] | None:
        now = _now_iso()
        cmd_id = f"CMD-{int(time.time() * 1000)}"
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE devices SET status = %s, updated_at = %s WHERE tenant_id = %s AND id = %s RETURNING *",
                (DeviceStatus.ISOLATED.value, now, tenant_id, device_id),
            )
            row = cur.fetchone()
            if not row:
                return None
            cur.execute(
                "UPDATE alerts SET updated_at = %s WHERE tenant_id = %s AND device_id = %s",
                (now, tenant_id, device_id),
            )
            self._append_audit(
                cur,
                tenant_id=tenant_id,
                actor_firebase_uid=actor_uid,
                actor_label=actor_uid,
                action=AuditAction.DEVICE_QUARANTINED.value,
                target_type="device",
                target_id=device_id,
                result=f"Isolation command {cmd_id} dispatched",
                metadata={"status": "ISOLATED"},
            )
            conn.commit()
        return {"deviceId": device_id, "status": "ISOLATED", "commandId": cmd_id, "sentAt": now}

    def list_incidents(
        self,
        tenant_id: str,
        *,
        limit: int = 100,
        cursor: str | None = None,
        status: str | None = None,
        severity: str | None = None,
        assignee: str | None = None,
        fl_client_ids: list[str] | None = None,
    ) -> tuple[list[Incident], str | None, int]:
        clauses = ["i.tenant_id = %s"]
        params: list[Any] = [tenant_id]
        if status:
            clauses.append("i.status = %s")
            params.append(status)
        if severity:
            clauses.append("i.severity = %s")
            params.append(severity)
        if assignee:
            clauses.append("i.assignee = %s")
            params.append(assignee)
        if fl_client_ids is not None:
            if not fl_client_ids:
                clauses.append("FALSE")
            else:
                clauses.append(
                    """EXISTS (
                    SELECT 1
                    FROM jsonb_array_elements_text(i.affected_device_ids_json) AS aid(dev_id)
                    JOIN devices d ON d.tenant_id = i.tenant_id AND d.id = aid.dev_id
                    WHERE d.fl_client_id = ANY(%s)
                )"""
                )
                params.append(fl_client_ids)
        where_sql = " AND ".join(clauses)
        start = _decode_cursor(cursor)
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) AS total FROM incidents i WHERE {where_sql}", params)
            total = int(cur.fetchone()["total"])
            cur.execute(
                f"SELECT i.* FROM incidents i WHERE {where_sql} ORDER BY i.created DESC OFFSET %s LIMIT %s",
                [*params, start, limit],
            )
            rows = cur.fetchall()
            ids = [str(row["id"]) for row in rows]
            events = self._incident_events_by_incident(cur, tenant_id, ids)
            devices = self._devices_map(cur, tenant_id)
        items = [self._incident_from_row(row, devices, events.get(str(row["id"]), [])) for row in rows]
        next_cursor = _encode_cursor(start + limit) if (start + limit) < total else None
        return items, next_cursor, total

    def get_incident(self, tenant_id: str, incident_id: str, *, fl_client_ids: list[str] | None = None) -> Incident | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM incidents WHERE tenant_id = %s AND id = %s", (tenant_id, incident_id))
            row = cur.fetchone()
            if not row:
                return None
            events = self._incident_events_by_incident(cur, tenant_id, [incident_id]).get(incident_id, [])
            devices = self._devices_map(cur, tenant_id)
        inc = self._incident_from_row(row, devices, events)
        if fl_client_ids is not None:
            if not fl_client_ids or not any(d.fl_client_id in fl_client_ids for d in inc.affected_devices):
                return None
        return inc

    def run_playbook(self, tenant_id: str, incident_id: str, actor_uid: str) -> tuple[Incident | None, int | None, str]:
        now_iso = _now_iso()
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM incidents WHERE tenant_id = %s AND id = %s", (tenant_id, incident_id))
            row = cur.fetchone()
            if not row:
                return None, None, now_iso
            playbook = Playbook.model_validate(row["playbook_json"])
            current_step = 1
            if playbook.steps:
                step_idx = next((idx for idx, step in enumerate(playbook.steps) if step.status in ("PENDING", "RUNNING")), 0)
                current_step = playbook.steps[step_idx].step_number
                playbook.steps[step_idx] = playbook.steps[step_idx].model_copy(update={"status": "RUNNING", "timestamp": now_iso})
            playbook = playbook.model_copy(update={"executions": playbook.executions + 1, "last_run": now_iso, "status": "ACTIVE"})
            cur.execute(
                "UPDATE incidents SET playbook_json = %s::jsonb, updated_at = %s WHERE tenant_id = %s AND id = %s",
                (Json(playbook.model_dump(mode="json")), now_iso, tenant_id, incident_id),
            )
            self._insert_incident_event(cur, tenant_id=tenant_id, incident_id=incident_id, event=IncidentEvent(id=f"ps-{int(time.time() * 1000)}", timestamp=now_iso, type="PLAYBOOK_START", description="Playbook run started"))
            self._append_audit(cur, tenant_id=tenant_id, actor_firebase_uid=actor_uid, actor_label=actor_uid, action=AuditAction.RESPONSE_TRIGGERED.value, target_type="incident", target_id=incident_id, result=f"Playbook run started (step {current_step})", metadata={"step": current_step})
            conn.commit()
        return self.get_incident(tenant_id, incident_id), current_step, now_iso

    def patch_incident_status(self, tenant_id: str, *, incident_id: str, status: IncidentStatus, assignee: str, notes: str | None, actor_uid: str) -> Incident | None:
        now = _now_iso()
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1 FROM incidents WHERE tenant_id = %s AND id = %s", (tenant_id, incident_id))
            if not cur.fetchone():
                return None
            cur.execute(
                "UPDATE incidents SET status = %s, assignee = %s, updated_at = %s WHERE tenant_id = %s AND id = %s",
                (status.value, assignee, now, tenant_id, incident_id),
            )
            event_type = "RESOLVED" if status == IncidentStatus.RESOLVED else "ANALYST_ASSIGNED"
            self._insert_incident_event(cur, tenant_id=tenant_id, incident_id=incident_id, event=IncidentEvent(id=f"ev-{int(time.time() * 1000)}", timestamp=now, type=event_type, description=notes or f"Incident status updated to {status.value}"))
            self._append_audit(cur, tenant_id=tenant_id, actor_firebase_uid=actor_uid, actor_label=actor_uid, action=AuditAction.RESPONSE_TRIGGERED.value, target_type="incident", target_id=incident_id, result=f"{status.value}: {notes or f'Incident status updated to {status.value}'}", metadata={})
            conn.commit()
        return self.get_incident(tenant_id, incident_id)

    def patch_playbook_step(self, tenant_id: str, *, incident_id: str, step_id: str, status: str, notes: str | None, actor_uid: str) -> Any | None:
        if status not in ("COMPLETED", "RUNNING", "PENDING"):
            return None
        now = _now_iso()
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT playbook_json FROM incidents WHERE tenant_id = %s AND id = %s", (tenant_id, incident_id))
            row = cur.fetchone()
            if not row:
                return None
            playbook = Playbook.model_validate(row["playbook_json"])
            updated_step = None
            for idx, step in enumerate(playbook.steps):
                if step.id == step_id:
                    updated_step = step.model_copy(update={"status": status, "timestamp": now, "notes": notes})
                    playbook.steps[idx] = updated_step
                    break
            if updated_step is None:
                return None
            new_status = None
            if playbook.steps and all(step.status == "COMPLETED" for step in playbook.steps):
                new_status = IncidentStatus.RESOLVED.value
                self._insert_incident_event(cur, tenant_id=tenant_id, incident_id=incident_id, event=IncidentEvent(id=f"ev-{int(time.time() * 1000)}-pb", timestamp=now, type="RESOLVED", description="All playbook steps completed"))
            cur.execute(
                """
                UPDATE incidents
                SET playbook_json = %s::jsonb,
                    status = COALESCE(%s, status),
                    updated_at = %s
                WHERE tenant_id = %s AND id = %s
                """,
                (Json(playbook.model_dump(mode="json")), new_status, now, tenant_id, incident_id),
            )
            self._append_audit(cur, tenant_id=tenant_id, actor_firebase_uid=actor_uid, actor_label=actor_uid, action=AuditAction.RESPONSE_TRIGGERED.value, target_type="incident", target_id=incident_id, result=f"Playbook step {step_id} -> {status}", metadata={"stepId": step_id})
            conn.commit()
        return updated_step

    def halt_playbook(self, tenant_id: str, *, incident_id: str, reason: str, actor_uid: str) -> dict[str, Any] | None:
        now = _now_iso()
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT playbook_json FROM incidents WHERE tenant_id = %s AND id = %s", (tenant_id, incident_id))
            row = cur.fetchone()
            if not row:
                return None
            playbook = Playbook.model_validate(row["playbook_json"])
            running = next((step for step in playbook.steps if step.status == "RUNNING"), None)
            if running is None:
                return {"halted": True, "haltedAt": now, "stoppedAt": None}
            playbook.steps = [step.model_copy(update={"status": "PENDING", "timestamp": now, "notes": reason}) if step.id == running.id else step for step in playbook.steps]
            cur.execute("UPDATE incidents SET playbook_json = %s::jsonb, updated_at = %s WHERE tenant_id = %s AND id = %s", (Json(playbook.model_dump(mode="json")), now, tenant_id, incident_id))
            self._append_audit(cur, tenant_id=tenant_id, actor_firebase_uid=actor_uid, actor_label=actor_uid, action=AuditAction.RESPONSE_TRIGGERED.value, target_type="incident", target_id=incident_id, result=f"Playbook halted: {reason}", metadata={})
            conn.commit()
        return {"halted": True, "haltedAt": now, "stoppedAt": running.id}

    def fl_status_dict(self, tenant_id: str, fl_client_ids: list[str] | None = None) -> dict[str, Any]:
        rounds, session_id = self.list_fl_rounds(tenant_id)
        clients = self.list_fl_clients(tenant_id, fl_client_ids=fl_client_ids)
        current = rounds[-1].round if rounds else 0
        latest = rounds[-1] if rounds else None
        active_clients = sum(1 for c in clients if c.status == FLClientStatus.ACTIVE)
        poison = any(c.status == FLClientStatus.POISONING_SUSPECT for c in clients)
        md = self.fl_models_dict(tenant_id, fl_client_ids=fl_client_ids)
        zoo = sorted({str(m["name"]) for m in md["models"]})
        return {
            "currentRound": current,
            "totalRounds": max(current, 100),
            "activeClients": active_clients,
            "totalClients": len(clients),
            "nextRoundIn": 180,
            "aggregatorStatus": "AGGREGATING" if session_id else "IDLE",
            "latestAccuracy": round(latest.accuracy, 1) if latest else 0.0,
            "latestFpRate": round(latest.fp_rate, 1) if latest else 0.0,
            "driftDetected": poison,
            "activeModel": self._active_model_for_scope(tenant_id, fl_client_ids),
            "modelZoo": zoo,
            "federationScope": "DEMO_RESEARCH" if tenant_id == settings.demo_tenant_id else "LOCAL_RUNTIME_ONLY",
        }

    def get_fl_client(self, tenant_id: str, client_id: str, *, fl_client_ids: list[str] | None = None) -> FLClient | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM fl_clients WHERE tenant_id = %s AND id = %s", (tenant_id, client_id))
            row = cur.fetchone()
        if not row:
            return None
        cl = FLClient.model_validate(row)
        if fl_client_ids is not None:
            if not fl_client_ids or cl.id not in fl_client_ids:
                return None
        return cl

    def list_fl_rounds(self, tenant_id: str) -> tuple[list[FLRound], str]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM fl_rounds WHERE tenant_id = %s ORDER BY round ASC", (tenant_id,))
            rows = cur.fetchall()
            cur.execute("SELECT session_id FROM fl_rounds WHERE tenant_id = %s ORDER BY round DESC LIMIT 1", (tenant_id,))
            row = cur.fetchone()
        return [FLRound.model_validate(r) for r in rows], (str(row["session_id"]) if row else "sess_empty")

    def list_fl_clients(self, tenant_id: str, fl_client_ids: list[str] | None = None) -> list[FLClient]:
        with self._connect() as conn, conn.cursor() as cur:
            if fl_client_ids is not None:
                if not fl_client_ids:
                    rows = []
                else:
                    cur.execute(
                        "SELECT * FROM fl_clients WHERE tenant_id = %s AND id = ANY(%s) ORDER BY id ASC",
                        (tenant_id, fl_client_ids),
                    )
                    rows = cur.fetchall()
            else:
                cur.execute("SELECT * FROM fl_clients WHERE tenant_id = %s ORDER BY id ASC", (tenant_id,))
                rows = cur.fetchall()
        return [FLClient.model_validate(row) for row in rows]

    def patch_fl_client(self, tenant_id: str, client_id: str, *, client_type: FLClientType) -> FLClient | None:
        now = _now_iso()
        ct_val = client_type.value if hasattr(client_type, "value") else str(client_type)
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE fl_clients SET client_type = %s, updated_at = %s
                WHERE tenant_id = %s AND id = %s
                RETURNING *
                """,
                (ct_val, now, tenant_id, client_id),
            )
            row = cur.fetchone()
            conn.commit()
        if not row:
            return None
        return FLClient.model_validate(row)

    def create_fl_client(
        self,
        tenant_id: str,
        *,
        client_id: str,
        node_name: str,
        department: str,
        client_type: FLClientType,
        email: str | None,
        firebase_uid: str | None,
        created_by_uid: str,
    ) -> FLClient:
        now = _now_iso()
        ct = client_type.value if hasattr(client_type, "value") else str(client_type)
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO fl_clients
                    (tenant_id, id, department, participation_pct, last_round, dp_epsilon,
                     model_version, status, client_type, node_name, created_by_firebase_uid, created_at, updated_at)
                VALUES (%s, %s, %s, 0, 0, 1.0, '', 'OFFLINE', %s, %s, %s, %s, %s)
                ON CONFLICT (tenant_id, id) DO NOTHING
                RETURNING *
                """,
                (tenant_id, client_id, department, ct, node_name, created_by_uid, now, now),
            )
            row = cur.fetchone()
            conn.commit()
        if row:
            return FLClient.model_validate(row)
        # Conflict — fetch existing
        existing = self.get_fl_client(tenant_id, client_id)
        if existing:
            return existing
        raise RuntimeError(f"create_fl_client conflict and fetch failed for {client_id}")

    def provision_client_user_access(
        self,
        tenant_id: str,
        firebase_uid: str,
        email: str | None,
        display_name: str | None,
        fl_client_ids: list[str],
    ) -> None:
        now = _now_iso()
        with self._connect() as conn, conn.cursor() as cur:
            # Upsert user record
            cur.execute(
                """
                INSERT INTO users (firebase_uid, email, display_name, photo_url, created_at, last_login_at)
                VALUES (%s, %s, %s, NULL, %s, %s)
                ON CONFLICT (firebase_uid) DO UPDATE SET
                    email = COALESCE(EXCLUDED.email, users.email),
                    display_name = COALESCE(EXCLUDED.display_name, users.display_name),
                    last_login_at = EXCLUDED.last_login_at
                """,
                (firebase_uid, email, display_name, now, now),
            )
            # Demote existing default memberships for this user
            cur.execute(
                "UPDATE memberships SET is_default = FALSE WHERE firebase_uid = %s",
                (firebase_uid,),
            )
            # Upsert membership as client_user on this tenant
            cur.execute(
                """
                INSERT INTO memberships (tenant_id, firebase_uid, role, is_default, created_at)
                VALUES (%s, %s, 'client_user', TRUE, %s)
                ON CONFLICT (tenant_id, firebase_uid) DO UPDATE SET
                    role = 'client_user',
                    is_default = EXCLUDED.is_default
                """,
                (tenant_id, firebase_uid, now),
            )
            # Replace client scopes
            cur.execute(
                "DELETE FROM membership_client_scopes WHERE tenant_id = %s AND firebase_uid = %s",
                (tenant_id, firebase_uid),
            )
            for cid in fl_client_ids:
                cur.execute(
                    """
                    INSERT INTO membership_client_scopes (tenant_id, firebase_uid, fl_client_id)
                    VALUES (%s, %s, %s) ON CONFLICT DO NOTHING
                    """,
                    (tenant_id, firebase_uid, cid),
                )
            conn.commit()

    def get_tenant_name(self, tenant_id: str) -> str | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT name FROM tenants WHERE id = %s", (tenant_id,))
            row = cur.fetchone()
        return str(row["name"]) if row and row.get("name") else None

    def count_fl_clients_by_creator(self, tenant_id: str, firebase_uid: str) -> int:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) AS c FROM fl_clients
                WHERE tenant_id = %s AND created_by_firebase_uid = %s
                """,
                (tenant_id, firebase_uid),
            )
            row = cur.fetchone()
        return int(row["c"]) if row else 0

    def list_client_user_invites(self, tenant_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, email, fl_client_ids, expires_at, created_at, consumed_at
                FROM client_user_invites
                WHERE tenant_id = %s
                ORDER BY created_at DESC
                """,
                (tenant_id,),
            )
            rows = cur.fetchall()

        def _ts(v: Any) -> str:
            if v is None:
                return ""
            if hasattr(v, "isoformat"):
                return v.isoformat().replace("+00:00", "Z")
            return str(v)

        out: list[dict[str, Any]] = []
        for r in rows:
            consumed = r.get("consumed_at")
            out.append(
                {
                    "invite_id": str(r["id"]),
                    "email": r.get("email"),
                    "fl_client_ids": list(r["fl_client_ids"] or []),
                    "expires_at": _ts(r["expires_at"]),
                    "created_at": _ts(r["created_at"]),
                    "consumed_at": _ts(consumed) if consumed is not None else None,
                }
            )
        return out

    def fl_drift_dict(self, tenant_id: str, fl_client_ids: list[str] | None = None) -> dict[str, Any]:
        rounds, _ = self.list_fl_rounds(tenant_id)
        clients = self.list_fl_clients(tenant_id, fl_client_ids=fl_client_ids)
        latest_round = rounds[-1].round if rounds else 0
        latest_acc = rounds[-1].accuracy if rounds else 0.0
        baseline_acc = rounds[-6].accuracy if len(rounds) >= 6 else latest_acc
        entries: list[dict[str, Any]] = []
        for client in clients:
            rounds_ago = max(0, latest_round - client.last_round)
            flagged = client.status in (FLClientStatus.POISONING_SUSPECT, FLClientStatus.DEGRADED)
            drift = round(max(0.01, (baseline_acc - latest_acc) / max(1.0, 100.0) + (0.06 if flagged else 0.02)), 2)
            entries.append({"clientId": client.id, "department": client.department, "roundsAgo": rounds_ago, "driftScore": drift, "baselineAccuracy": round(baseline_acc, 1), "currentAccuracy": round(latest_acc, 1), "flagged": flagged})
        peak = max((float(item["driftScore"]) for item in entries), default=0.0)
        base: dict[str, Any] = {
            "entries": entries,
            "available": True,
            "driftScores": [
                {
                    "model": "Per-client drift overlay",
                    "score": peak,
                    "peakScore": peak,
                    "status": "DEMO_RESEARCH",
                    "samples": len(entries),
                    "lastEvent": "External client telemetry not connected",
                }
            ],
            "overallDrift": peak,
            "overallStatus": "DEMO_RESEARCH",
            "driftDetected": any(bool(item["flagged"]) for item in entries),
            "nReferenceImages": 0,
            "samplesAnalyzed": len(entries),
            "checkedAt": _now_iso(),
            "scope": "DEMO_RESEARCH",
            "operatorUse": "Per-client drift remains demo/research unless external client telemetry is connected.",
        }
        base.update(_fl_drift_semantics_overlay())
        return base

    def fl_models_dict(self, tenant_id: str, *, fl_client_ids: list[str] | None = None) -> dict[str, Any]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM model_registry WHERE tenant_id = %s ORDER BY name ASC", (tenant_id,))
            rows = cur.fetchall()
        models = [self._model_registry_payload(row) for row in rows]
        if fl_client_ids is not None:
            allow = set(fl_client_ids)
            models = [
                m
                for m in models
                if m.get("flClientId") is None or str(m.get("flClientId")) in allow or m.get("modelScope") == "global"
            ]
        return {"models": models}

    def activate_fl_model(
        self,
        tenant_id: str,
        model_name: str,
        actor_uid: str,
        *,
        fl_client_id: str | None = None,
    ) -> tuple[str | None, str, bool]:
        now = _now_iso()
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1 FROM model_registry WHERE tenant_id = %s AND name = %s", (tenant_id, model_name))
            if not cur.fetchone():
                return None, now, False
            if fl_client_id:
                cur.execute(
                    "SELECT model_name FROM fl_client_active_models WHERE tenant_id = %s AND fl_client_id = %s",
                    (tenant_id, fl_client_id),
                )
                prev_row = cur.fetchone()
                prev = str(prev_row["model_name"]) if prev_row else None
                cur.execute(
                    "SELECT fl_client_id, model_scope FROM model_registry WHERE tenant_id = %s AND name = %s",
                    (tenant_id, model_name),
                )
                mrow = cur.fetchone()
                if not mrow:
                    return None, now, False
                mcid = mrow.get("fl_client_id")
                mscope = str(mrow.get("model_scope") or "tenant")
                if mcid and str(mcid) != str(fl_client_id):
                    return None, now, False
                if mcid is None and mscope not in ("tenant", "global"):
                    return None, now, False
                cur.execute(
                    """
                    INSERT INTO fl_client_active_models (tenant_id, fl_client_id, model_name, updated_at, updated_by_uid)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (tenant_id, fl_client_id) DO UPDATE SET
                        model_name = EXCLUDED.model_name,
                        updated_at = EXCLUDED.updated_at,
                        updated_by_uid = EXCLUDED.updated_by_uid
                    """,
                    (tenant_id, fl_client_id, model_name, now, actor_uid),
                )
                self._append_audit(
                    cur,
                    tenant_id=tenant_id,
                    actor_firebase_uid=actor_uid,
                    actor_label=actor_uid,
                    action=AuditAction.MODEL_UPDATED.value,
                    target_type="model",
                    target_id=model_name,
                    result=f"Activated model {model_name} for client {fl_client_id}",
                    metadata={"flClientId": fl_client_id},
                )
                conn.commit()
                return prev, now, True
            cur.execute("SELECT name FROM model_registry WHERE tenant_id = %s AND is_active = TRUE LIMIT 1", (tenant_id,))
            current = cur.fetchone()
            cur.execute("UPDATE model_registry SET is_active = FALSE, updated_at = %s WHERE tenant_id = %s", (now, tenant_id))
            cur.execute("UPDATE model_registry SET is_active = TRUE, updated_at = %s WHERE tenant_id = %s AND name = %s", (now, tenant_id, model_name))
            self._append_audit(cur, tenant_id=tenant_id, actor_firebase_uid=actor_uid, actor_label=actor_uid, action=AuditAction.MODEL_UPDATED.value, target_type="model", target_id=model_name, result=f"Activated model {model_name}", metadata={})
            conn.commit()
        return (str(current["name"]) if current else None), now, True

    def upload_fl_model_file(
        self,
        tenant_id: str,
        *,
        file: Any,
        name: str,
        model_type: str,
        description: str,
        trained_on: str,
        size_label: str,
        accuracy: float,
        fp_rate: float,
        fl_client_id: str | None,
        actor_uid: str,
    ) -> dict[str, Any] | None:
        from app.services.supabase_storage import upload_model_bytes

        safe_name = "".join(c for c in name.strip() if c.isalnum() or c in ("-", "_", "."))[:80] or "model"
        data = file.file.read() if hasattr(file, "file") else file.read()
        fname = getattr(file, "filename", "model.bin") or "model.bin"
        safe_file = "".join(c for c in fname if c.isalnum() or c in (".", "-", "_"))[:120] or "upload.bin"
        now = _now_iso()
        if fl_client_id:
            object_name = f"{tenant_id}/clients/{fl_client_id}/models/{safe_name}/{safe_file}"
            scope = "client"
        else:
            object_name = f"global/{safe_name}/{safe_file}"
            scope = "global"
        storage_path = upload_model_bytes(data=data, object_name=object_name)
        if not storage_path:
            return None
        bucket, obj_key = storage_path.split("/", 1)
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO model_registry
                    (tenant_id, name, model_type, accuracy, fp_rate, size, trained_on, description, is_active,
                     created_at, updated_at, fl_client_id, storage_path, model_scope)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, FALSE, %s, %s, %s, %s, %s)
                ON CONFLICT (tenant_id, name) DO UPDATE SET
                    model_type = EXCLUDED.model_type,
                    accuracy = EXCLUDED.accuracy,
                    fp_rate = EXCLUDED.fp_rate,
                    size = EXCLUDED.size,
                    trained_on = EXCLUDED.trained_on,
                    description = EXCLUDED.description,
                    updated_at = EXCLUDED.updated_at,
                    fl_client_id = EXCLUDED.fl_client_id,
                    storage_path = EXCLUDED.storage_path,
                    model_scope = EXCLUDED.model_scope
                """,
                (
                    tenant_id,
                    safe_name,
                    model_type[:32],
                    accuracy,
                    fp_rate,
                    size_label[:64],
                    trained_on[:64],
                    description[:2000],
                    now,
                    now,
                    fl_client_id,
                    f"{bucket}/{obj_key}",
                    scope,
                ),
            )
            self._append_audit(
                cur,
                tenant_id=tenant_id,
                actor_firebase_uid=actor_uid,
                actor_label=actor_uid,
                action=AuditAction.MODEL_UPDATED.value,
                target_type="model",
                target_id=safe_name,
                result="Model file uploaded",
                metadata={"storagePath": f"{bucket}/{obj_key}", "flClientId": fl_client_id},
            )
            conn.commit()
        return self._model_registry_payload(
            {
                "name": safe_name,
                "model_type": model_type[:32],
                "accuracy": accuracy,
                "fp_rate": fp_rate,
                "size": size_label[:64],
                "trained_on": trained_on[:64],
                "description": description[:2000],
                "is_active": False,
                "fl_client_id": fl_client_id,
                "storage_path": f"{bucket}/{obj_key}",
                "model_scope": scope,
            }
        )

    def sync_global_model_bundles_from_disk(
        self,
        tenant_id: str,
        *,
        actor_uid: str,
    ) -> dict[str, Any]:
        """Upload canonical weights from backend/data/models into the models bucket (global/*) and upsert registry rows (.pth only)."""
        from pathlib import Path

        from app.services.supabase_storage import upload_model_bytes

        backend_root = Path(__file__).resolve().parents[2]
        pytorch_global = backend_root / "data" / "models" / "pytorch" / "global"
        drift_dir = backend_root / "data" / "models" / "drift"

        known_bundles: list[tuple[str, str, str, str]] = [
            ("generic-global-resnet", "CNN", "Bundled global ResNet (data/models/pytorch/global)", "fl_global_resnet.pth"),
            ("generic-global-dnn", "DNN", "Bundled global DNN (data/models/pytorch/global)", "fl_global_dnn.pth"),
            ("generic-global-meta", "HYB", "Bundled global meta-fusion (data/models/pytorch/global)", "fl_global_meta.pth"),
        ]
        known_names = {t[3] for t in known_bundles}

        uploaded: list[str] = []
        registered: list[str] = []
        skipped_missing: list[str] = []
        storage_failed: list[str] = []
        drift_object: str | None = None
        now = _now_iso()

        def _upsert_registry(
            *,
            reg_name: str,
            model_type: str,
            description: str,
            size_label: str,
            storage_full: str,
        ) -> None:
            with self._connect() as conn, conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO model_registry
                        (tenant_id, name, model_type, accuracy, fp_rate, size, trained_on, description, is_active,
                         created_at, updated_at, fl_client_id, storage_path, model_scope)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, FALSE, %s, %s, NULL, %s, %s)
                    ON CONFLICT (tenant_id, name) DO UPDATE SET
                        model_type = EXCLUDED.model_type,
                        accuracy = EXCLUDED.accuracy,
                        fp_rate = EXCLUDED.fp_rate,
                        size = EXCLUDED.size,
                        trained_on = EXCLUDED.trained_on,
                        description = EXCLUDED.description,
                        updated_at = EXCLUDED.updated_at,
                        fl_client_id = EXCLUDED.fl_client_id,
                        storage_path = EXCLUDED.storage_path,
                        model_scope = EXCLUDED.model_scope
                    """,
                    (
                        tenant_id,
                        reg_name,
                        model_type[:32],
                        0.0,
                        0.0,
                        size_label[:64],
                        now[:64],
                        description[:2000],
                        now,
                        now,
                        storage_full,
                        "global",
                    ),
                )
                self._append_audit(
                    cur,
                    tenant_id=tenant_id,
                    actor_firebase_uid=actor_uid,
                    actor_label=actor_uid,
                    action=AuditAction.MODEL_UPDATED.value,
                    target_type="model",
                    target_id=reg_name,
                    result="Global model bundle synced from disk",
                    metadata={"storagePath": storage_full},
                )
                conn.commit()

        def _process_pth_file(*, reg_name: str, model_type: str, description: str, path: Path) -> None:
            data = path.read_bytes()
            object_name = f"global/{path.name}"
            storage_path = upload_model_bytes(data=data, object_name=object_name)
            if not storage_path:
                storage_failed.append(path.name)
                return
            bucket, obj_key = storage_path.split("/", 1)
            full_sp = f"{bucket}/{obj_key}"
            uploaded.append(full_sp)
            _upsert_registry(
                reg_name=reg_name,
                model_type=model_type,
                description=description,
                size_label=f"{len(data)} bytes",
                storage_full=full_sp,
            )
            registered.append(reg_name)

        for reg_name, mtype, desc, fname in known_bundles:
            p = pytorch_global / fname
            if not p.is_file():
                skipped_missing.append(fname)
                continue
            _process_pth_file(reg_name=reg_name, model_type=mtype, description=desc, path=p)

        if pytorch_global.is_dir():
            for path in sorted(pytorch_global.glob("*.pth")):
                if path.name in known_names:
                    continue
                stem = "".join(c for c in path.stem if c.isalnum() or c in ("-", "_", "."))[:72] or "model"
                reg_name = f"generic-file-{stem}"
                _process_pth_file(reg_name=reg_name, model_type="CUSTOM", description=f"Synced from disk: {path.name}", path=path)

        drift_fp = drift_dir / "drift_reference.npz"
        if drift_fp.is_file():
            blob = drift_fp.read_bytes()
            sp = upload_model_bytes(data=blob, object_name=f"global/{drift_fp.name}")
            if sp:
                drift_object = sp
            else:
                storage_failed.append(drift_fp.name)

        return {
            "uploaded": uploaded,
            "registered": registered,
            "skippedMissing": skipped_missing,
            "storageFailed": storage_failed,
            "driftObject": drift_object,
        }

    def list_client_artifacts(
        self,
        tenant_id: str,
        *,
        fl_client_id: str | None = None,
        label: str | None = None,
        limit: int = 100,
        fl_client_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        clauses = ["tenant_id = %s"]
        params: list[Any] = [tenant_id]
        if fl_client_id:
            clauses.append("fl_client_id = %s")
            params.append(fl_client_id)
        if label in ("benign", "malware"):
            clauses.append("label = %s")
            params.append(label)
        if fl_client_ids is not None:
            if not fl_client_ids:
                return []
            clauses.append("fl_client_id = ANY(%s)")
            params.append(fl_client_ids)
        where_sql = " AND ".join(clauses)
        lim = max(1, min(int(limit), 500))
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT * FROM client_artifacts WHERE {where_sql} ORDER BY created_at DESC LIMIT %s",
                [*params, lim],
            )
            rows = cur.fetchall()
        return [dict(r) for r in rows]

    def upload_client_artifact(
        self,
        tenant_id: str,
        *,
        fl_client_id: str,
        label: str,
        file: Any,
        notes: str | None,
        actor_uid: str,
    ) -> dict[str, Any] | None:
        from app.services.supabase_storage import upload_artifact_bytes

        if label not in ("benign", "malware"):
            return None
        data = file.file.read() if hasattr(file, "file") else file.read()
        fname = getattr(file, "filename", "artifact.bin") or "artifact.bin"
        ext = fname.rsplit(".", 1)[-1].lower() if "." in fname else ""
        kind = "json" if ext == "json" else ("image" if ext in ("png", "jpg", "jpeg", "webp", "gif") else "other")
        now = _now_iso()
        sha256 = hashlib.sha256(data).hexdigest()
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM fl_clients WHERE tenant_id = %s AND id = %s",
                (tenant_id, fl_client_id),
            )
            if not cur.fetchone():
                return None
            cur.execute(
                "SELECT id FROM client_artifacts WHERE tenant_id = %s ORDER BY id DESC LIMIT 1",
                (tenant_id,),
            )
            row = cur.fetchone()
            next_num = int(str(row["id"]).split("-")[-1]) + 1 if row else 1
            art_id = f"ART-{next_num:05d}"
            safe_fn = "".join(c for c in fname if c.isalnum() or c in (".", "-", "_"))[:120] or "file"
            object_name = f"{tenant_id}/{fl_client_id}/{label}/{art_id}_{safe_fn}"
            storage_path = upload_artifact_bytes(data=data, object_name=object_name)
            if not storage_path:
                bucket = settings.supabase_artifacts_bucket
                object_key = object_name
            else:
                bucket, object_key = storage_path.split("/", 1)
            cur.execute(
                """
                INSERT INTO client_artifacts
                    (tenant_id, id, fl_client_id, label, kind, filename, sha256, size_bytes,
                     storage_bucket, storage_object_key, status, notes, uploaded_by_uid, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    tenant_id,
                    art_id,
                    fl_client_id,
                    label,
                    kind,
                    fname[:255],
                    sha256,
                    len(data),
                    bucket,
                    object_key,
                    "UPLOADED" if storage_path else "PENDING_STORAGE",
                    (notes or "")[:2000],
                    actor_uid,
                    now,
                    now,
                ),
            )
            self._append_audit(
                cur,
                tenant_id=tenant_id,
                actor_firebase_uid=actor_uid,
                actor_label=actor_uid,
                action=AuditAction.DETECTION_MADE.value,
                target_type="client_artifact",
                target_id=art_id,
                result="Client artifact uploaded",
                metadata={"flClientId": fl_client_id, "label": label, "kind": kind},
            )
            conn.commit()
            cur.execute("SELECT * FROM client_artifacts WHERE tenant_id = %s AND id = %s", (tenant_id, art_id))
            out = cur.fetchone()
        return dict(out) if out else None

    def list_samples(
        self,
        tenant_id: str,
        *,
        limit: int = 50,
        cursor: str | None = None,
        status: str | None = None,
        family: str | None = None,
        fl_client_ids: list[str] | None = None,
    ) -> tuple[list[MalwareSample], str | None, int]:
        clauses = ["m.tenant_id = %s"]
        params: list[Any] = [tenant_id]
        if status:
            clauses.append("m.status = %s")
            params.append(status)
        if family:
            clauses.append("m.family = %s")
            params.append(family)
        if fl_client_ids is not None:
            if not fl_client_ids:
                clauses.append("FALSE")
            else:
                clauses.append(
                    """EXISTS (
                    SELECT 1 FROM devices d
                    WHERE d.tenant_id = m.tenant_id AND d.id = m.device_id AND d.fl_client_id = ANY(%s)
                )"""
                )
                params.append(fl_client_ids)
        where_sql = " AND ".join(clauses)
        start = _decode_cursor(cursor)
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) AS total FROM malware_samples m WHERE {where_sql}", params)
            total = int(cur.fetchone()["total"])
            cur.execute(
                f"SELECT m.* FROM malware_samples m WHERE {where_sql} ORDER BY m.upload_time DESC OFFSET %s LIMIT %s",
                [*params, start, limit],
            )
            rows = cur.fetchall()
        items = [self._sample_from_row(row) for row in rows]
        next_cursor = _encode_cursor(start + limit) if (start + limit) < total else None
        return items, next_cursor, total

    def escalate_alert(
        self, tenant_id: str, alert_id: str, actor_uid: str, *, fl_client_ids: list[str] | None = None
    ) -> Incident | None:
        from app.routers.alerts import _build_incident_from_alert  # local import to avoid cycle at module load

        alert = self.get_alert(tenant_id, alert_id, fl_client_ids=fl_client_ids)
        if not alert:
            return None
        incident = _build_incident_from_alert(alert)
        now = _now_iso()
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO incidents
                    (tenant_id, id, title, severity, status, affected_device_ids_json, time_open, analyst_initials, playbook_json, ticket_id, reporter, assignee, priority, created, labels_json, created_by, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s)
                """,
                (tenant_id, incident.id, incident.title, _camel_enum_str(incident.severity), _camel_enum_str(incident.status), Json([device.id for device in incident.affected_devices]), incident.time_open, incident.analyst_initials, Json(incident.playbook.model_dump(mode="json")), incident.ticket_id, incident.reporter, incident.assignee, incident.priority, incident.created, Json(incident.labels), actor_uid, now, now),
            )
            for event in incident.timeline:
                self._insert_incident_event(cur, tenant_id=tenant_id, incident_id=incident.id, event=event)
            self.update_alert_status(tenant_id, alert_id, AlertStatus.IN_REVIEW, actor_uid)
            conn.commit()
        return incident

    def get_sample(self, tenant_id: str, sample_id: str, *, fl_client_ids: list[str] | None = None) -> MalwareSample | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM malware_samples WHERE tenant_id = %s AND id = %s", (tenant_id, sample_id))
            row = cur.fetchone()
        if not row:
            return None
        sample = self._sample_from_row(row)
        if fl_client_ids is not None:
            if not fl_client_ids:
                return None
            dev = self.get_device(tenant_id, sample.device_id, fl_client_ids=fl_client_ids)
            if dev is None:
                return None
        return sample

    def upload_sample(self, tenant_id: str, *, file: Any, device_id: str, notes: str | None, actor_uid: str) -> MalwareSample:
        data = file.file.read() if hasattr(file, "file") else file.read()
        now = _now_iso()
        sha256 = hashlib.sha256(data).hexdigest()
        md5 = hashlib.md5(data).hexdigest()
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT id FROM malware_samples WHERE tenant_id = %s ORDER BY id DESC LIMIT 1", (tenant_id,))
            row = cur.fetchone()
            next_num = int(str(row["id"]).split("-")[-1]) + 1 if row else 1
            sample_id = f"MAL-{next_num:03d}"
            object_name = f"tenants/{tenant_id}/samples/{sample_id}/{sha256[:24]}_{getattr(file, 'filename', 'upload.bin')}"
            storage_path = upload_forensics_bytes(data=data, object_name=object_name)
            bucket = None
            object_key = None
            if storage_path and "/" in storage_path:
                bucket, object_key = storage_path.split("/", 1)
            analysis = SampleAnalysis(static=StaticAnalysis(imports=[], strings=[]), dynamic=DynamicAnalysis(network=[], file_system=[], processes=[]))
            chain_of_custody = [
                {"timestamp": now, "actor": actor_uid, "action": "UPLOADED", "detail": f"Sample uploaded for device {device_id}"},
                {"timestamp": now, "actor": "system", "action": "QUEUED_FOR_SCAN", "detail": "Queued for scanner review"},
            ]
            cur.execute(
                """
                INSERT INTO malware_samples
                    (id, tenant_id, sha256, md5, filename, size, type, device_id, timestamp, upload_time, family, threat_score, status, analysis_json, storage_bucket, storage_object_key, scan_status, quarantine_status, retention_status, chain_of_custody_json, scanner_verdict_json, is_demo, created_by, created_at, updated_at)
                VALUES
                    (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, FALSE, %s, %s, %s)
                """,
                (sample_id, tenant_id, sha256, md5, getattr(file, "filename", "upload.bin"), f"{len(data)} bytes", "UPLOADED", device_id, now, now, notes or "Uploaded Sample", 0, "QUEUED", Json(analysis.model_dump(mode="json")), bucket, object_key, "QUEUED", "NONE", "ACTIVE", Json(chain_of_custody), Json(None), actor_uid, now, now),
            )
            self._append_audit(cur, tenant_id=tenant_id, actor_firebase_uid=actor_uid, actor_label=actor_uid, action=AuditAction.DETECTION_MADE.value, target_type="sample", target_id=sample_id, result="Malware sample uploaded", metadata={"deviceId": device_id})
            conn.commit()
        return self.get_sample(tenant_id, sample_id)  # type: ignore[return-value]

    def run_sample_scan(self, tenant_id: str, *, sample_id: str, actor_uid: str) -> MalwareSample | None:
        sample = self.get_sample(tenant_id, sample_id)
        if not sample:
            return None
        result = scan_forensics_sample(sample_id=sample.id, filename=sample.filename, sha256=sample.sha256)
        now = _now_iso()
        chain_of_custody = list(sample.chain_of_custody)
        chain_of_custody.append({"timestamp": now, "actor": actor_uid, "action": "SCANNED", "detail": result.summary})
        verdict = {"engine": result.engine, "verdict": result.verdict, "confidence": result.confidence, "summary": result.summary}
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE malware_samples
                SET status = 'SCANNED',
                    scan_status = 'SCANNED',
                    scanner_verdict_json = %s::jsonb,
                    chain_of_custody_json = %s::jsonb,
                    updated_at = %s
                WHERE tenant_id = %s AND id = %s
                """,
                (Json(verdict), Json(chain_of_custody), now, tenant_id, sample_id),
            )
            self._append_audit(cur, tenant_id=tenant_id, actor_firebase_uid=actor_uid, actor_label=actor_uid, action=AuditAction.RESPONSE_TRIGGERED.value, target_type="sample", target_id=sample_id, result=f"Sample scanned: {result.verdict}", metadata=verdict)
            conn.commit()
        return self.get_sample(tenant_id, sample_id)

    def update_sample_disposition(self, tenant_id: str, *, sample_id: str, quarantine_status: str | None = None, retention_status: str | None = None, actor_uid: str, detail: str | None = None) -> MalwareSample | None:
        sample = self.get_sample(tenant_id, sample_id)
        if not sample:
            return None
        now = _now_iso()
        chain_of_custody = list(sample.chain_of_custody)
        action = quarantine_status or retention_status or "UPDATED"
        chain_of_custody.append({"timestamp": now, "actor": actor_uid, "action": action, "detail": detail or action})
        status_value = sample.status
        if quarantine_status == "QUARANTINED":
            status_value = "QUARANTINED"
        elif quarantine_status == "RELEASED":
            status_value = "RELEASED"
        if retention_status == "EXPIRED":
            status_value = "EXPIRED"
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE malware_samples
                SET status = %s,
                    quarantine_status = COALESCE(%s, quarantine_status),
                    retention_status = COALESCE(%s, retention_status),
                    chain_of_custody_json = %s::jsonb,
                    updated_at = %s
                WHERE tenant_id = %s AND id = %s
                """,
                (status_value, quarantine_status, retention_status, Json(chain_of_custody), now, tenant_id, sample_id),
            )
            self._append_audit(cur, tenant_id=tenant_id, actor_firebase_uid=actor_uid, actor_label=actor_uid, action=AuditAction.RESPONSE_TRIGGERED.value, target_type="sample", target_id=sample_id, result=detail or action, metadata={"quarantineStatus": quarantine_status, "retentionStatus": retention_status})
            conn.commit()
        return self.get_sample(tenant_id, sample_id, fl_client_ids=None)

    def list_rca_reports(self, tenant_id: str, fl_client_ids: list[str] | None = None) -> tuple[list[RCAReport], int]:
        with self._connect() as conn, conn.cursor() as cur:
            if fl_client_ids is not None:
                if not fl_client_ids:
                    rows = []
                else:
                    cur.execute(
                        """
                    SELECT r.* FROM rca_reports r
                    WHERE r.tenant_id = %s
                      AND EXISTS (
                        SELECT 1
                        FROM incidents i
                        CROSS JOIN LATERAL jsonb_array_elements_text(i.affected_device_ids_json) AS aid(dev_id)
                        JOIN devices d ON d.tenant_id = i.tenant_id AND d.id = aid.dev_id
                        WHERE i.tenant_id = r.tenant_id AND i.id = r.incident_id AND d.fl_client_id = ANY(%s)
                      )
                    ORDER BY r.created_at DESC
                    """,
                        (tenant_id, fl_client_ids),
                    )
                    rows = cur.fetchall()
            else:
                cur.execute("SELECT * FROM rca_reports WHERE tenant_id = %s ORDER BY created_at DESC", (tenant_id,))
                rows = cur.fetchall()
        items = [self._rca_from_row(row) for row in rows]
        return items, len(items)

    def get_rca(self, tenant_id: str, rca_id: str, *, fl_client_ids: list[str] | None = None) -> RCAReport | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM rca_reports WHERE tenant_id = %s AND id = %s", (tenant_id, rca_id))
            row = cur.fetchone()
        if not row:
            return None
        rpt = self._rca_from_row(row)
        if fl_client_ids is not None:
            if not fl_client_ids or self.get_incident(tenant_id, rpt.incident_id, fl_client_ids=fl_client_ids) is None:
                return None
        return rpt

    def generate_rca_report(self, tenant_id: str, incident_id: str, *, fl_client_ids: list[str] | None = None) -> RCAReport | None:
        incident = self.get_incident(tenant_id, incident_id, fl_client_ids=fl_client_ids)
        if not incident:
            return None
        now = _now_iso()
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT id FROM rca_reports WHERE tenant_id = %s ORDER BY id DESC LIMIT 1", (tenant_id,))
            row = cur.fetchone()
            next_num = int(str(row["id"]).split("-")[-1]) + 1 if row else 1
            rca_id = f"RCA-{next_num:03d}"
            report = RCAReport(
                id=rca_id,
                incident_id=incident.id,
                title=f"Auto RCA — {incident.title}",
                executive_summary=f"Generated RCA for incident {incident.id}.",
                timeline_nodes=[TimelineNode(label=event.type, timestamp=event.timestamp) for event in incident.timeline],
                affected_nodes=[AffectedNode(device_name=device.name, ip=device.ip, impact=str(device.status)) for device in incident.affected_devices],
                mitre_chain=["Initial Access", "Execution", "Impact"],
                response_actions=["Automated analysis run", "Report assembled from incident timeline"],
                recommendations=["Review affected devices", "Update detection rules and runbook"],
            )
            cur.execute(
                """
                INSERT INTO rca_reports
                    (id, tenant_id, incident_id, title, executive_summary, timeline_nodes_json, affected_nodes_json, mitre_chain_json, response_actions_json, recommendations_json, created_by, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s, %s, %s)
                """,
                (report.id, tenant_id, report.incident_id, report.title, report.executive_summary, Json([node.model_dump(mode="json") for node in report.timeline_nodes]), Json([node.model_dump(mode="json") for node in report.affected_nodes]), Json(report.mitre_chain), Json(report.response_actions), Json(report.recommendations), "system", now, now),
            )
            self._append_audit(cur, tenant_id=tenant_id, actor_firebase_uid="system", actor_label="BastionFed System", action=AuditAction.REPORT_GENERATED.value, target_type="incident", target_id=incident_id, result=f"Generated {report.id} at {now}", metadata={})
            conn.commit()
        return report

    def block_ip(self, tenant_id: str, *, ip: str, reason: str, alert_id: str | None) -> dict[str, Any] | None:
        now = _now_iso()
        rule_id = f"FW-RULE-{random.randint(1000, 9999)}"
        with self._connect() as conn, conn.cursor() as cur:
            self._append_audit(cur, tenant_id=tenant_id, actor_firebase_uid="system", actor_label="BastionFed System", action=AuditAction.RESPONSE_TRIGGERED.value, target_type="alert" if alert_id else "network", target_id=alert_id or ip, result=f"Blocked IP {ip}: {reason}", metadata={"ip": ip})
            conn.commit()
        return {"ip": ip, "ruleId": rule_id, "appliedAt": now}

    def list_audit_logs(
        self,
        tenant_id: str,
        *,
        limit: int = 50,
        cursor: str | None = None,
        action: str | None = None,
        actor: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        fl_client_ids: list[str] | None = None,
        scope_firebase_uid: str | None = None,
    ) -> tuple[list[AuditLog], str | None, int]:
        clauses = ["al.tenant_id = %s"]
        params: list[Any] = [tenant_id]
        if action:
            clauses.append("al.action = %s")
            params.append(action)
        if actor:
            clauses.append("al.actor_label = %s")
            params.append(actor)
        if date_from:
            clauses.append("al.created_at >= %s")
            params.append(date_from)
        if date_to:
            clauses.append("al.created_at <= %s")
            params.append(date_to)
        if fl_client_ids is not None or scope_firebase_uid:
            sub: list[str] = []
            sub_params: list[Any] = []
            if fl_client_ids is not None and fl_client_ids:
                sub.append(
                    """(
                    (al.target_type = 'device' AND EXISTS (
                        SELECT 1 FROM devices d
                        WHERE d.tenant_id = al.tenant_id AND d.id = al.target_id AND d.fl_client_id = ANY(%s)
                    ))
                    OR (al.target_type = 'alert' AND EXISTS (
                        SELECT 1 FROM alerts a2 JOIN devices d ON a2.tenant_id = d.tenant_id AND a2.device_id = d.id
                        WHERE a2.tenant_id = al.tenant_id AND a2.id = al.target_id AND d.fl_client_id = ANY(%s)
                    ))
                    OR (al.target_type = 'incident' AND EXISTS (
                        SELECT 1 FROM incidents inc
                        CROSS JOIN LATERAL jsonb_array_elements_text(inc.affected_device_ids_json) AS aid(dev_id)
                        JOIN devices d ON d.tenant_id = inc.tenant_id AND d.id = aid.dev_id
                        WHERE inc.tenant_id = al.tenant_id AND inc.id = al.target_id AND d.fl_client_id = ANY(%s)
                    ))
                    OR (al.target_type = 'sample' AND EXISTS (
                        SELECT 1 FROM malware_samples m JOIN devices d ON m.tenant_id = d.tenant_id AND m.device_id = d.id
                        WHERE m.tenant_id = al.tenant_id AND m.id = al.target_id AND d.fl_client_id = ANY(%s)
                    ))
                )"""
                )
                sub_params.extend([fl_client_ids, fl_client_ids, fl_client_ids, fl_client_ids])
            if scope_firebase_uid:
                sub.append("al.actor_firebase_uid = %s")
                sub_params.append(scope_firebase_uid)
            if sub:
                joiner = " OR ".join(sub)
                clauses.append(f"AND ({joiner})")
                params.extend(sub_params)
            elif fl_client_ids is not None and not fl_client_ids:
                clauses.append("AND FALSE")
        where_sql = " AND ".join(clauses)
        start = _decode_cursor(cursor)
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) AS total FROM audit_log al WHERE {where_sql}", params)
            total = int(cur.fetchone()["total"])
            cur.execute(
                f"SELECT al.* FROM audit_log al WHERE {where_sql} ORDER BY al.sequence DESC OFFSET %s LIMIT %s",
                [*params, start, limit],
            )
            rows = cur.fetchall()
        items = [AuditLog(id=f"AUD-{row['sequence']}", timestamp=str(row["created_at"]), actor=str(row["actor_label"]), action=str(row["action"]), target=str(row["target_id"]), result=str(row["result"]), hash=str(row["hash"]), target_type=str(row["target_type"]), metadata=dict(row["metadata_json"] or {})) for row in rows]
        next_cursor = _encode_cursor(start + limit) if (start + limit) < total else None
        return items, next_cursor, total

    def verify_audit_chain(
        self, tenant_id: str, fl_client_ids: list[str] | None = None, scope_firebase_uid: str | None = None
    ) -> dict[str, Any]:
        checked_at = _now_iso()
        with self._connect() as conn, conn.cursor() as cur:
            if fl_client_ids is not None or scope_firebase_uid:
                clauses = ["al.tenant_id = %s"]
                params: list[Any] = [tenant_id]
                sub: list[str] = []
                sub_params: list[Any] = []
                if fl_client_ids is not None and fl_client_ids:
                    sub.append(
                        """(
                    (al.target_type = 'device' AND EXISTS (
                        SELECT 1 FROM devices d
                        WHERE d.tenant_id = al.tenant_id AND d.id = al.target_id AND d.fl_client_id = ANY(%s)
                    ))
                    OR (al.target_type = 'alert' AND EXISTS (
                        SELECT 1 FROM alerts a2 JOIN devices d ON a2.tenant_id = d.tenant_id AND a2.device_id = d.id
                        WHERE a2.tenant_id = al.tenant_id AND a2.id = al.target_id AND d.fl_client_id = ANY(%s)
                    ))
                    OR (al.target_type = 'incident' AND EXISTS (
                        SELECT 1 FROM incidents inc
                        CROSS JOIN LATERAL jsonb_array_elements_text(inc.affected_device_ids_json) AS aid(dev_id)
                        JOIN devices d ON d.tenant_id = inc.tenant_id AND d.id = aid.dev_id
                        WHERE inc.tenant_id = al.tenant_id AND inc.id = al.target_id AND d.fl_client_id = ANY(%s)
                    ))
                    OR (al.target_type = 'sample' AND EXISTS (
                        SELECT 1 FROM malware_samples m JOIN devices d ON m.tenant_id = d.tenant_id AND m.device_id = d.id
                        WHERE m.tenant_id = al.tenant_id AND m.id = al.target_id AND d.fl_client_id = ANY(%s)
                    ))
                )"""
                    )
                    sub_params.extend([fl_client_ids, fl_client_ids, fl_client_ids, fl_client_ids])
                if scope_firebase_uid:
                    sub.append("al.actor_firebase_uid = %s")
                    sub_params.append(scope_firebase_uid)
                if sub:
                    clauses.append(f"AND ({' OR '.join(sub)})")
                    params.extend(sub_params)
                elif fl_client_ids is not None and not fl_client_ids:
                    clauses.append("AND FALSE")
                where_sql = " AND ".join(clauses)
                cur.execute(
                    f"""
                    SELECT al.sequence, al.prev_hash, al.hash, al.actor_label, al.action, al.target_id, al.result, al.created_at
                    FROM audit_log al
                    WHERE {where_sql}
                    ORDER BY al.sequence ASC
                    """,
                    params,
                )
                rows = cur.fetchall()
                for row in rows:
                    expected = _audit_hash(
                        str(row["prev_hash"] or ""),
                        str(row["created_at"]),
                        str(row["actor_label"]),
                        str(row["action"]),
                        str(row["target_id"]),
                        str(row["result"]),
                    )
                    if expected != str(row["hash"]):
                        return {
                            "valid": False,
                            "firstBreakAt": f"AUD-{row['sequence']}",
                            "totalLogs": len(rows),
                            "checkedAt": checked_at,
                            "clientScopedVerify": True,
                        }
                return {"valid": True, "totalLogs": len(rows), "checkedAt": checked_at, "clientScopedVerify": True}
            cur.execute(
                "SELECT sequence, prev_hash, hash, actor_label, action, target_id, result, created_at FROM audit_log WHERE tenant_id = %s ORDER BY sequence ASC",
                (tenant_id,),
            )
            rows = cur.fetchall()
            prev = ""
            for row in rows:
                expected = _audit_hash(
                    prev,
                    str(row["created_at"]),
                    str(row["actor_label"]),
                    str(row["action"]),
                    str(row["target_id"]),
                    str(row["result"]),
                )
                if expected != str(row["hash"]) or str(row["prev_hash"] or "") != prev:
                    return {"valid": False, "firstBreakAt": f"AUD-{row['sequence']}", "totalLogs": len(rows), "checkedAt": checked_at}
                prev = str(row["hash"])
            return {"valid": True, "totalLogs": len(rows), "checkedAt": checked_at}

    def dashboard_kpis(self, tenant_id: str, fl_client_ids: list[str] | None = None) -> dict[str, Any]:
        a_scope = ""
        d_scope = ""
        i_scope = ""
        params_a: list[Any] = [tenant_id]
        params_d: list[Any] = [tenant_id]
        params_i: list[Any] = [tenant_id]
        if fl_client_ids is not None:
            if not fl_client_ids:
                a_scope = " AND FALSE"
                d_scope = " AND FALSE"
                i_scope = " AND FALSE"
            else:
                a_scope = """ AND EXISTS (
                SELECT 1 FROM devices d
                WHERE d.tenant_id = alerts.tenant_id AND d.id = alerts.device_id AND d.fl_client_id = ANY(%s)
            )"""
                params_a.append(fl_client_ids)
                d_scope = " AND fl_client_id = ANY(%s)"
                params_d.append(fl_client_ids)
                i_scope = """ AND EXISTS (
                SELECT 1
                FROM jsonb_array_elements_text(incidents.affected_device_ids_json) AS aid(dev_id)
                JOIN devices d ON d.tenant_id = incidents.tenant_id AND d.id = aid.dev_id
                WHERE d.fl_client_id = ANY(%s)
            )"""
                params_i.append(fl_client_ids)
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT COUNT(*) AS c FROM alerts WHERE tenant_id = %s AND status = 'OPEN'{a_scope}",
                params_a,
            )
            active_threats = int(cur.fetchone()["c"])
            cur.execute(f"SELECT AVG(confidence) AS avg_c FROM alerts WHERE tenant_id = %s{a_scope}", params_a)
            avg_conf = float(cur.fetchone()["avg_c"] or 0.0)
            cur.execute(
                f"SELECT COUNT(*) AS c FROM devices WHERE tenant_id = %s AND status IN ('SUSPICIOUS', 'COMPROMISED', 'ISOLATED'){d_scope}",
                params_d,
            )
            devices_under_watch = int(cur.fetchone()["c"])
            cur.execute("SELECT round FROM fl_rounds WHERE tenant_id = %s ORDER BY round DESC LIMIT 1", (tenant_id,))
            row = cur.fetchone()
            fl_round = int(row["round"]) if row else 0
            cur.execute(
                f"SELECT COUNT(*) AS c FROM incidents WHERE tenant_id = %s AND status NOT IN ('RESOLVED', 'POST_MORTEM'){i_scope}",
                params_i,
            )
            open_incidents = int(cur.fetchone()["c"])
            cur.execute(
                f"SELECT COUNT(*) AS c FROM alerts WHERE tenant_id = %s AND status = 'OPEN' AND severity = 'CRITICAL'{a_scope}",
                params_a,
            )
            critical_alerts = int(cur.fetchone()["c"])
            cur.execute(f"SELECT COUNT(*) AS c FROM alerts WHERE tenant_id = %s AND status = 'FALSE_POSITIVE'{a_scope}", params_a)
            fp_count = int(cur.fetchone()["c"])
            cur.execute(f"SELECT COUNT(*) AS c FROM alerts WHERE tenant_id = %s{a_scope}", params_a)
            total_alerts = int(cur.fetchone()["c"])
            cur.execute(
                f"SELECT COUNT(*) AS c FROM alerts WHERE tenant_id = %s AND status = 'RESOLVED' AND DATE(timestamp) = CURRENT_DATE{a_scope}",
                params_a,
            )
            resolved_today = int(cur.fetchone()["c"])
            cur.execute("SELECT COUNT(*) AS c FROM ingest_sources WHERE tenant_id = %s", (tenant_id,))
            ingest_sources = int(cur.fetchone()["c"])
            cur.execute("SELECT COUNT(*) AS c FROM ingest_events WHERE tenant_id = %s", (tenant_id,))
            ingest_events = int(cur.fetchone()["c"])
            cur.execute("SELECT is_demo FROM tenants WHERE id = %s", (tenant_id,))
            tenant_row = cur.fetchone()
        return {"activeThreats": active_threats, "avgConfidence": round(avg_conf, 1), "devicesUnderWatch": devices_under_watch, "flRound": fl_round, "openIncidents": open_incidents, "criticalAlerts": critical_alerts, "resolvedToday": resolved_today, "falsePositiveRate": round((fp_count / total_alerts * 100) if total_alerts else 0.0, 1), "liveDataConnected": ingest_events > 0, "ingestSourcesConfigured": ingest_sources, "ingestEventsReceived": ingest_events, "demoMode": bool(tenant_row["is_demo"]) if tenant_row else False}

    def list_ingest_sources(self, tenant_id: str) -> list[IngestSource]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT id, tenant_id, name, source_type, connector_kind, secret_last_rotated_at, created_at, updated_at FROM ingest_sources WHERE tenant_id = %s ORDER BY created_at DESC", (tenant_id,))
            rows = cur.fetchall()
        return [IngestSource.model_validate(row) for row in rows]

    def create_ingest_source(self, tenant_id: str, *, name: str, source_type: str, connector_kind: str, actor_uid: str) -> tuple[IngestSource, str]:
        now = _now_iso()
        source_id = f"src-{int(time.time() * 1000)}"
        secret = secrets.token_urlsafe(24)
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ingest_sources
                    (id, tenant_id, name, source_type, connector_kind, secret_hash, secret_last_rotated_at, created_by, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (source_id, tenant_id, name, source_type.upper(), connector_kind.upper(), _secret_hash(secret), now, actor_uid, now, now),
            )
            self._append_audit(cur, tenant_id=tenant_id, actor_firebase_uid=actor_uid, actor_label=actor_uid, action=AuditAction.CONFIG_CHANGED.value, target_type="ingest_source", target_id=source_id, result=f"Created ingest source {name}", metadata={"sourceType": source_type, "connectorKind": connector_kind})
            conn.commit()
        return IngestSource(id=source_id, tenant_id=tenant_id, name=name, source_type=source_type.upper(), connector_kind=connector_kind.upper(), secret_last_rotated_at=now, created_at=now, updated_at=now), secret

    def rotate_ingest_source_secret(self, tenant_id: str, *, source_id: str, actor_uid: str) -> tuple[IngestSource | None, str | None]:
        now = _now_iso()
        secret = secrets.token_urlsafe(24)
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE ingest_sources
                SET secret_hash = %s, secret_last_rotated_at = %s, updated_at = %s
                WHERE tenant_id = %s AND id = %s
                RETURNING id, tenant_id, name, source_type, connector_kind, secret_last_rotated_at, created_at, updated_at
                """,
                (_secret_hash(secret), now, now, tenant_id, source_id),
            )
            row = cur.fetchone()
            if not row:
                return None, None
            self._append_audit(cur, tenant_id=tenant_id, actor_firebase_uid=actor_uid, actor_label=actor_uid, action=AuditAction.CONFIG_CHANGED.value, target_type="ingest_source", target_id=source_id, result="Rotated ingest source secret", metadata={})
            conn.commit()
        return IngestSource.model_validate(row), secret

    def ingest_event(self, *, source_id: str, source_secret: str, external_id: str, event_type: str, payload: dict[str, Any], occurred_at: str | None = None) -> IngestEventResult | None:
        received_at = _now_iso()
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM ingest_sources WHERE id = %s", (source_id,))
            source = cur.fetchone()
            if not source or str(source["secret_hash"]) != _secret_hash(source_secret):
                return None
            tenant_id = str(source["tenant_id"])
            cur.execute("SELECT * FROM ingest_events WHERE tenant_id = %s AND source_id = %s AND external_id = %s", (tenant_id, source_id, external_id))
            existing = cur.fetchone()
            if existing:
                return IngestEventResult(event_id=str(existing["id"]), tenant_id=tenant_id, source_id=source_id, external_id=external_id, parse_status="DUPLICATE", normalized_targets=list(existing["normalized_targets_json"] or []), received_at=str(existing["received_at"]))
            result = self._normalize_ingest_event(cur, source=source, external_id=external_id, event_type=event_type, payload=payload, occurred_at=occurred_at, received_at=received_at)
            cur.execute(
                """
                INSERT INTO ingest_events
                    (id, tenant_id, source_id, external_id, event_type, payload_json, parse_status, normalized_targets_json, received_at, occurred_at, created_at)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s::jsonb, %s, %s, %s)
                """,
                (result.event_id, tenant_id, source_id, external_id, event_type, Json(payload), result.parse_status, Json(result.normalized_targets), result.received_at, occurred_at, result.received_at),
            )
            self._append_audit(cur, tenant_id=tenant_id, actor_firebase_uid="connector", actor_label=f"{source['name']} connector", action=AuditAction.DETECTION_MADE.value, target_type=event_type.lower(), target_id=external_id, result=f"Ingested {event_type.lower()} event", metadata={"sourceId": source_id, "eventId": result.event_id})
            conn.commit()
            return result

    def export_audit_logs(
        self,
        tenant_id: str,
        *,
        format: str = "jsonl",
        date_from: str | None = None,
        date_to: str | None = None,
        fl_client_ids: list[str] | None = None,
        scope_firebase_uid: str | None = None,
    ) -> str:
        items, _, _ = self.list_audit_logs(
            tenant_id,
            limit=1000,
            date_from=date_from,
            date_to=date_to,
            fl_client_ids=fl_client_ids,
            scope_firebase_uid=scope_firebase_uid,
        )
        if format == "csv":
            lines = ["id,timestamp,actor,action,targetType,target,result,hash"]
            for item in items:
                lines.append(f'{item.id},{item.timestamp},{item.actor},{item.action},{item.target_type or ""},{item.target},{item.result},{item.hash}')
            return "\n".join(lines)
        return "\n".join(json.dumps(item.model_dump(by_alias=True, mode="json")) for item in items)

    def append_audit(self, tenant_id: str, *, actor_uid: str, actor_label: str, action: AuditAction, target_type: str, target_id: str, result: str, metadata: dict[str, Any] | None = None) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            self._append_audit(
                cur,
                tenant_id=tenant_id,
                actor_firebase_uid=actor_uid,
                actor_label=actor_label,
                action=action.value,
                target_type=target_type,
                target_id=target_id,
                result=result,
                metadata=metadata or {},
            )
            conn.commit()

    def _append_audit(self, cur: Any, *, tenant_id: str, actor_firebase_uid: str, actor_label: str, action: str, target_type: str, target_id: str, result: str, metadata: dict[str, Any]) -> None:
        cur.execute("SELECT sequence, hash FROM audit_log WHERE tenant_id = %s ORDER BY sequence DESC LIMIT 1", (tenant_id,))
        last = cur.fetchone()
        sequence = int(last["sequence"]) + 1 if last else 1
        prev_hash = str(last["hash"]) if last else ""
        now = _now_iso()
        row_hash = _audit_hash(prev_hash, now, actor_label, action, target_id, result)
        cur.execute(
            """
            INSERT INTO audit_log
                (tenant_id, sequence, prev_hash, hash, actor_firebase_uid, actor_label, action, target_type, target_id, result, metadata_json, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
            """,
            (tenant_id, sequence, prev_hash, row_hash, actor_firebase_uid, actor_label, action, target_type, target_id, result, Json(metadata), now),
        )

    def _insert_incident_event(self, cur: Any, *, tenant_id: str, incident_id: str, event: IncidentEvent) -> None:
        cur.execute(
            """
            INSERT INTO incident_events (id, tenant_id, incident_id, timestamp, type, description, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
            """,
            (event.id, tenant_id, incident_id, event.timestamp, event.type, event.description, event.timestamp),
        )

    def _device_from_row(self, row: dict[str, Any]) -> Device:
        return Device(id=str(row["id"]), name=str(row["name"]), ip=str(row["ip"]), type=str(row["type"]), wing=str(row["wing"]), criticality=int(row["criticality"]), fl_client_id=str(row["fl_client_id"]), status=DeviceStatus(str(row["status"])), source_type=row.get("source_type"), source_ref=row.get("source_ref"), ingested_at=row.get("ingested_at"), is_demo=bool(row.get("is_demo", False)))

    def _get_device(self, cur: Any, tenant_id: str, device_id: str) -> Device | None:
        cur.execute("SELECT * FROM devices WHERE tenant_id = %s AND id = %s", (tenant_id, device_id))
        row = cur.fetchone()
        return self._device_from_row(row) if row else None

    def _devices_map(self, cur: Any, tenant_id: str, device_ids: list[str] | None = None) -> dict[str, Device]:
        if device_ids:
            cur.execute("SELECT * FROM devices WHERE tenant_id = %s AND id = ANY(%s)", (tenant_id, device_ids))
        else:
            cur.execute("SELECT * FROM devices WHERE tenant_id = %s", (tenant_id,))
        return {str(row["id"]): self._device_from_row(row) for row in cur.fetchall()}

    def _alert_from_row(self, row: dict[str, Any], device: Device | None) -> Alert:
        if device is None:
            raise ValueError(f"Missing device for alert {row['id']}")
        return Alert(id=str(row["id"]), timestamp=str(row["timestamp"]), device_id=str(row["device_id"]), device=device, type=str(row["type"]), tactic=str(row["tactic"]), technique=row["technique_json"], severity=Severity(str(row["severity"])), confidence=float(row["confidence"]), status=AlertStatus(str(row["status"])), model_version=str(row["model_version"]), threat_intel=row["threat_intel_json"], cve_reference=row["cve_reference"], feature_summary=str(row["feature_summary"]), source_type=row.get("source_type"), source_ref=row.get("source_ref"), ingested_at=row.get("ingested_at"), is_demo=bool(row.get("is_demo", False)))

    def _incident_events_by_incident(self, cur: Any, tenant_id: str, incident_ids: list[str]) -> dict[str, list[IncidentEvent]]:
        if not incident_ids:
            return {}
        cur.execute("SELECT * FROM incident_events WHERE tenant_id = %s AND incident_id = ANY(%s) ORDER BY timestamp ASC, id ASC", (tenant_id, incident_ids))
        grouped: dict[str, list[IncidentEvent]] = {}
        for row in cur.fetchall():
            grouped.setdefault(str(row["incident_id"]), []).append(IncidentEvent(id=str(row["id"]), timestamp=str(row["timestamp"]), type=str(row["type"]), description=str(row["description"])))
        return grouped

    def _incident_from_row(self, row: dict[str, Any], devices: dict[str, Device], timeline: list[IncidentEvent]) -> Incident:
        device_ids = list(row["affected_device_ids_json"] or [])
        playbook = Playbook.model_validate(row["playbook_json"])
        return Incident(
            id=str(row["id"]),
            title=str(row["title"]),
            severity=Severity(str(row["severity"])),
            status=IncidentStatus(str(row["status"])),
            affected_devices=[devices[device_id] for device_id in device_ids if device_id in devices],
            time_open=str(row["time_open"]),
            analyst_initials=str(row["analyst_initials"]),
            timeline=timeline,
            playbook=playbook,
            ticket_id=str(row["ticket_id"]),
            reporter=str(row["reporter"]),
            assignee=str(row["assignee"]),
            priority=str(row["priority"]),
            created=str(row["created"]),
            labels=list(row["labels_json"] or []),
            source_type=row.get("source_type"),
            source_ref=row.get("source_ref"),
            ingested_at=row.get("ingested_at"),
            is_demo=bool(row.get("is_demo", False)),
        )

    def _sample_from_row(self, row: dict[str, Any]) -> MalwareSample:
        storage_path = None
        if row["storage_bucket"] and row["storage_object_key"]:
            storage_path = f"{row['storage_bucket']}/{row['storage_object_key']}"
        return MalwareSample(id=str(row["id"]), sha256=str(row["sha256"]), md5=str(row["md5"]), filename=str(row["filename"]), size=str(row["size"]), type=str(row["type"]), device_id=str(row["device_id"]), timestamp=str(row["timestamp"]), upload_time=str(row["upload_time"]), family=str(row["family"]), threat_score=int(row["threat_score"]), status=str(row["status"]), analysis=SampleAnalysis.model_validate(row["analysis_json"]), storage_path=storage_path, scan_status=str(row.get("scan_status") or "NOT_SCANNED"), quarantine_status=str(row.get("quarantine_status") or "NONE"), retention_status=str(row.get("retention_status") or "ACTIVE"), chain_of_custody=list(row.get("chain_of_custody_json") or []), scanner_verdict=row.get("scanner_verdict_json"), is_demo=bool(row.get("is_demo", False)))

    def _rca_from_row(self, row: dict[str, Any]) -> RCAReport:
        return RCAReport(id=str(row["id"]), incident_id=str(row["incident_id"]), title=str(row["title"]), executive_summary=str(row["executive_summary"]), timeline_nodes=[TimelineNode.model_validate(item) for item in row["timeline_nodes_json"]], affected_nodes=[AffectedNode.model_validate(item) for item in row["affected_nodes_json"]], mitre_chain=list(row["mitre_chain_json"] or []), response_actions=list(row["response_actions_json"] or []), recommendations=list(row["recommendations_json"] or []))

    def _model_registry_payload(self, row: dict[str, Any]) -> dict[str, Any]:
        fid = row.get("fl_client_id")
        return {
            "name": row["name"],
            "type": row["model_type"],
            "accuracy": float(row["accuracy"]),
            "fpRate": float(row["fp_rate"]),
            "size": row["size"],
            "trainedOn": row["trained_on"],
            "description": row["description"],
            "active": bool(row["is_active"]),
            "flClientId": str(fid) if fid else None,
            "modelScope": str(row.get("model_scope") or "tenant"),
            "storagePath": row.get("storage_path"),
        }

    def _normalize_ingest_event(self, cur: Any, *, source: dict[str, Any], external_id: str, event_type: str, payload: dict[str, Any], occurred_at: str | None, received_at: str) -> IngestEventResult:
        tenant_id = str(source["tenant_id"])
        source_type = str(source["source_type"])
        device_id = str(payload.get("deviceId") or payload.get("device_id") or f"dev-ingest-{int(time.time() * 1000)}")
        cur.execute("SELECT * FROM devices WHERE tenant_id = %s AND id = %s", (tenant_id, device_id))
        device_row = cur.fetchone()
        normalized_targets: list[dict[str, str]] = []
        if not device_row:
            cur.execute(
                """
                INSERT INTO devices
                    (tenant_id, id, name, ip, type, wing, criticality, fl_client_id, status, source_type, source_ref, ingested_at, is_demo, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, FALSE, %s, %s)
                """,
                (tenant_id, device_id, str(payload.get("deviceName") or payload.get("device_name") or device_id), str(payload.get("ip") or "0.0.0.0"), str(payload.get("deviceType") or payload.get("type") or "UNKNOWN"), str(payload.get("wing") or "INGEST"), int(payload.get("criticality") or 3), str(payload.get("flClientId") or "client-ingest"), str(payload.get("deviceStatus") or payload.get("status") or DeviceStatus.SUSPICIOUS.value), source_type, external_id, received_at, received_at, received_at),
            )
            normalized_targets.append({"type": "device", "id": device_id})
        event_type_norm = event_type.lower()
        if event_type_norm == "alert":
            alert_id = str(payload.get("alertId") or payload.get("id") or f"ALT-{int(time.time() * 1000)}")
            cur.execute(
                """
                INSERT INTO alerts
                    (tenant_id, id, timestamp, device_id, type, tactic, technique_json, severity, confidence, status, model_version, threat_intel_json, cve_reference, feature_summary, source_type, source_ref, ingested_at, is_demo, created_by, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, FALSE, %s, %s, %s)
                ON CONFLICT (tenant_id, id) DO UPDATE SET updated_at = EXCLUDED.updated_at, source_type = EXCLUDED.source_type, source_ref = EXCLUDED.source_ref, ingested_at = EXCLUDED.ingested_at
                """,
                (tenant_id, alert_id, occurred_at or received_at, device_id, str(payload.get("alertType") or payload.get("type") or "External Alert"), str(payload.get("tactic") or "Execution"), Json({"id": str(payload.get("techniqueId") or "T1204"), "tactic": str(payload.get("tactic") or "Execution"), "name": str(payload.get("techniqueName") or "User Execution")}), str(payload.get("severity") or Severity.HIGH.value), float(payload.get("confidence") or 0.8), AlertStatus.OPEN.value, str(payload.get("modelVersion") or source["connector_kind"]), Json(payload.get("threatIntel") or []), payload.get("cveReference"), str(payload.get("summary") or "Ingested from external source"), source_type, external_id, received_at, source["name"], received_at, received_at),
            )
            normalized_targets.append({"type": "alert", "id": alert_id})
        elif event_type_norm == "ticket":
            incident_id = str(payload.get("incidentId") or payload.get("ticketId") or f"INC-{int(time.time() * 1000)}")
            incident = Incident(
                id=incident_id,
                title=str(payload.get("title") or "External Incident"),
                severity=Severity(str(payload.get("severity") or Severity.MEDIUM.value)),
                status=IncidentStatus(str(payload.get("incidentStatus") or IncidentStatus.NEW.value)),
                affected_devices=[],
                time_open="0m",
                analyst_initials=str(payload.get("analystInitials") or "EX"),
                timeline=[IncidentEvent(id=f"evt-{int(time.time() * 1000)}", timestamp=str(occurred_at or received_at), type="ALERT", description=str(payload.get("summary") or "Ingested ticket event"))],
                playbook=Playbook(id=f"pb-{incident_id}", name="External Ticket", trigger_condition=source_type, last_run=received_at, executions=0, status="DRAFT", steps=[]),
                ticket_id=str(payload.get("ticketId") or incident_id),
                reporter=str(payload.get("reporter") or source["name"]),
                assignee=str(payload.get("assignee") or "Unassigned"),
                priority=str(payload.get("priority") or "P3"),
                created=str(occurred_at or received_at),
                labels=list(payload.get("labels") or [source_type]),
                source_type=source_type,
                source_ref=external_id,
                ingested_at=received_at,
                is_demo=False,
            )
            cur.execute(
                """
                INSERT INTO incidents
                    (tenant_id, id, title, severity, status, affected_device_ids_json, time_open, analyst_initials, playbook_json, ticket_id, reporter, assignee, priority, created, labels_json, source_type, source_ref, ingested_at, is_demo, created_by, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, FALSE, %s, %s, %s)
                """,
                (tenant_id, incident.id, incident.title, _camel_enum_str(incident.severity), _camel_enum_str(incident.status), Json([device_id]), incident.time_open, incident.analyst_initials, Json(incident.playbook.model_dump(mode="json")), incident.ticket_id, incident.reporter, incident.assignee, incident.priority, incident.created, Json(incident.labels), source_type, external_id, received_at, source["name"], received_at, received_at),
            )
            for event in incident.timeline:
                self._insert_incident_event(cur, tenant_id=tenant_id, incident_id=incident.id, event=event)
            normalized_targets.append({"type": "incident", "id": incident.id})
        return IngestEventResult(event_id=f"ing-{int(time.time() * 1000)}", tenant_id=tenant_id, source_id=str(source["id"]), external_id=external_id, parse_status="ACCEPTED", normalized_targets=normalized_targets, received_at=received_at)

    def _active_model_name(self, tenant_id: str) -> str:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT name FROM model_registry WHERE tenant_id = %s AND is_active = TRUE LIMIT 1", (tenant_id,))
            row = cur.fetchone()
        return str(row["name"]) if row else "v4.2.1-DNN"

    def _active_model_for_scope(self, tenant_id: str, fl_client_ids: list[str] | None) -> str:
        if fl_client_ids is not None and len(fl_client_ids) == 1:
            cid = fl_client_ids[0]
            with self._connect() as conn, conn.cursor() as cur:
                cur.execute(
                    "SELECT model_name FROM fl_client_active_models WHERE tenant_id = %s AND fl_client_id = %s",
                    (tenant_id, cid),
                )
                row = cur.fetchone()
            if row:
                return str(row["model_name"])
        return self._active_model_name(tenant_id)

    def _seed_demo_tenant(self, cur: Any, tenant_id: str) -> None:
        now = datetime.now(timezone.utc)
        devices = seed_data.build_devices(now)
        alerts = seed_data.build_alerts(devices, now)
        incidents = seed_data.build_incidents(devices, now)
        fl_rounds = seed_data.build_fl_rounds()
        fl_clients = seed_data.build_fl_clients()
        samples = seed_data.build_malware_samples(now)
        rca_reports = seed_data.build_rca_reports()
        audit_rows = seed_data.build_audit_log_payloads(now)
        for device in devices:
            cur.execute("INSERT INTO devices (tenant_id, id, name, ip, type, wing, criticality, fl_client_id, status, source_type, source_ref, ingested_at, is_demo, created_at, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE, %s, %s) ON CONFLICT (tenant_id, id) DO NOTHING", (tenant_id, device.id, device.name, device.ip, device.type, device.wing, device.criticality, device.fl_client_id, _camel_enum_str(device.status), "DEMO", f"seed:{device.id}", _now_iso(), _now_iso(), _now_iso()))
        for alert in alerts:
            cur.execute("INSERT INTO alerts (tenant_id, id, timestamp, device_id, type, tactic, technique_json, severity, confidence, status, model_version, threat_intel_json, cve_reference, feature_summary, source_type, source_ref, ingested_at, is_demo, created_by, created_at, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, TRUE, %s, %s, %s) ON CONFLICT (tenant_id, id) DO NOTHING", (tenant_id, alert.id, alert.timestamp, alert.device_id, alert.type, alert.tactic, Json(alert.technique.model_dump(mode="json")), _camel_enum_str(alert.severity), alert.confidence, _camel_enum_str(alert.status), alert.model_version, Json([item.model_dump(mode="json") for item in alert.threat_intel]), alert.cve_reference, alert.feature_summary, "DEMO", f"seed:{alert.id}", _now_iso(), "demo", _now_iso(), _now_iso()))
        for incident in incidents:
            cur.execute("INSERT INTO incidents (tenant_id, id, title, severity, status, affected_device_ids_json, time_open, analyst_initials, playbook_json, ticket_id, reporter, assignee, priority, created, labels_json, source_type, source_ref, ingested_at, is_demo, created_by, created_at, updated_at) VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, TRUE, %s, %s, %s) ON CONFLICT (tenant_id, id) DO NOTHING", (tenant_id, incident.id, incident.title, _camel_enum_str(incident.severity), _camel_enum_str(incident.status), Json([device.id for device in incident.affected_devices]), incident.time_open, incident.analyst_initials, Json(incident.playbook.model_dump(mode="json")), incident.ticket_id, incident.reporter, incident.assignee, incident.priority, incident.created, Json(incident.labels), "DEMO", f"seed:{incident.id}", _now_iso(), "demo", _now_iso(), _now_iso()))
            for event in incident.timeline:
                self._insert_incident_event(cur, tenant_id=tenant_id, incident_id=incident.id, event=event)
        for row in fl_rounds:
            cur.execute("INSERT INTO fl_rounds (tenant_id, session_id, round, accuracy, fp_rate, train_loss, val_loss, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (tenant_id, round) DO NOTHING", (tenant_id, "sess_2025_06_01", row.round, row.accuracy, row.fp_rate, row.train_loss, row.val_loss, _now_iso()))
        for client in fl_clients:
            ct = client.client_type.value if hasattr(client.client_type, "value") else str(client.client_type)
            cur.execute(
                """
                INSERT INTO fl_clients
                    (tenant_id, id, department, participation_pct, last_round, dp_epsilon, model_version, status,
                     client_type, created_at, updated_at, created_by_firebase_uid)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (tenant_id, id) DO NOTHING
                """,
                (
                    tenant_id,
                    client.id,
                    client.department,
                    client.participation_pct,
                    client.last_round,
                    client.dp_epsilon,
                    client.model_version,
                    _camel_enum_str(client.status),
                    ct,
                    _now_iso(),
                    _now_iso(),
                    None,
                ),
            )
        for payload in [
            {"name": "v4.2.1-DNN", "model_type": "DNN", "accuracy": 94.2, "fp_rate": 0.9, "size": "48MB", "trained_on": "2025-05-28T00:00:00Z", "description": "Deep neural network, general-purpose IoMT threat detection.", "is_active": True},
            {"name": "v4.1.0-GNN", "model_type": "GNN", "accuracy": 91.8, "fp_rate": 1.1, "size": "36MB", "trained_on": "2025-05-20T00:00:00Z", "description": "Graph neural network for lateral movement and topology anomalies.", "is_active": False},
            {"name": "v4.0.5-HYB", "model_type": "HYB", "accuracy": 89.5, "fp_rate": 1.4, "size": "60MB", "trained_on": "2025-05-10T00:00:00Z", "description": "Legacy ensemble hybrid model. Kept for fallback and baseline comparison.", "is_active": False},
        ]:
            cur.execute("INSERT INTO model_registry (tenant_id, name, model_type, accuracy, fp_rate, size, trained_on, description, is_active, created_at, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (tenant_id, name) DO NOTHING", (tenant_id, payload["name"], payload["model_type"], payload["accuracy"], payload["fp_rate"], payload["size"], payload["trained_on"], payload["description"], payload["is_active"], _now_iso(), _now_iso()))
        for sample in samples:
            bucket = None
            object_key = None
            if sample.storage_path and "/" in sample.storage_path:
                bucket, object_key = sample.storage_path.split("/", 1)
            cur.execute("INSERT INTO malware_samples (tenant_id, id, sha256, md5, filename, size, type, device_id, timestamp, upload_time, family, threat_score, status, analysis_json, storage_bucket, storage_object_key, scan_status, quarantine_status, retention_status, chain_of_custody_json, scanner_verdict_json, is_demo, created_by, created_at, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, TRUE, %s, %s, %s) ON CONFLICT (tenant_id, id) DO NOTHING", (tenant_id, sample.id, sample.sha256, sample.md5, sample.filename, sample.size, sample.type, sample.device_id, sample.timestamp, sample.upload_time, sample.family, sample.threat_score, sample.status, Json(sample.analysis.model_dump(mode="json")), bucket, object_key, "SCANNED", "NONE", "ACTIVE", Json([{"timestamp": sample.upload_time, "actor": "demo", "action": "SEEDED", "detail": "Demo sample seeded"}]), Json({"engine": "demo-seed", "verdict": "MALICIOUS", "confidence": sample.threat_score, "summary": "Seeded demo verdict"}), "demo", _now_iso(), _now_iso()))
        for rca in rca_reports:
            cur.execute("INSERT INTO rca_reports (tenant_id, id, incident_id, title, executive_summary, timeline_nodes_json, affected_nodes_json, mitre_chain_json, response_actions_json, recommendations_json, created_by, created_at, updated_at) VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s, %s, %s) ON CONFLICT (tenant_id, id) DO NOTHING", (tenant_id, rca.id, rca.incident_id, rca.title, rca.executive_summary, Json([node.model_dump(mode="json") for node in rca.timeline_nodes]), Json([node.model_dump(mode="json") for node in rca.affected_nodes]), Json(rca.mitre_chain), Json(rca.response_actions), Json(rca.recommendations), "demo", _now_iso(), _now_iso()))
        prev = ""
        for row in audit_rows:
            row_hash = _audit_hash(prev, row["timestamp"], row["actor"], row["action"].value if hasattr(row["action"], "value") else str(row["action"]), row["target"], row["result"])
            cur.execute("INSERT INTO audit_log (tenant_id, sequence, prev_hash, hash, actor_firebase_uid, actor_label, action, target_type, target_id, result, metadata_json, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s) ON CONFLICT (tenant_id, sequence) DO NOTHING", (tenant_id, int(str(row["id"]).split("-")[-1]), prev, row_hash, "demo", row["actor"], row["action"].value if hasattr(row["action"], "value") else str(row["action"]), "seed", row["target"], row["result"], Json({}), row["timestamp"]))
            prev = row_hash


_impl: TenantStore = MemoryTenantStore()


class _TenantStoreProxy:
    def __getattr__(self, name: str):
        return getattr(_impl, name)


tenant_store = _TenantStoreProxy()


def set_tenant_store(store: TenantStore) -> None:
    global _impl
    _impl = store
