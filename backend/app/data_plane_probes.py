"""Live probes for Postgres, Redis, and Supabase Storage (readiness / strict startup)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx
import redis as redis_sync

from app.config import settings
from app.db.connect_params import pg_probe_connect_kwargs

logger = logging.getLogger(__name__)

# Bounded so strict-mode startup / readiness never hangs on a single stuck network call.
_REDIS_SOCKET_CONNECT_S = 5
_REDIS_SOCKET_S = 5
_STORAGE_HTTP_S = 10.0


def probe_postgres() -> dict[str, Any]:
    if not settings.persistence_enabled:
        return {"configured": False, "ok": None, "detail": "DATABASE_URL not set"}
    try:
        import psycopg

        with psycopg.connect(settings.database_url or "", **pg_probe_connect_kwargs()) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        return {"configured": True, "ok": True}
    except Exception as exc:
        logger.warning("Postgres probe failed: %s", exc)
        return {"configured": True, "ok": False, "detail": str(exc)[:300]}


def probe_redis() -> dict[str, Any]:
    if not settings.redis_enabled:
        return {"configured": False, "ok": None, "detail": "REDIS_URL not set"}
    try:
        client = redis_sync.from_url(
            settings.redis_url or "",
            decode_responses=True,
            socket_connect_timeout=_REDIS_SOCKET_CONNECT_S,
            socket_timeout=_REDIS_SOCKET_S,
        )
        try:
            client.ping()
            return {"configured": True, "ok": True}
        finally:
            client.close()
    except Exception as exc:
        logger.warning("Redis probe failed: %s", exc)
        return {"configured": True, "ok": False, "detail": str(exc)[:300]}


def probe_storage_buckets() -> dict[str, Any]:
    if not settings.supabase_storage_enabled:
        return {"configured": False, "ok": None, "detail": "SUPABASE_URL / SUPABASE_SERVICE_KEY not set"}
    base = (settings.supabase_url or "").rstrip("/")
    key = settings.supabase_service_key or ""
    try:
        with httpx.Client(timeout=_STORAGE_HTTP_S) as c:
            r = c.get(
                f"{base}/storage/v1/bucket",
                headers={"Authorization": f"Bearer {key}", "apikey": key},
            )
            r.raise_for_status()
            rows = r.json()
        names = {b["name"] for b in rows if isinstance(b, dict) and "name" in b}
        need = {settings.supabase_forensics_bucket, settings.supabase_models_bucket}
        missing = sorted(need - names)
        art = getattr(settings, "supabase_artifacts_bucket", "images")
        optional_missing = sorted({art} - names) if art else []
        if missing:
            return {
                "configured": True,
                "ok": False,
                "detail": f"Missing buckets: {missing}",
                "buckets_found": sorted(names),
                "optional_artifacts_bucket": art,
                "optional_buckets_missing": optional_missing,
            }
        out: dict[str, Any] = {
            "configured": True,
            "ok": True,
            "buckets_found": sorted(names),
            "optional_artifacts_bucket": art,
        }
        if optional_missing:
            out["optional_buckets_missing"] = optional_missing
            out["detail"] = (
                f"Required buckets OK. Create optional bucket `{art}` for client PNG/JSON artifacts: missing."
            )
        return out
    except Exception as exc:
        logger.warning("Storage probe failed: %s", exc)
        return {"configured": True, "ok": False, "detail": str(exc)[:300]}


def readiness_report() -> tuple[dict[str, Any], bool]:
    """
    Build readiness JSON. `all_ok` is True iff every *configured* service passed
    (unconfigured services are ignored).
    """
    checked_at = datetime.now(timezone.utc).isoformat()
    logger.info("readiness: probe Postgres …")
    pg = probe_postgres()
    logger.info("readiness: probe Redis …")
    rd = probe_redis()
    logger.info("readiness: probe Storage …")
    st = probe_storage_buckets()
    body: dict[str, Any] = {
        "checkedAt": checked_at,
        "postgres": pg,
        "redis": rd,
        "storage": st,
    }
    any_configured = any(bool(p.get("configured")) for p in (pg, rd, st))
    all_ok = True
    for probe in (pg, rd, st):
        if probe.get("configured") and probe.get("ok") is not True:
            all_ok = False
    if not any_configured:
        body["status"] = "demo"
        all_ok = True
    else:
        body["status"] = "ready" if all_ok else "degraded"
    return body, all_ok


def strict_env_misconfiguration_message() -> str | None:
    """If strict mode is on but an env var is missing, return a message; else None."""
    if not settings.strict_data_plane:
        return None
    missing: list[str] = []
    if not settings.persistence_enabled:
        missing.append("DATABASE_URL or SUPABASE_DATABASE_URL")
    if not settings.redis_enabled:
        missing.append("REDIS_URL or UPSTASH_REDIS_URL")
    if not settings.supabase_storage_enabled:
        missing.append("SUPABASE_URL (or SUPABASE_PROJECT_URL) and SUPABASE_SERVICE_KEY")
    if missing:
        return "BASTIONFED_STRICT_DATA_PLANE=1 requires: " + ", ".join(missing)
    return None


def require_readiness_ok_or_raise() -> None:
    """After Postgres bootstrap: fail startup if any configured service does not respond."""
    if not settings.strict_data_plane:
        return
    body, ok = readiness_report()
    if ok:
        return
    parts: list[str] = []
    for label, key in ("Postgres", "postgres"), ("Redis", "redis"), ("Storage", "storage"):
        p = body.get(key) or {}
        if p.get("configured") and p.get("ok") is not True:
            detail = str(p.get("detail") or "check failed")[:500]
            parts.append(f"{label}: {detail}")
    summary = "; ".join(parts) if parts else "one or more data-plane checks failed"
    raise RuntimeError(
        f"BASTIONFED_STRICT_DATA_PLANE=1: readiness failed — {summary}. "
        f"See GET /health/ready for JSON. Checked at {body.get('checkedAt', '')}."
    )
