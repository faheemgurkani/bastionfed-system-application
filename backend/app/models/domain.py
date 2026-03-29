from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, use_enum_values=True)


# --- Enums ---


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class AlertStatus(str, Enum):
    OPEN = "OPEN"
    IN_REVIEW = "IN_REVIEW"
    RESOLVED = "RESOLVED"
    FALSE_POSITIVE = "FALSE_POSITIVE"


class FLClientStatus(str, Enum):
    ACTIVE = "ACTIVE"
    DEGRADED = "DEGRADED"
    OFFLINE = "OFFLINE"
    POISONING_SUSPECT = "POISONING_SUSPECT"


class IncidentStatus(str, Enum):
    NEW = "NEW"
    TRIAGING = "TRIAGING"
    RESPONDING = "RESPONDING"
    RESOLVED = "RESOLVED"
    POST_MORTEM = "POST_MORTEM"


class DeviceStatus(str, Enum):
    NORMAL = "NORMAL"
    SUSPICIOUS = "SUSPICIOUS"
    COMPROMISED = "COMPROMISED"
    ISOLATED = "ISOLATED"


class AuditAction(str, Enum):
    DETECTION_MADE = "DETECTION_MADE"
    RESPONSE_TRIGGERED = "RESPONSE_TRIGGERED"
    MODEL_UPDATED = "MODEL_UPDATED"
    USER_LOGIN = "USER_LOGIN"
    DEVICE_QUARANTINED = "DEVICE_QUARANTINED"
    CONFIG_CHANGED = "CONFIG_CHANGED"
    REPORT_GENERATED = "REPORT_GENERATED"
    FL_ROUND_COMPLETED = "FL_ROUND_COMPLETED"


# --- Nested / entities ---


class Device(CamelModel):
    id: str
    name: str
    ip: str
    type: str
    wing: str
    criticality: int
    fl_client_id: str
    status: DeviceStatus


class MitreAttackTechnique(CamelModel):
    id: str
    tactic: str
    name: str


class ThreatIntelIndicator(CamelModel):
    type: Literal["HASH", "IP", "DOMAIN"]
    value: str
    source: str


class Alert(CamelModel):
    id: str
    timestamp: str
    device_id: str
    device: Device
    type: str
    tactic: str
    technique: MitreAttackTechnique
    severity: Severity
    confidence: float
    status: AlertStatus
    model_version: str
    threat_intel: list[ThreatIntelIndicator]
    cve_reference: str | None = None
    feature_summary: str


class FLRound(CamelModel):
    round: int
    accuracy: float
    fp_rate: float
    train_loss: float
    val_loss: float


class FLClient(CamelModel):
    id: str
    department: str
    participation_pct: float
    last_round: int
    dp_epsilon: float
    model_version: str
    status: FLClientStatus


class PlaybookStep(CamelModel):
    id: str
    step_number: int
    name: str
    status: Literal["COMPLETED", "RUNNING", "PENDING"]
    timestamp: str | None = None
    notes: str | None = None


class Playbook(CamelModel):
    id: str
    name: str
    trigger_condition: str
    last_run: str
    executions: int
    status: Literal["ACTIVE", "DRAFT", "DEPRECATED"]
    steps: list[PlaybookStep]


class IncidentEvent(CamelModel):
    id: str
    timestamp: str
    type: Literal[
        "DETECTION",
        "ALERT",
        "PLAYBOOK_START",
        "QUARANTINE",
        "ANALYST_ASSIGNED",
        "RESOLVED",
    ]
    description: str


class Incident(CamelModel):
    id: str
    title: str
    severity: Severity
    status: IncidentStatus
    affected_devices: list[Device]
    time_open: str
    analyst_initials: str
    timeline: list[IncidentEvent]
    playbook: Playbook
    ticket_id: str
    reporter: str
    assignee: str
    priority: str
    created: str
    labels: list[str]


class StaticAnalysis(CamelModel):
    imports: list[str]
    strings: list[str]


class DynamicAnalysis(CamelModel):
    network: list[str]
    file_system: list[str]
    processes: list[str]


class SampleAnalysis(CamelModel):
    static: StaticAnalysis
    dynamic: DynamicAnalysis


class MalwareSample(CamelModel):
    id: str
    sha256: str
    md5: str
    filename: str
    size: str
    type: str
    device_id: str
    timestamp: str
    upload_time: str
    family: str
    threat_score: int
    status: Literal["COMPLETED", "IN_PROGRESS", "PENDING", "ANALYZED", "ANALYZING"]
    analysis: SampleAnalysis


class TimelineNode(CamelModel):
    label: str
    timestamp: str


class AffectedNode(CamelModel):
    device_name: str
    ip: str
    impact: str


class RCAReport(CamelModel):
    id: str
    incident_id: str
    title: str
    executive_summary: str
    timeline_nodes: list[TimelineNode]
    affected_nodes: list[AffectedNode]
    mitre_chain: list[str]
    response_actions: list[str]
    recommendations: list[str]


class AuditLog(CamelModel):
    id: str
    timestamp: str
    actor: str
    action: AuditAction | str
    target: str
    result: str
    hash: str


class UserRecord(BaseModel):
    uid: str
    email: str | None
    display_name: str | None
    photo_url: str | None
    created_at: str
    last_login_at: str


class BotMessage(CamelModel):
    id: str
    role: Literal["USER", "BOT"]
    content: str
    timestamp: str
    sources: list["SourceCitation"] = []


class ConversationSummary(CamelModel):
    id: str
    title: str
    preview: str
    created_at: str
    updated_at: str
    message_count: int


class BotChatContext(CamelModel):
    alert_id: str | None = None
    incident_id: str | None = None


class SourceCitation(CamelModel):
    id: str
    label: str
    source_type: Literal["doc", "ui", "api", "live_data"]
    path: str
    excerpt: str


class FLClientPatch(CamelModel):
    id: str
    participation_pct: float | None = None
    last_round: int | None = None
    status: FLClientStatus | None = None
