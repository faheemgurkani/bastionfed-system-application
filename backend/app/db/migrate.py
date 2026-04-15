from __future__ import annotations

from pathlib import Path

import psycopg

from app.config import settings
from app.db.connect_params import pg_app_connect_kwargs


def _connect():
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL / SUPABASE_DATABASE_URL not configured")
    return psycopg.connect(settings.database_url, **pg_app_connect_kwargs(application_name="bastionfed_migrate"))


def migration_dir() -> Path:
    return Path(__file__).resolve().parent / "migrations"


def run_migrations() -> None:
    files = sorted(path for path in migration_dir().glob("*.sql") if path.is_file())
    if not files:
        return
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version TEXT PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            for path in files:
                version = path.name
                cur.execute("SELECT 1 FROM schema_migrations WHERE version = %s", (version,))
                if cur.fetchone():
                    continue
                cur.execute(path.read_text())
                cur.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (version,))
        conn.commit()
