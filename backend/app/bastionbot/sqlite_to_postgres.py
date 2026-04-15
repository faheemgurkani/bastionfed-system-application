"""One-way merge of legacy BastionBot SQLite into Supabase Postgres (tenant_id + uid scoped)."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import psycopg

from app.db.connect_params import pg_app_connect_kwargs

logger = logging.getLogger(__name__)
_PG = pg_app_connect_kwargs(application_name="bastionfed_bastionbot_import")


def _resolve_sqlite_path(sqlite_path: str | Path, *, backend_root: Path) -> Path:
    p = Path(sqlite_path)
    if p.is_absolute():
        return p
    return backend_root / p


def _sqlite_columns(lite: sqlite3.Connection, table: str) -> set[str]:
    allowed = ("bot_conversations", "bot_messages", "bot_user_memory")
    if table not in allowed:
        raise ValueError(f"unsupported table {table!r}")
    rows = lite.execute("PRAGMA table_info(" + table + ")").fetchall()
    return {str(r[1]) for r in rows}


def import_legacy_bastionbot_sqlite(
    sqlite_path: str | Path,
    database_url: str,
    *,
    backend_root: Path | None = None,
    legacy_default_tenant_id: str | None = None,
) -> dict[str, int]:
    """
    Copy rows from local BastionBot SQLite into Postgres when the file exists.
    Idempotent: conversations/messages use ON CONFLICT (id) DO NOTHING; memory merges by updated_at.
    """
    root = backend_root or Path(__file__).resolve().parents[2]
    src = _resolve_sqlite_path(sqlite_path, backend_root=root)
    stats: dict[str, int] = {
        "conversations": 0,
        "messages": 0,
        "memory": 0,
        "skipped_no_file": 0,
        "skipped_legacy_schema": 0,
    }

    if not src.exists():
        stats["skipped_no_file"] = 1
        return stats

    try:
        lite = sqlite3.connect(str(src))
        lite.row_factory = sqlite3.Row
    except OSError as exc:
        logger.warning("BastionBot SQLite import: cannot open %s: %s", src, exc)
        return stats

    try:
        ccols = _sqlite_columns(lite, "bot_conversations")
        mcols = _sqlite_columns(lite, "bot_messages")
        memcols = _sqlite_columns(lite, "bot_user_memory")

        conv_has_tenant = "tenant_id" in ccols
        msg_has_tenant = "tenant_id" in mcols
        mem_has_tenant = "tenant_id" in memcols

        if not conv_has_tenant or not msg_has_tenant or not mem_has_tenant:
            tid = (legacy_default_tenant_id or "").strip()
            if not tid:
                try:
                    with psycopg.connect(database_url, **_PG) as c2:
                        with c2.cursor() as c2r:
                            c2r.execute("SELECT id FROM tenants ORDER BY created_at ASC NULLS LAST LIMIT 2")
                            trows = c2r.fetchall()
                        if len(trows) == 1:
                            tid = str(trows[0][0])
                except Exception:
                    tid = ""
            if not tid:
                logger.warning(
                    "BastionBot SQLite at %s uses a legacy schema (missing tenant_id on some bot_* tables). "
                    "Set BASTIONBOT_IMPORT_LEGACY_DEFAULT_TENANT_ID or ensure exactly one row in tenants; skipping import.",
                    src,
                )
                stats["skipped_legacy_schema"] = 1
                return stats

            if conv_has_tenant:
                conv_rows = lite.execute(
                    "SELECT id, tenant_id, uid, title, preview, created_at, updated_at FROM bot_conversations"
                ).fetchall()
            else:
                conv_rows = lite.execute(
                    "SELECT id, uid, title, preview, created_at, updated_at FROM bot_conversations"
                ).fetchall()

            if msg_has_tenant:
                msg_rows = lite.execute(
                    "SELECT id, conversation_id, tenant_id, uid, role, content, created_at, sources_json, context_json FROM bot_messages"
                ).fetchall()
            else:
                msg_rows = lite.execute(
                    "SELECT id, conversation_id, uid, role, content, created_at, sources_json, context_json FROM bot_messages"
                ).fetchall()

            if mem_has_tenant:
                mem_rows = lite.execute(
                    "SELECT tenant_id, uid, last_active_conversation_id, recent_topics_json, preferred_answer_style, updated_at FROM bot_user_memory"
                ).fetchall()
            else:
                mem_rows = lite.execute(
                    "SELECT uid, last_active_conversation_id, recent_topics_json, preferred_answer_style, updated_at FROM bot_user_memory"
                ).fetchall()
        else:
            tid = ""
            conv_rows = lite.execute(
                "SELECT id, tenant_id, uid, title, preview, created_at, updated_at FROM bot_conversations"
            ).fetchall()
            msg_rows = lite.execute(
                "SELECT id, conversation_id, tenant_id, uid, role, content, created_at, sources_json, context_json FROM bot_messages"
            ).fetchall()
            mem_rows = lite.execute(
                "SELECT tenant_id, uid, last_active_conversation_id, recent_topics_json, preferred_answer_style, updated_at FROM bot_user_memory"
            ).fetchall()
    finally:
        lite.close()

    if not conv_rows and not msg_rows and not mem_rows:
        return stats

    def conv_tuple(r: sqlite3.Row) -> tuple:
        if conv_has_tenant:
            return (r["id"], r["tenant_id"], r["uid"], r["title"], r["preview"], r["created_at"], r["updated_at"])
        return (r["id"], tid, r["uid"], r["title"], r["preview"], r["created_at"], r["updated_at"])

    def msg_tuple(r: sqlite3.Row) -> tuple:
        if msg_has_tenant:
            return (
                r["id"],
                r["conversation_id"],
                r["tenant_id"],
                r["uid"],
                r["role"],
                r["content"],
                r["created_at"],
                r["sources_json"] or "[]",
                r["context_json"] or "{}",
            )
        return (
            r["id"],
            r["conversation_id"],
            tid,
            r["uid"],
            r["role"],
            r["content"],
            r["created_at"],
            r["sources_json"] or "[]",
            r["context_json"] or "{}",
        )

    def mem_tuple(r: sqlite3.Row) -> tuple:
        if mem_has_tenant:
            return (
                r["tenant_id"],
                r["uid"],
                r["last_active_conversation_id"],
                r["recent_topics_json"] or "[]",
                r["preferred_answer_style"],
                r["updated_at"],
            )
        return (
            tid,
            r["uid"],
            r["last_active_conversation_id"],
            r["recent_topics_json"] or "[]",
            r["preferred_answer_style"],
            r["updated_at"],
        )

    with psycopg.connect(database_url, **_PG) as conn:
        with conn.cursor() as cur:
            for r in conv_rows:
                cid, tenant_id, uid, title, preview, created_at, updated_at = conv_tuple(r)
                cur.execute(
                    """
                    INSERT INTO bot_conversations (id, tenant_id, uid, title, preview, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (cid, tenant_id, uid, title, preview, created_at, updated_at),
                )
                if cur.rowcount:
                    stats["conversations"] += 1

            for r in msg_rows:
                cur.execute(
                    """
                    INSERT INTO bot_messages
                        (id, conversation_id, tenant_id, uid, role, content, created_at, sources_json, context_json)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    msg_tuple(r),
                )
                if cur.rowcount:
                    stats["messages"] += 1

            for r in mem_rows:
                mt = mem_tuple(r)
                cur.execute(
                    """
                    INSERT INTO bot_user_memory
                        (tenant_id, uid, last_active_conversation_id, recent_topics_json, preferred_answer_style, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (tenant_id, uid) DO UPDATE SET
                        last_active_conversation_id = CASE
                            WHEN EXCLUDED.updated_at > bot_user_memory.updated_at
                            THEN EXCLUDED.last_active_conversation_id
                            ELSE bot_user_memory.last_active_conversation_id
                        END,
                        recent_topics_json = CASE
                            WHEN EXCLUDED.updated_at > bot_user_memory.updated_at
                            THEN EXCLUDED.recent_topics_json
                            ELSE bot_user_memory.recent_topics_json
                        END,
                        preferred_answer_style = CASE
                            WHEN EXCLUDED.updated_at > bot_user_memory.updated_at
                            THEN EXCLUDED.preferred_answer_style
                            ELSE bot_user_memory.preferred_answer_style
                        END,
                        updated_at = GREATEST(bot_user_memory.updated_at, EXCLUDED.updated_at)
                    """,
                    mt,
                )
                stats["memory"] += 1
        conn.commit()

    if stats["conversations"] or stats["messages"]:
        logger.info(
            "BastionBot SQLite → Postgres import from %s: +%s conversations, +%s messages, %s memory upserts",
            src,
            stats["conversations"],
            stats["messages"],
            stats["memory"],
        )
    elif stats["memory"]:
        logger.debug(
            "BastionBot SQLite import from %s: memory-only reconcile (%s rows)",
            src,
            stats["memory"],
        )
    return stats
