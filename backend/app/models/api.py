from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.models.domain import (
    Alert,
    AuditLog,
    BotChatContext,
    BotMessage,
    ConversationSummary,
    FLClient,
    FLRound,
    Incident,
    MalwareSample,
    SourceCitation,
)


class CamelRequest(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class AlertListResponse(CamelRequest):
    items: list[Alert]
    next_cursor: str | None = Field(None, alias="nextCursor")
    total: int


class MalwareSampleListResponse(CamelRequest):
    items: list[MalwareSample]
    next_cursor: str | None = Field(None, alias="nextCursor")
    total: int


class AuthSessionRequest(CamelRequest):
    uid: str
    email: str | None = None
    display_name: str | None = None
    photo_url: str | None = None


class AuthSessionResponse(CamelRequest):
    uid: str
    created_at: str = Field(..., alias="createdAt")
    last_login_at: str = Field(..., alias="lastLoginAt")


class AlertPatchRequest(CamelRequest):
    status: str


class DashboardKpisResponse(CamelRequest):
    active_threats: int = Field(..., alias="activeThreats")
    avg_confidence: float = Field(..., alias="avgConfidence")
    devices_under_watch: int = Field(..., alias="devicesUnderWatch")
    fl_round: int = Field(..., alias="flRound")
    open_incidents: int = Field(..., alias="openIncidents")
    critical_alerts: int = Field(..., alias="criticalAlerts")
    resolved_today: int = Field(..., alias="resolvedToday")
    false_positive_rate: float = Field(..., alias="falsePositiveRate")


class QuarantineResponse(CamelRequest):
    device_id: str = Field(..., alias="deviceId")
    status: str
    command_id: str = Field(..., alias="commandId")
    sent_at: str = Field(..., alias="sentAt")


class AuditVerifyValidResponse(CamelRequest):
    valid: bool = True
    total_logs: int = Field(..., alias="totalLogs")
    checked_at: str = Field(..., alias="checkedAt")


class AuditVerifyInvalidResponse(CamelRequest):
    valid: bool = False
    first_break_at: str = Field(..., alias="firstBreakAt")
    total_logs: int = Field(..., alias="totalLogs")
    checked_at: str = Field(..., alias="checkedAt")


class IncidentListResponse(CamelRequest):
    items: list[Incident]
    next_cursor: str | None = Field(None, alias="nextCursor")
    total: int


class EscalateAlertResponse(CamelRequest):
    incident: Incident


class PlaybookRunResponse(CamelRequest):
    incident_id: str = Field(..., alias="incidentId")
    playbook_id: str = Field(..., alias="playbookId")
    started_at: str = Field(..., alias="startedAt")
    current_step: int = Field(..., alias="currentStep")


class FLRoundsResponse(CamelRequest):
    rounds: list[FLRound]
    session_id: str = Field(..., alias="sessionId")


class FLClientsResponse(CamelRequest):
    clients: list[FLClient]


class AuditLogsResponse(CamelRequest):
    items: list[AuditLog]
    next_cursor: str | None = Field(None, alias="nextCursor")
    total: int


class ConversationListResponse(CamelRequest):
    conversations: list[ConversationSummary]


class BastionBotChatRequest(CamelRequest):
    message: str
    conversation_id: str | None = Field(None, alias="conversationId")
    context: BotChatContext | None = None


class ConversationHistoryResponse(CamelRequest):
    conversation_id: str = Field(..., alias="conversationId")
    conversation: ConversationSummary
    messages: list[BotMessage]


class BastionBotChatResponse(CamelRequest):
    message: BotMessage
    conversation_id: str = Field(..., alias="conversationId")
    conversation: ConversationSummary
    sources: list[SourceCitation]
    memory_used: bool = Field(..., alias="memoryUsed")


class FLModelActivateResponse(CamelRequest):
    activated: str
    previously_active: str = Field(..., alias="previouslyActive")
    switched_at: str = Field(..., alias="switchedAt")
