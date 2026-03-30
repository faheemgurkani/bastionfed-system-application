from __future__ import annotations

import base64
import hashlib
import json
import random
import time
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

from app.models.domain import (
    Alert,
    AlertStatus,
    BotMessage,
    ConversationSummary,
    AuditAction,
    AuditLog,
    Device,
    DeviceStatus,
    FLClient,
    FLClientStatus,
    FLRound,
    Incident,
    IncidentEvent,
    MalwareSample,
    RCAReport,
    UserRecord,
)
from app.store import seed_data

AUDIT_COUNTER = 2000


def _norm_iso(ts: str) -> datetime:
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return datetime.fromisoformat(ts)


def _enum_primitive(val: Any) -> str:
    """Pydantic may store enum fields as Enum or as plain str (use_enum_values)."""
    if isinstance(val, Enum):
        return val.value
    return str(val)


def _audit_hash(prev: str, entry: dict[str, Any]) -> str:
    act = entry["action"]
    act_s = act.value if isinstance(act, AuditAction) else str(act)
    raw = f"{prev}{entry['timestamp']}{entry['actor']}{act_s}{entry['target']}{entry['result']}"
    return hashlib.sha256(raw.encode()).hexdigest()


class AppState:
    def __init__(self) -> None:
        self.devices: list[Device] = []
        self.alerts: list[Alert] = []
        self.incidents: list[Incident] = []
        self.fl_rounds: list[FLRound] = []
        self.fl_clients: list[FLClient] = []
        self.malware_samples: list[MalwareSample] = []
        self.rca_reports: list[RCAReport] = []
        self.audit_logs: list[AuditLog] = []
        self.users: dict[str, UserRecord] = {}
        self.conversations: list[ConversationSummary] = []
        self.conversation_messages: dict[str, list[BotMessage]] = {}
        self.active_model_name: str = "fl-meta-v1"
        self.model_zoo_names: set[str] = {
            "fl-meta-v1", "fl-resnet-v1", "fl-dnn-v1",
            "client-1-meta", "client-1-resnet", "client-1-dnn",
            "client-2-meta", "client-2-resnet", "client-2-dnn",
            "client-3-meta", "client-3-resnet", "client-3-dnn",
            "client-4-meta", "client-4-resnet", "client-4-dnn",
        }
        self.fl_session_id: str = "sess_fl_nodp_r10"

    def reset(self) -> None:
        global AUDIT_COUNTER
        now = datetime.now(timezone.utc)
        self.devices = seed_data.build_devices(now)
        self.fl_rounds = seed_data.build_fl_rounds()
        self.fl_clients = seed_data.build_fl_clients()
        self.alerts = seed_data.build_alerts(self.devices, now)
        self.incidents = seed_data.build_incidents(self.devices, now)
        self.malware_samples = seed_data.build_malware_samples(now)
        self.rca_reports = seed_data.build_rca_reports()
        self.audit_logs = []
        self.users = {}
        self.active_model_name = "fl-meta-v1"
        self.conversations = [
            ConversationSummary(
                id="conv-1",
                title="Ransomware detection on Insulin Pump Hub",
                preview="Ransomware detection on Insulin Pump Hub",
                created_at=(now - timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
                updated_at=(now - timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
                message_count=0,
            ),
            ConversationSummary(
                id="conv-2",
                title="ATT&CK T0814 explanation",
                preview="ATT&CK T0814 explanation",
                created_at=(now - timedelta(days=1)).isoformat().replace("+00:00", "Z"),
                updated_at=(now - timedelta(days=1)).isoformat().replace("+00:00", "Z"),
                message_count=0,
            ),
            ConversationSummary(
                id="conv-3",
                title="FL model accuracy trend",
                preview="FL model accuracy trend",
                created_at=(now - timedelta(days=2)).isoformat().replace("+00:00", "Z"),
                updated_at=(now - timedelta(days=2)).isoformat().replace("+00:00", "Z"),
                message_count=0,
            ),
            ConversationSummary(
                id="conv-4",
                title="Summarize today's incidents",
                preview="Summarize today's incidents",
                created_at=(now - timedelta(days=3)).isoformat().replace("+00:00", "Z"),
                updated_at=(now - timedelta(days=3)).isoformat().replace("+00:00", "Z"),
                message_count=0,
            ),
            ConversationSummary(
                id="conv-5",
                title="Remediation for MRI Unit",
                preview="Remediation for MRI Unit",
                created_at=(now - timedelta(days=4)).isoformat().replace("+00:00", "Z"),
                updated_at=(now - timedelta(days=4)).isoformat().replace("+00:00", "Z"),
                message_count=0,
            ),
        ]
        self.conversation_messages = {c.id: [] for c in self.conversations}
        self.model_zoo_names = {
            "fl-meta-v1", "fl-resnet-v1", "fl-dnn-v1",
            "client-1-meta", "client-1-resnet", "client-1-dnn",
            "client-2-meta", "client-2-resnet", "client-2-dnn",
            "client-3-meta", "client-3-resnet", "client-3-dnn",
            "client-4-meta", "client-4-resnet", "client-4-dnn",
        }
        prev = ""
        for row in seed_data.build_audit_log_payloads(now):
            h = _audit_hash(prev, row)
            prev = h
            self.audit_logs.append(
                AuditLog(
                    id=row["id"],
                    timestamp=row["timestamp"],
                    actor=row["actor"],
                    action=row["action"],
                    target=row["target"],
                    result=row["result"],
                    hash=h,
                )
            )

    # --- Alerts ---

    def list_alerts(
        self,
        *,
        limit: int = 50,
        cursor: str | None = None,
        severity: str | None = None,
        tactic: str | None = None,
        status: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        sort: str = "timestamp_desc",
    ) -> tuple[list[Alert], str | None, int]:
        rows = list(self.alerts)
        if severity:
            rows = [a for a in rows if _enum_primitive(a.severity) == severity]
        if tactic:
            rows = [a for a in rows if a.tactic == tactic]
        if status:
            rows = [a for a in rows if _enum_primitive(a.status) == status]
        if date_from:
            df = _norm_iso(date_from)
            rows = [a for a in rows if _norm_iso(a.timestamp) >= df]
        if date_to:
            dt = _norm_iso(date_to)
            rows = [a for a in rows if _norm_iso(a.timestamp) <= dt]

        sev_order = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}

        def sev_key(a: Alert) -> int:
            return sev_order[_enum_primitive(a.severity)]

        if sort == "timestamp_desc":
            rows.sort(key=lambda a: _norm_iso(a.timestamp), reverse=True)
        elif sort == "timestamp_asc":
            rows.sort(key=lambda a: _norm_iso(a.timestamp))
        elif sort == "severity_desc":
            rows.sort(key=sev_key, reverse=True)
        else:
            rows.sort(key=lambda a: _norm_iso(a.timestamp), reverse=True)

        total = len(rows)
        start = 0
        if cursor:
            try:
                raw = base64.urlsafe_b64decode(cursor.encode())
                start = int(json.loads(raw.decode())["i"])
            except Exception:
                start = 0
        chunk = rows[start : start + limit]
        next_cursor: str | None = None
        if start + limit < total:
            next_cursor = base64.urlsafe_b64encode(json.dumps({"i": start + limit}).encode()).decode()
        return chunk, next_cursor, total

    def get_alert(self, alert_id: str) -> Alert | None:
        for a in self.alerts:
            if a.id == alert_id:
                return a.model_copy(deep=True)
        return None

    def update_alert_status(self, alert_id: str, status: AlertStatus) -> Alert | None:
        for i, a in enumerate(self.alerts):
            if a.id == alert_id:
                updated = a.model_copy(deep=True)
                updated = updated.model_copy(update={"status": status})
                self.alerts[i] = updated
                return updated.model_copy(deep=True)
        return None

    # --- Devices ---

    def get_device(self, device_id: str) -> Device | None:
        for d in self.devices:
            if d.id == device_id:
                return d.model_copy(deep=True)
        return None

    def set_device_status(self, device_id: str, status: DeviceStatus) -> Device | None:
        for i, d in enumerate(self.devices):
            if d.id == device_id:
                new_d = d.model_copy(update={"status": status})
                self.devices[i] = new_d
                return new_d.model_copy(deep=True)
        return None

    def sync_alert_devices_for_device_id(self, device_id: str) -> None:
        dev = self.get_device(device_id)
        if not dev:
            return
        for i, a in enumerate(self.alerts):
            if a.device_id == device_id:
                self.alerts[i] = a.model_copy(update={"device": dev.model_copy(deep=True)})

    # --- Incidents ---

    def get_incident(self, incident_id: str) -> Incident | None:
        for inc in self.incidents:
            if inc.id == incident_id:
                return inc.model_copy(deep=True)
        return None

    def append_quarantine_to_open_incidents(self, device_id: str, description: str) -> None:
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        for i, inc in enumerate(self.incidents):
            if _enum_primitive(inc.status) in ("RESOLVED", "POST_MORTEM"):
                continue
            dev_ids = {d.id for d in inc.affected_devices}
            if device_id not in dev_ids:
                continue
            ev = IncidentEvent(
                id=f"qe-{int(time.time() * 1000)}-{i}",
                timestamp=now,
                type="QUARANTINE",
                description=description,
            )
            new_timeline = list(inc.timeline) + [ev]
            self.incidents[i] = inc.model_copy(update={"timeline": new_timeline})

    # --- FL ---

    def get_fl_client(self, client_id: str) -> FLClient | None:
        for c in self.fl_clients:
            if c.id == client_id:
                return c.model_copy(deep=True)
        return None

    def fl_status_dict(self) -> dict[str, Any]:
        def _st(s: Any) -> str:
            return s.value if hasattr(s, "value") else str(s)

        rounds = self.fl_rounds
        current = rounds[-1].round if rounds else 0
        total_rounds = len(rounds)
        latest = rounds[-1] if rounds else None
        active_clients = sum(1 for c in self.fl_clients if _st(c.status) == "ACTIVE")
        total_clients = len(self.fl_clients)
        poison = any(_st(c.status) == "POISONING_SUSPECT" for c in self.fl_clients)
        return {
            "currentRound": current,
            "totalRounds": total_rounds,
            "activeClients": active_clients,
            "totalClients": total_clients,
            "nextRoundIn": 180,
            "aggregatorStatus": "AGGREGATING",
            "latestAccuracy": round(latest.accuracy, 1) if latest else 0.0,
            "latestFpRate": round(latest.fp_rate, 1) if latest else 0.0,
            "driftDetected": poison,
            "activeModel": self.active_model_name,
            "modelZoo": sorted(self.model_zoo_names),
        }

    # --- Forensics ---

    def list_samples(
        self,
        *,
        limit: int = 50,
        cursor: str | None = None,
        status: str | None = None,
        family: str | None = None,
    ) -> tuple[list[MalwareSample], str | None, int]:
        rows = list(self.malware_samples)
        if status:
            rows = [s for s in rows if s.status == status]
        if family:
            rows = [s for s in rows if s.family == family]
        total = len(rows)
        start = 0
        if cursor:
            try:
                raw = base64.urlsafe_b64decode(cursor.encode())
                start = int(json.loads(raw.decode())["i"])
            except Exception:
                start = 0
        chunk = rows[start : start + limit]
        next_cursor: str | None = None
        if start + limit < total:
            next_cursor = base64.urlsafe_b64encode(json.dumps({"i": start + limit}).encode()).decode()
        return chunk, next_cursor, total

    def get_rca(self, rca_id: str) -> RCAReport | None:
        for r in self.rca_reports:
            if r.id == rca_id:
                return r.model_copy(deep=True)
        return None

    # --- Audit ---

    def append_audit(
        self,
        *,
        actor: str,
        action: AuditAction,
        target: str,
        result: str,
    ) -> AuditLog:
        global AUDIT_COUNTER
        AUDIT_COUNTER += 1
        aid = f"AUD-{AUDIT_COUNTER}"
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        prev = self.audit_logs[-1].hash if self.audit_logs else ""
        row = {"timestamp": now, "actor": actor, "action": action, "target": target, "result": result}
        h = _audit_hash(prev, row)
        log = AuditLog(id=aid, timestamp=now, actor=actor, action=action, target=target, result=result, hash=h)
        self.audit_logs.append(log)
        return log

    def verify_audit_chain(self) -> dict[str, Any]:
        checked_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        total = len(self.audit_logs)
        if total == 0:
            return {"valid": True, "totalLogs": 0, "checkedAt": checked_at}
        prev = ""
        for log in self.audit_logs:
            row = {
                "timestamp": log.timestamp,
                "actor": log.actor,
                "action": log.action,
                "target": log.target,
                "result": log.result,
            }
            expected = _audit_hash(prev, row)
            if expected != log.hash:
                return {
                    "valid": False,
                    "firstBreakAt": log.id,
                    "totalLogs": total,
                    "checkedAt": checked_at,
                }
            prev = log.hash
        return {"valid": True, "totalLogs": total, "checkedAt": checked_at}

    # --- Users ---

    def upsert_session_user(
        self,
        *,
        uid: str,
        email: str | None,
        display_name: str | None,
        photo_url: str | None,
    ) -> UserRecord:
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        if uid in self.users:
            u = self.users[uid]
            updated = UserRecord(
                uid=u.uid,
                email=email if email is not None else u.email,
                display_name=display_name if display_name is not None else u.display_name,
                photo_url=photo_url if photo_url is not None else u.photo_url,
                created_at=u.created_at,
                last_login_at=now,
            )
            self.users[uid] = updated
            return updated
        self.users[uid] = UserRecord(
            uid=uid,
            email=email,
            display_name=display_name,
            photo_url=photo_url,
            created_at=now,
            last_login_at=now,
        )
        return self.users[uid]

    # --- KPIs ---

    def dashboard_kpis(self) -> dict[str, Any]:
        open_alerts = [a for a in self.alerts if _enum_primitive(a.status) == "OPEN"]
        critical = [
            a
            for a in self.alerts
            if _enum_primitive(a.severity) == "CRITICAL" and _enum_primitive(a.status) == "OPEN"
        ]
        avg_conf = sum(a.confidence for a in self.alerts) / len(self.alerts) if self.alerts else 0.0
        watch_statuses = {
            _enum_primitive(DeviceStatus.SUSPICIOUS),
            _enum_primitive(DeviceStatus.COMPROMISED),
            _enum_primitive(DeviceStatus.ISOLATED),
        }
        under_watch = sum(1 for d in self.devices if _enum_primitive(d.status) in watch_statuses)
        fl_round = self.fl_rounds[-1].round if self.fl_rounds else 0
        open_inc = sum(
            1
            for i in self.incidents
            if _enum_primitive(i.status) not in ("RESOLVED", "POST_MORTEM")
        )
        today = datetime.now(timezone.utc).date()
        resolved_today = sum(
            1
            for a in self.alerts
            if _enum_primitive(a.status) == "RESOLVED" and _norm_iso(a.timestamp).date() == today
        )
        fp_count = sum(1 for a in self.alerts if _enum_primitive(a.status) == "FALSE_POSITIVE")
        fp_rate = (fp_count / len(self.alerts) * 100) if self.alerts else 0.0
        return {
            "activeThreats": len(open_alerts),
            "avgConfidence": round(avg_conf, 1),
            "devicesUnderWatch": under_watch,
            "flRound": fl_round,
            "openIncidents": open_inc,
            "criticalAlerts": len(critical),
            "resolvedToday": resolved_today,
            "falsePositiveRate": round(fp_rate, 1),
        }

    # --- Hunain endpoints ---

    def get_sample(self, sample_id: str) -> MalwareSample | None:
        for s in self.malware_samples:
            if s.id == sample_id:
                return s.model_copy(deep=True)
        return None

    def list_incidents(
        self,
        *,
        limit: int = 100,
        cursor: str | None = None,
        status: str | None = None,
        severity: str | None = None,
        assignee: str | None = None,
    ) -> tuple[list[Incident], str | None, int]:
        rows = list(self.incidents)
        if status:
            rows = [i for i in rows if _enum_primitive(i.status) == status]
        if severity:
            rows = [i for i in rows if _enum_primitive(i.severity) == severity]
        if assignee:
            rows = [i for i in rows if i.assignee == assignee]

        total = len(rows)
        start = 0
        if cursor:
            try:
                raw = base64.urlsafe_b64decode(cursor.encode())
                start = int(json.loads(raw.decode())["i"])
            except Exception:
                start = 0

        chunk = rows[start : start + limit]
        next_cursor: str | None = None
        if start + limit < total:
            next_cursor = base64.urlsafe_b64encode(json.dumps({"i": start + limit}).encode()).decode()
        return chunk, next_cursor, total

    def run_playbook(self, incident_id: str, now_iso: str) -> tuple[Incident | None, int | None]:
        for i, inc in enumerate(self.incidents):
            if inc.id != incident_id:
                continue

            current_step = 1
            if inc.playbook.steps:
                step_idx = None
                for idx, st in enumerate(inc.playbook.steps):
                    if st.status in ("PENDING", "RUNNING"):
                        step_idx = idx
                        break
                if step_idx is None:
                    step_idx = 0
                current_step = inc.playbook.steps[step_idx].step_number
                updated_step = inc.playbook.steps[step_idx].model_copy(
                    update={"status": "RUNNING", "timestamp": now_iso}
                )
                new_steps = list(inc.playbook.steps)
                new_steps[step_idx] = updated_step
                inc = inc.model_copy(update={"playbook": inc.playbook.model_copy(update={"steps": new_steps})})

            inc = inc.model_copy(
                update={
                    "status": inc.status,
                    "playbook": inc.playbook.model_copy(
                        update={"executions": inc.playbook.executions + 1, "last_run": now_iso, "status": "ACTIVE"}
                    ),
                }
            )

            ev = IncidentEvent(
                id=f"ps-{int(time.time() * 1000)}-{i}",
                timestamp=now_iso,
                type="PLAYBOOK_START",
                description="Playbook run started",
            )
            inc = inc.model_copy(update={"timeline": list(inc.timeline) + [ev]})
            self.incidents[i] = inc
            return inc.model_copy(deep=True), current_step

        return None, None

    def list_audit_logs(
        self,
        *,
        limit: int = 50,
        cursor: str | None = None,
        action: str | None = None,
        actor: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> tuple[list[AuditLog], str | None, int]:
        rows = list(self.audit_logs)
        if action:
            rows = [l for l in rows if _enum_primitive(l.action) == action]
        if actor:
            rows = [l for l in rows if l.actor == actor]
        if date_from:
            df = _norm_iso(date_from)
            rows = [l for l in rows if _norm_iso(l.timestamp) >= df]
        if date_to:
            dt = _norm_iso(date_to)
            rows = [l for l in rows if _norm_iso(l.timestamp) <= dt]

        total = len(rows)
        start = 0
        if cursor:
            try:
                raw = base64.urlsafe_b64decode(cursor.encode())
                start = int(json.loads(raw.decode())["i"])
            except Exception:
                start = 0

        chunk = rows[start : start + limit]
        next_cursor: str | None = None
        if start + limit < total:
            next_cursor = base64.urlsafe_b64encode(json.dumps({"i": start + limit}).encode()).decode()
        return chunk, next_cursor, total

    def list_conversations(self) -> list[ConversationSummary]:
        return [c.model_copy(deep=True) for c in self.conversations]

    def list_conversation_history(self, conversation_id: str) -> list[BotMessage]:
        msgs = self.conversation_messages.get(conversation_id, [])
        return [m.model_copy(deep=True) for m in msgs]

    def append_bot_message(
        self, *, conversation_id: str, role: str, content: str, now_iso: str
    ) -> BotMessage:
        msg = BotMessage(
            id=f"msg-{int(time.time() * 1000)}",
            role=role,  # validate in router / request parsing
            content=content,
            timestamp=now_iso,
        )
        if conversation_id not in self.conversation_messages:
            self.conversation_messages[conversation_id] = []
        self.conversation_messages[conversation_id].append(msg)

        updated_at = now_iso
        preview = content[:80]
        found = False
        for idx, c in enumerate(self.conversations):
            if c.id == conversation_id:
                found = True
                new_count = len(self.conversation_messages[conversation_id])
                self.conversations[idx] = c.model_copy(
                    update={"updated_at": updated_at, "message_count": new_count, "preview": c.preview or preview}
                )
                break
        if not found:
            self.conversations.append(
                ConversationSummary(
                    id=conversation_id,
                    title=preview,
                    preview=preview,
                    created_at=updated_at,
                    updated_at=updated_at,
                    message_count=len(self.conversation_messages[conversation_id]),
                )
            )
        return msg.model_copy(deep=True)

    def activate_fl_model(self, model_name: str, now_iso: str) -> str | None:
        if model_name not in self.model_zoo_names:
            return None
        prev = self.active_model_name
        self.active_model_name = model_name
        return prev

    def next_fl_client_patch(self) -> dict[str, Any]:
        if not self.fl_clients:
            raise RuntimeError("No FL clients seeded")
        idx = random.randrange(len(self.fl_clients))
        client = self.fl_clients[idx]

        patch: dict[str, Any] = {"id": client.id}
        status_s = _enum_primitive(client.status)

        # Keep changes small so the UI doesn't jump wildly.
        r = random.random()
        if status_s == "OFFLINE":
            if r > 0.7:
                new_status = FLClientStatus.ACTIVE
                new_part = 85 + int(random.random() * 15)
                new_round = max(client.last_round + 1, 1)
                client = client.model_copy(
                    update={"status": new_status, "participation_pct": float(new_part), "last_round": new_round}
                )
                patch["status"] = new_status.value
                patch["participationPct"] = float(new_part)
                patch["lastRound"] = new_round
        else:
            if r < 0.4:
                delta = (1 if random.random() > 0.5 else -1) * int(random.random() * 3)
                new_part = max(0.0, min(100.0, client.participation_pct + delta))
                client = client.model_copy(update={"participation_pct": new_part})
                patch["participationPct"] = float(round(new_part, 1))
            elif r < 0.7:
                new_round = client.last_round + 1
                client = client.model_copy(update={"last_round": new_round})
                patch["lastRound"] = new_round
            else:
                new_status = "DEGRADED" if status_s == "ACTIVE" else "ACTIVE"
                client = client.model_copy(update={"status": new_status})
                patch["status"] = new_status

            if "lastRound" not in patch and status_s != "OFFLINE":
                patch["lastRound"] = client.last_round

        self.fl_clients[idx] = client
        if set(patch.keys()) == {"id"}:
            patch["lastRound"] = client.last_round
        return patch

    # --- SSE synthetic alert ---

    def next_streaming_alert(self) -> Alert:
        base = random.choice(self.alerts) if self.alerts else None
        if base is None:
            raise RuntimeError("No alerts seeded")
        ms = int(time.time() * 1000)
        return base.model_copy(
            update={
                "id": f"ALT-{ms}",
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            },
            deep=True,
        )


state = AppState()
