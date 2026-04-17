from pathlib import Path

from dotenv import load_dotenv
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_backend_env_path() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        candidate = parent / ".env"
        if candidate.exists():
            return candidate
        if parent.name == "backend":
            return candidate
    return current.parents[1] / ".env"


BACKEND_ENV_PATH = _find_backend_env_path()
load_dotenv(BACKEND_ENV_PATH)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(BACKEND_ENV_PATH), env_file_encoding="utf-8", extra="ignore")

    allowed_origins: str = (
        "http://localhost:3000,http://127.0.0.1:3000,"
        "http://localhost:3001,http://127.0.0.1:3001"
    )
    api_title: str = "BastionFed API"
    # Resolved relative to cwd; run API from backend/ → backend/data/runtime/ (see backend/DATA_DIRECTORY.md)
    bastionbot_db_path: str = "data/runtime/bastionbot.sqlite3"
    # After Postgres bootstrap, merge legacy local BastionBot SQLite into bot_* tables (idempotent).
    bastionbot_import_sqlite_on_postgres_boot: bool = Field(
        default=True,
        validation_alias="BASTIONBOT_IMPORT_SQLITE_ON_POSTGRES_BOOT",
    )
    # If local SQLite predates tenant_id columns, set this to your real tenant id for import.
    bastionbot_import_legacy_default_tenant_id: str | None = Field(
        default=None,
        validation_alias="BASTIONBOT_IMPORT_LEGACY_DEFAULT_TENANT_ID",
    )
    gemini_api_key: str = Field(default="", validation_alias=AliasChoices("GEMINI_API_KEY", "GOOGLE_API_KEY"))
    gemini_model: str = Field(default="gemini-1.5-flash", validation_alias="GEMINI_MODEL")
    groq_api_key: str = ""
    groq_model: str = "llama-3.1-8b-instant"
    demo_mode: bool = Field(default=False, validation_alias="DEMO_MODE")
    demo_tenant_id: str = "tenant-demo"
    demo_tenant_name: str = "BastionFed Demo"
    firebase_project_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("FIREBASE_PROJECT_ID", "NEXT_PUBLIC_FIREBASE_PROJECT_ID"),
    )
    # Web API key — used server-side to call the Identity Toolkit REST API for user creation.
    # Already in .env as NEXT_PUBLIC_FIREBASE_API_KEY; no service account needed.
    firebase_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("FIREBASE_API_KEY", "NEXT_PUBLIC_FIREBASE_API_KEY"),
    )
    firebase_auth_emulator_uid: str | None = Field(default=None, validation_alias="FIREBASE_AUTH_EMULATOR_UID")
    firebase_cert_url: str = "https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com"

    # Supabase Postgres (see docs/FIREBASE_DATA_PLANE_MAPPING.md)
    database_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("DATABASE_URL", "SUPABASE_DATABASE_URL"),
    )
    # Upstash or any Redis for SSE pub/sub
    redis_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("REDIS_URL", "UPSTASH_REDIS_URL"),
    )
    # Supabase Storage (forensics + models buckets)
    supabase_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SUPABASE_URL", "SUPABASE_PROJECT_URL"),
    )
    supabase_service_key: str | None = Field(default=None, validation_alias="SUPABASE_SERVICE_KEY")
    supabase_forensics_bucket: str = "forensics"
    supabase_models_bucket: str = "models"
    # Training / client PNG+JSON artifacts (single bucket; override with SUPABASE_ARTIFACTS_BUCKET)
    supabase_artifacts_bucket: str = "images"

    # When true, require Postgres + Redis + Supabase Storage env and live probes at startup (no silent DB fallback).
    strict_data_plane: bool = Field(default=False, validation_alias="BASTIONFED_STRICT_DATA_PLANE")

    # Signed download URLs for private Storage objects (forensics / models)
    storage_signed_url_expires_s: int = Field(
        default=3600,
        ge=60,
        le=604800,
        validation_alias=AliasChoices("STORAGE_SIGNED_URL_EXPIRES_S", "SUPABASE_SIGNED_URL_EXPIRES_S"),
    )

    # SMTP email (for sending client credentials)
    smtp_host: str | None = Field(default=None, validation_alias="SMTP_HOST")
    smtp_port: int = Field(default=587, validation_alias="SMTP_PORT")
    smtp_user: str | None = Field(default=None, validation_alias="SMTP_USER")
    smtp_password: str | None = Field(default=None, validation_alias="SMTP_PASSWORD")
    smtp_from_email: str | None = Field(default=None, validation_alias="SMTP_FROM_EMAIL")
    smtp_from_name: str = Field(default="BastionFed", validation_alias="SMTP_FROM_NAME")

    # Firebase Admin SDK (for creating Firebase Auth users on behalf of admins)
    # Pass the full service-account JSON as a single-line string in this env var.
    firebase_admin_credentials_json: str | None = Field(
        default=None, validation_alias="FIREBASE_SERVICE_ACCOUNT_KEY_JSON"
    )

    # Frontend base URL (used in credential emails)
    frontend_base_url: str = Field(default="http://localhost:3000", validation_alias="FRONTEND_BASE_URL")

    # Max FL client nodes an admin can provision for a tenant (PERSON + DEVICE combined)
    max_clients_per_admin: int = Field(default=5, ge=1, le=100, validation_alias="MAX_CLIENTS_PER_ADMIN")

    # When True: onboarding only registers empty FL client rows in Postgres — no Firebase user creation,
    # credential email, or membership_client_scopes wiring. False = full PERSON flow (Auth + email + scope).
    identity_only_provisioning: bool = Field(default=False, validation_alias="BASTIONFED_IDENTITY_ONLY_PROVISIONING")

    # Persist in-memory AppState snapshot to Postgres this often (seconds)
    db_snapshot_interval_s: float = 20.0
    # SSE: when using Redis, synthetic alert publish interval (seconds)
    sse_alert_publish_interval_s: float = 60.0
    sse_fl_publish_interval_s: float = 2.0

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def persistence_enabled(self) -> bool:
        return bool(self.database_url and self.database_url.strip())

    @property
    def redis_enabled(self) -> bool:
        return bool(self.redis_url and self.redis_url.strip())

    @property
    def supabase_storage_enabled(self) -> bool:
        return bool(self.supabase_url and self.supabase_service_key)


settings = Settings()
