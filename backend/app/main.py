import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.bastionbot import bastionbot_engine
from app.data_plane_probes import (
    readiness_report,
    require_readiness_ok_or_raise,
    strict_env_misconfiguration_message,
)
from app.bastionbot.pg_store import PostgresBastionBotStore
from app.bastionbot.sqlite_to_postgres import import_legacy_bastionbot_sqlite
from app.bastionbot.storage import BastionBotStore, set_bastionbot_store
from app.config import settings
from app import runtime_config
from app.db.migrate import run_migrations
from app.store.tenant_store import MemoryTenantStore, PostgresTenantStore, set_tenant_store, tenant_store

logger = logging.getLogger(__name__)

_PERSISTENCE_BOOT_TIMEOUT_S = 45.0
_BASTIONBOT_INDEX_TIMEOUT_S = 120.0


def _fallback_sqlite_and_memory() -> None:
    sqlite_store = BastionBotStore(settings.bastionbot_db_path)
    set_bastionbot_store(sqlite_store)
    sqlite_store.initialize()
    set_tenant_store(MemoryTenantStore())


def _bootstrap_postgres_persistence() -> None:
    run_migrations()
    pg = PostgresBastionBotStore(settings.database_url or "")
    pg.initialize()
    set_bastionbot_store(pg)
    set_tenant_store(PostgresTenantStore(settings.database_url or ""))
    runtime_config.live_postgres = True
    if settings.bastionbot_import_sqlite_on_postgres_boot:
        backend_root = Path(__file__).resolve().parents[1]
        try:
            import_legacy_bastionbot_sqlite(
                settings.bastionbot_db_path,
                settings.database_url or "",
                backend_root=backend_root,
                legacy_default_tenant_id=settings.bastionbot_import_legacy_default_tenant_id,
            )
        except Exception:
            logger.warning(
                "BastionBot legacy SQLite import failed; Postgres store is still active.",
                exc_info=True,
            )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    strict_msg = strict_env_misconfiguration_message()
    if strict_msg:
        raise RuntimeError(strict_msg)

    stop = asyncio.Event()
    bg_tasks: list[asyncio.Task] = []
    runtime_config.live_postgres = False

    if settings.persistence_enabled:
        logger.info("Startup: Postgres (migrations + BastionBot DDL), timeout=%ss …", _PERSISTENCE_BOOT_TIMEOUT_S)
        try:
            await asyncio.wait_for(
                asyncio.to_thread(_bootstrap_postgres_persistence),
                timeout=_PERSISTENCE_BOOT_TIMEOUT_S,
            )
            logger.info("Startup: Postgres persistence ready.")
        except asyncio.TimeoutError:
            msg = (
                f"Postgres did not complete bootstrap within {_PERSISTENCE_BOOT_TIMEOUT_S:.0f}s "
                "(check DATABASE_URL / VPN / Supabase pooler; try `psql` to the same URL)."
            )
            if settings.strict_data_plane:
                raise RuntimeError(msg) from None
            logger.warning("%s Falling back to SQLite + in-memory.", msg)
            _fallback_sqlite_and_memory()
        except Exception:
            if settings.strict_data_plane:
                raise
            logger.exception(
                "Supabase/Postgres unavailable (check pooler URL and postgres.<ref> user). "
                "Falling back to SQLite BastionBot + tenant-scoped in-memory product state."
            )
            _fallback_sqlite_and_memory()
    else:
        if settings.strict_data_plane:
            raise RuntimeError(
                "BASTIONFED_STRICT_DATA_PLANE=1 requires DATABASE_URL or SUPABASE_DATABASE_URL"
            )
        logger.info("Startup: DATABASE_URL not set — SQLite BastionBot + in-memory tenant store.")
        sqlite_store = BastionBotStore(settings.bastionbot_db_path)
        set_bastionbot_store(sqlite_store)
        sqlite_store.initialize()
        set_tenant_store(MemoryTenantStore())

    # Demo/seed data is NOT written at startup. With DEMO_MODE=1, tenant_store.ensure_demo_tenant()
    # runs lazily on first ?dev=true (or legacy ?guest=true) auth — see app/auth/deps.py.

    logger.info("Startup: BastionBot knowledge index …")
    try:
        await asyncio.wait_for(
            asyncio.to_thread(bastionbot_engine.initialize),
            timeout=_BASTIONBOT_INDEX_TIMEOUT_S,
        )
    except asyncio.TimeoutError:
        logger.exception(
            "BastionBot knowledge index exceeded %ss (slow disk on repo path?). Server may be degraded.",
            _BASTIONBOT_INDEX_TIMEOUT_S,
        )
        raise RuntimeError("BastionBot startup timed out") from None

    # No outer asyncio timeout: data_plane_probes caps each service (Postgres/Redis/HTTP).
    logger.info("Startup: readiness checks (strict data-plane) …")
    await asyncio.to_thread(require_readiness_ok_or_raise)

    logger.info("Startup: application ready.")
    yield

    stop.set()
    for t in bg_tasks:
        t.cancel()
    await asyncio.gather(*bg_tasks, return_exceptions=True)

    from app.sse_bus import close_redis

    await close_redis()


app = FastAPI(title=settings.api_title, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

from app.routers import (  # noqa: E402
    access,
    alerts,
    audit,
    auth,
    bastionbot,
    dashboard,
    devices,
    events,
    fl,
    forensics,
    ingest,
    incidents,
    onboarding,
    storage,
)

app.include_router(access.router, prefix="/api")
app.include_router(alerts.router, prefix="/api")
app.include_router(incidents.router, prefix="/api")
app.include_router(fl.router, prefix="/api")
app.include_router(forensics.router, prefix="/api")
app.include_router(devices.router, prefix="/api")
app.include_router(audit.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(bastionbot.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(events.router, prefix="/api")
app.include_router(ingest.router, prefix="/api")
app.include_router(onboarding.router, prefix="/api")
app.include_router(storage.router, prefix="/api")


@app.get("/health/live")
def health_live():
    """Process is up (Kubernetes liveness). Does not check Postgres/Redis/Storage."""
    return {"status": "alive"}


@app.get("/health")
def health():
    payload: dict = {"status": "ok", "demo_mode": settings.demo_mode}
    if runtime_config.live_postgres:
        payload["persistence"] = "postgres"
        payload["bastionbot_storage"] = "postgres"
    else:
        payload["persistence"] = "memory"
        payload["bastionbot_storage"] = "sqlite"
    if settings.redis_enabled:
        payload["sse_bus"] = "redis"
    if settings.supabase_storage_enabled:
        payload["object_storage"] = "supabase"
    if settings.strict_data_plane:
        payload["strict_data_plane"] = True
    return payload


@app.get("/health/ready")
def health_ready():
    """Readiness: Postgres `SELECT 1`, Redis `PING`, Storage bucket list. HTTP 503 if any configured service fails.

    Use `/health/live` for liveness (no external calls). See `app/db/connect_params.py` for probe timeouts.
    """
    body, ok = readiness_report()
    code = 200 if ok else 503
    return JSONResponse(content=body, status_code=code)
