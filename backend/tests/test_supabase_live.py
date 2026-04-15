"""Live Supabase Postgres + Storage checks (skipped when .env incomplete).

Mapping: docs/FIREBASE_DATA_PLANE_MAPPING.md §2–§3.
Reads secrets only from backend/.env via dotenv_values — not affected by tests/conftest.py.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from dotenv import dotenv_values


def _backend_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _env() -> dict[str, str | None]:
    p = _backend_root() / ".env"
    return dotenv_values(p) if p.is_file() else {}


def _db_url() -> str | None:
    v = _env()
    raw = v.get("SUPABASE_DATABASE_URL") or v.get("DATABASE_URL")
    if not raw:
        return None
    s = str(raw).strip().strip('"').strip("'")
    return s or None


def _storage_config() -> tuple[str, str] | None:
    v = _env()
    base = (v.get("SUPABASE_PROJECT_URL") or v.get("SUPABASE_URL") or "").strip().strip('"').strip("'")
    key = (v.get("SUPABASE_SERVICE_KEY") or "").strip().strip('"').strip("'")
    if not base or not key:
        return None
    return base.rstrip("/"), key


@pytest.fixture
def db_url() -> str:
    u = _db_url()
    if not u:
        pytest.skip("Set SUPABASE_DATABASE_URL or DATABASE_URL in backend/.env")
    return u


@pytest.fixture
def storage_pair() -> tuple[str, str]:
    p = _storage_config()
    if not p:
        pytest.skip("Set SUPABASE_PROJECT_URL / SUPABASE_URL and SUPABASE_SERVICE_KEY in backend/.env")
    return p


def test_supabase_postgres_ping(db_url: str) -> None:
    import psycopg

    try:
        with psycopg.connect(db_url, connect_timeout=25, prepare_threshold=None) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                assert cur.fetchone()[0] == 1
    except psycopg.OperationalError as exc:
        pytest.skip(f"Live Supabase unreachable from this environment: {exc}")


def test_supabase_persistence_tables_exist(db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Tenant-scoped migrations create normalized domain tables + bot_* store."""
    import psycopg

    from app.config import settings
    from app.db.migrate import run_migrations
    from app.bastionbot.pg_store import PostgresBastionBotStore

    monkeypatch.setattr(settings, "database_url", db_url)
    try:
        run_migrations()
        PostgresBastionBotStore(db_url).initialize()
        with psycopg.connect(db_url, connect_timeout=25, prepare_threshold=None) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT to_regclass('public.tenants')")
                assert cur.fetchone()[0] is not None
                cur.execute("SELECT to_regclass('public.memberships')")
                assert cur.fetchone()[0] is not None
                cur.execute("SELECT to_regclass('public.alerts')")
                assert cur.fetchone()[0] is not None
                cur.execute("SELECT to_regclass('public.audit_log')")
                assert cur.fetchone()[0] is not None
                cur.execute("SELECT to_regclass('public.bot_conversations')")
                assert cur.fetchone()[0] is not None
    except psycopg.OperationalError as exc:
        pytest.skip(f"Live Supabase unreachable from this environment: {exc}")


def test_supabase_storage_buckets(storage_pair: tuple[str, str]) -> None:
    base, key = storage_pair
    try:
        with httpx.Client(timeout=30.0) as c:
            r = c.get(
                f"{base}/storage/v1/bucket",
                headers={"Authorization": f"Bearer {key}", "apikey": key},
            )
            r.raise_for_status()
            rows = r.json()
    except httpx.HTTPError as exc:
        pytest.skip(f"Live Supabase Storage unreachable from this environment: {exc}")
    names = {b["name"] for b in rows if isinstance(b, dict) and "name" in b}
    assert "forensics" in names, "Create private bucket `forensics` (mapping §3)"
    assert "models" in names, "Create private bucket `models` (mapping §3)"


def test_supabase_storage_signed_url(storage_pair: tuple[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import settings
    from app.services.supabase_storage import (
        create_signed_download_url,
        parse_bucket_and_object,
        upload_forensics_bytes,
    )

    monkeypatch.setattr(settings, "supabase_url", storage_pair[0])
    monkeypatch.setattr(settings, "supabase_service_key", storage_pair[1])
    name = "pytest_signed_url_probe.bin"
    try:
        path = upload_forensics_bytes(data=b"\x00probe", object_name=name)
    except Exception as exc:
        pytest.skip(f"Live Supabase Storage unreachable from this environment: {exc}")
    if not path:
        pytest.skip("Live Supabase Storage probe could not upload from this environment")
    parsed = parse_bucket_and_object(path)
    assert parsed is not None
    bucket, object_key = parsed
    assert bucket == "forensics"
    signed = create_signed_download_url(bucket=bucket, object_key=object_key, expires_in=120)
    assert signed and signed.startswith("http")
