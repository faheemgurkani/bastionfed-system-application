from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.models.domain import (
    Alert,
    AuditLog,
    BotChatContext,
    BotMessage,
    ConversationSummary,
    FLClient,
    FLClientType,
    FLRound,
    IngestEventResult,
    IngestSource,
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
    account_type: str | None = Field(None, alias="accountType")


class AuthSessionResponse(CamelRequest):
    uid: str
    created_at: str = Field(..., alias="createdAt")
    last_login_at: str = Field(..., alias="lastLoginAt")
    tenant_id: str | None = Field(None, alias="tenantId")
    role: str | None = None
    is_new_tenant: bool = Field(..., alias="isNewTenant")
    needs_client_invite: bool = Field(False, alias="needsClientInvite")


class AuthBootstrapResponse(CamelRequest):
    has_membership: bool = Field(..., alias="hasMembership")
    tenant_id: str | None = Field(None, alias="tenantId")
    role: str | None = None


class ClientUserInviteCreateRequest(CamelRequest):
    email: str | None = None
    fl_client_ids: list[str] = Field(..., alias="flClientIds")
    expires_in_days: int = Field(14, alias="expiresInDays")


class ClientUserInviteCreateResponse(CamelRequest):
    invite_id: str = Field(..., alias="inviteId")
    token: str
    expires_in_days: int = Field(..., alias="expiresInDays")


class ClientUserInviteAcceptRequest(CamelRequest):
    token: str


class ClientUserInviteItem(CamelRequest):
    invite_id: str = Field(..., alias="inviteId")
    email: str | None = None
    fl_client_ids: list[str] = Field(..., alias="flClientIds")
    expires_at: str = Field(..., alias="expiresAt")
    created_at: str = Field(..., alias="createdAt")
    consumed_at: str | None = Field(None, alias="consumedAt")


class ClientUserInvitesListResponse(CamelRequest):
    invites: list[ClientUserInviteItem]


class FLClientPatchBody(CamelRequest):
    client_type: FLClientType = Field(..., alias="clientType")


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


class IngestSourceCreateRequest(CamelRequest):
    name: str
    source_type: str = Field(..., alias="sourceType")
    connector_kind: str = Field(..., alias="connectorKind")


class IngestSourceResponse(CamelRequest):
    source: IngestSource
    secret: str | None = None


class IngestSourceListResponse(CamelRequest):
    items: list[IngestSource]


class IngestEventRequest(CamelRequest):
    source_id: str = Field(..., alias="sourceId")
    external_id: str = Field(..., alias="externalId")
    event_type: str = Field(..., alias="eventType")
    occurred_at: str | None = Field(None, alias="occurredAt")
    payload: dict


class IngestEventResponse(CamelRequest):
    result: IngestEventResult


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


# --- Admin client-provisioning (onboarding) ---

class OnboardingClientInput(CamelRequest):
    """A single client definition submitted by an admin during onboarding."""

    node_name: str = Field(..., alias="nodeName")
    client_type: str = Field(..., alias="clientType")  # "PERSON" | "DEVICE"
    email: str | None = Field(default=None)
    department: str | None = Field(default=None)


class OnboardingClientResult(CamelRequest):
    """Per-client result returned from the onboarding endpoint."""

    node_name: str = Field(..., alias="nodeName")
    client_type: str = Field(..., alias="clientType")
    status: str  # "created" | "error" | "email_failed"
    client_id: str | None = Field(default=None, alias="clientId")
    email: str | None = Field(default=None)
    firebase_uid: str | None = Field(default=None, alias="firebaseUid")
    error: str | None = Field(default=None)
    email_error: str | None = Field(default=None, alias="emailError")
    identity_only: bool = Field(
        default=False,
        alias="identityOnly",
        description="True when BASTIONFED_IDENTITY_ONLY_PROVISIONING: DB shell only, no Firebase/email.",
    )


class OnboardingClientsRequest(CamelRequest):
    clients: list[OnboardingClientInput]
    tenant_name: str | None = Field(default=None, alias="tenantName")


class OnboardingClientsResponse(CamelRequest):
    results: list[OnboardingClientResult]
    created_count: int = Field(..., alias="createdCount")
    error_count: int = Field(..., alias="errorCount")


class OnboardingLimitsResponse(CamelRequest):
    """How many more clients the current admin may provision for this tenant."""

    max_clients_per_admin: int
    already_provisioned: int
    remaining: int
