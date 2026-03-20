from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.models.domain import Alert, MalwareSample


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
