"""Legacy bf_bundle persistence helpers kept only for historical reference.

The unified runtime no longer uses this module. Active persistence now lives in
`app/db/migrate.py`, `app/store/tenant_store.py`, and `app/bastionbot/pg_store.py`.
Do not wire new code to `bf_bundle`.
"""

from __future__ import annotations

import json
import logging
import psycopg
from psycopg.types.json import Json

from app.config import settings
from app.store.memory import export_app_snapshot, import_app_snapshot, state

logger = logging.getLogger(__name__)

_BUNDLE_ID = 1


def _connect():
    if not settings.persistence_enabled or not settings.database_url:
        raise RuntimeError("DATABASE_URL / Supabase URL not configured")
    # Transaction pooler (port 6543) does not support prepared statements like direct Postgres.
    return psycopg.connect(
        settings.database_url,
        connect_timeout=15,
        prepare_threshold=None,
    )


def init_schema() -> None:
    """Create bf_bundle and BastionBot tables if missing."""
    ddl = """
    CREATE TABLE IF NOT EXISTS bf_bundle (
        id SMALLINT PRIMARY KEY CHECK (id = 1),
        payload JSONB NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS bot_conversations (
        id TEXT PRIMARY KEY,
        uid TEXT NOT NULL,
        title TEXT NOT NULL,
        preview TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_bot_conversations_uid_updated_at
        ON bot_conversations (uid, updated_at DESC);

    CREATE TABLE IF NOT EXISTS bot_messages (
        id TEXT PRIMARY KEY,
        conversation_id TEXT NOT NULL REFERENCES bot_conversations(id) ON DELETE CASCADE,
        uid TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TEXT NOT NULL,
        sources_json TEXT NOT NULL DEFAULT '[]',
        context_json TEXT NOT NULL DEFAULT '{}'
    );
    CREATE INDEX IF NOT EXISTS idx_bot_messages_conversation_created_at
        ON bot_messages (conversation_id, created_at ASC);

    CREATE TABLE IF NOT EXISTS bot_user_memory (
        uid TEXT PRIMARY KEY,
        last_active_conversation_id TEXT,
        recent_topics_json TEXT NOT NULL DEFAULT '[]',
        preferred_answer_style TEXT NOT NULL DEFAULT 'concise',
        updated_at TEXT NOT NULL
    );
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(ddl)
        conn.commit()
    logger.info("Postgres schema ensured (bf_bundle + bot_*).")


def load_bundle_into_state() -> bool:
    """
    Load bf_bundle into module `state`. Returns True if a snapshot existed.
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT payload FROM bf_bundle WHERE id = %s", (_BUNDLE_ID,))
            row = cur.fetchone()
    if not row or row[0] is None:
        return False
    payload = row[0]
    if isinstance(payload, str):
        data = json.loads(payload)
    else:
        data = payload
    import_app_snapshot(state, data)
    logger.info("Loaded AppState from bf_bundle.")
    return True


def save_bundle_from_state() -> None:
    snap = export_app_snapshot(state)
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO bf_bundle (id, payload)
                VALUES (%s, %s::jsonb)
                ON CONFLICT (id) DO UPDATE SET
                    payload = EXCLUDED.payload,
                    updated_at = NOW()
                """,
                (_BUNDLE_ID, Json(snap)),
            )
        conn.commit()


def bootstrap_state_if_needed() -> None:
    """
    If DATABASE_URL is set: ensure schema, load bundle or seed + persist.
    Mutates module-level `state`.
    """
    if not settings.persistence_enabled:
        return
    try:
        init_schema()
    except Exception as exc:
        logger.exception("Postgres init_schema failed: %s", exc)
        return
    try:
        if load_bundle_into_state():
            return
    except Exception as exc:
        logger.exception("Postgres load failed; re-seeding: %s", exc)
    state.reset()
    try:
        save_bundle_from_state()
        logger.info("Seeded initial bf_bundle.")
    except Exception as exc:
        logger.exception("Postgres seed save failed: %s", exc)


def persist_state_snapshot() -> None:
    if not settings.persistence_enabled:
        return
    try:
        save_bundle_from_state()
    except Exception as exc:
        logger.warning("bf_bundle save failed: %s", exc)
