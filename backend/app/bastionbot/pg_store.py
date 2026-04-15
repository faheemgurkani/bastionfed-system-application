"""BastionBot store backed by Supabase Postgres."""

from __future__ import annotations

import json
import threading
from typing import Any
from uuid import uuid4

import psycopg

from app.db.connect_params import pg_app_connect_kwargs
from app.models.domain import BotMessage, ConversationSummary, SourceCitation
from app.bastionbot.storage import BotUserMemory

_PG_CONNECT_KW = pg_app_connect_kwargs(application_name="bastionfed_bastionbot")


class PostgresBastionBotStore:
    def __init__(self, database_url: str) -> None:
        self._url = database_url
        self._lock = threading.Lock()

    def configure(self, database_url: str) -> None:
        self._url = database_url

    def initialize(self) -> None:
        statements = [
            """
            CREATE TABLE IF NOT EXISTS bot_conversations (
                id TEXT PRIMARY KEY,
                tenant_id TEXT,
                uid TEXT NOT NULL,
                title TEXT NOT NULL,
                preview TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS bot_messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL REFERENCES bot_conversations(id) ON DELETE CASCADE,
                tenant_id TEXT,
                uid TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                sources_json TEXT NOT NULL DEFAULT '[]',
                context_json TEXT NOT NULL DEFAULT '{}'
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS bot_user_memory (
                tenant_id TEXT,
                uid TEXT NOT NULL,
                last_active_conversation_id TEXT,
                recent_topics_json TEXT NOT NULL DEFAULT '[]',
                preferred_answer_style TEXT NOT NULL DEFAULT 'concise',
                updated_at TEXT NOT NULL
            )
            """,
            "ALTER TABLE bot_conversations ADD COLUMN IF NOT EXISTS tenant_id TEXT",
            "ALTER TABLE bot_messages ADD COLUMN IF NOT EXISTS tenant_id TEXT",
            "ALTER TABLE bot_user_memory ADD COLUMN IF NOT EXISTS tenant_id TEXT",
            "UPDATE bot_conversations SET tenant_id = COALESCE(NULLIF(tenant_id, ''), 'tenant-demo')",
            "UPDATE bot_messages SET tenant_id = COALESCE(NULLIF(tenant_id, ''), 'tenant-demo')",
            "UPDATE bot_user_memory SET tenant_id = COALESCE(NULLIF(tenant_id, ''), 'tenant-demo')",
            "CREATE INDEX IF NOT EXISTS idx_bot_conversations_uid_updated_at ON bot_conversations (tenant_id, uid, updated_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_bot_messages_conversation_created_at ON bot_messages (tenant_id, conversation_id, created_at ASC)",
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_bot_user_memory_tenant_uid ON bot_user_memory (tenant_id, uid)",
        ]
        with psycopg.connect(self._url, **_PG_CONNECT_KW) as conn:
            with conn.cursor() as cur:
                for statement in statements:
                    cur.execute(statement)
            conn.commit()

    def list_conversations(self, tenant_id: str, uid: str) -> list[ConversationSummary]:
        with self._lock, psycopg.connect(self._url, **_PG_CONNECT_KW) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT c.id, c.title, c.preview, c.created_at, c.updated_at,
                           (SELECT COUNT(*)::int FROM bot_messages m WHERE m.tenant_id = c.tenant_id AND m.conversation_id = c.id) AS message_count
                    FROM bot_conversations c
                    WHERE c.tenant_id = %s AND c.uid = %s
                    ORDER BY c.updated_at DESC, c.created_at DESC
                    """,
                    (tenant_id, uid),
                )
                rows = cur.fetchall()
        return [self._row_to_conversation(r) for r in rows]

    def get_conversation(self, tenant_id: str, uid: str, conversation_id: str) -> ConversationSummary | None:
        with self._lock, psycopg.connect(self._url, **_PG_CONNECT_KW) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT c.id, c.title, c.preview, c.created_at, c.updated_at,
                           (SELECT COUNT(*)::int FROM bot_messages m WHERE m.tenant_id = c.tenant_id AND m.conversation_id = c.id) AS message_count
                    FROM bot_conversations c
                    WHERE c.tenant_id = %s AND c.uid = %s AND c.id = %s
                    """,
                    (tenant_id, uid, conversation_id),
                )
                row = cur.fetchone()
        return self._row_to_conversation(row) if row else None

    def get_conversation_history(self, tenant_id: str, uid: str, conversation_id: str) -> list[BotMessage] | None:
        if self.get_conversation(tenant_id, uid, conversation_id) is None:
            return None
        with self._lock, psycopg.connect(self._url, **_PG_CONNECT_KW) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, role, content, created_at, sources_json
                    FROM bot_messages
                    WHERE tenant_id = %s AND uid = %s AND conversation_id = %s
                    ORDER BY created_at ASC
                    """,
                    (tenant_id, uid, conversation_id),
                )
                rows = cur.fetchall()
        return [self._row_to_message(r) for r in rows]

    def create_conversation(
        self,
        *,
        tenant_id: str,
        uid: str,
        title: str,
        preview: str,
        now_iso: str,
        conversation_id: str | None = None,
    ) -> ConversationSummary:
        conv_id = conversation_id or f"conv_{uuid4().hex}"
        with self._lock, psycopg.connect(self._url, **_PG_CONNECT_KW) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO bot_conversations (id, tenant_id, uid, title, preview, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (conv_id, tenant_id, uid, title, preview, now_iso, now_iso),
                )
            conn.commit()
        return self.get_conversation(tenant_id, uid, conv_id)  # type: ignore[return-value]

    def append_message(
        self,
        *,
        tenant_id: str,
        uid: str,
        conversation_id: str,
        role: str,
        content: str,
        now_iso: str,
        sources: list[SourceCitation] | None = None,
        context: dict[str, Any] | None = None,
        title: str | None = None,
        preview: str | None = None,
    ) -> BotMessage:
        msg_id = f"msg_{uuid4().hex}"
        serialized_sources = json.dumps([s.model_dump(by_alias=True) for s in (sources or [])])
        serialized_context = json.dumps(context or {})
        preview_value = (preview or content).strip()[:140]

        with self._lock, psycopg.connect(self._url, **_PG_CONNECT_KW) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO bot_messages
                        (id, conversation_id, tenant_id, uid, role, content, created_at, sources_json, context_json)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (msg_id, conversation_id, tenant_id, uid, role, content, now_iso, serialized_sources, serialized_context),
                )
                cur.execute(
                    "SELECT title FROM bot_conversations WHERE tenant_id = %s AND id = %s AND uid = %s",
                    (tenant_id, conversation_id, uid),
                )
                row = cur.fetchone()
                if row is None:
                    raise ValueError(f"Conversation {conversation_id} not found for tenant_id={tenant_id} uid={uid}")
                next_title = row[0]
                if title and (not next_title or next_title.lower().startswith("new conversation")):
                    next_title = title
                cur.execute(
                    """
                    UPDATE bot_conversations
                    SET title = %s, preview = %s, updated_at = %s
                    WHERE tenant_id = %s AND id = %s AND uid = %s
                    """,
                    (next_title, preview_value, now_iso, tenant_id, conversation_id, uid),
                )
            conn.commit()

        return BotMessage(
            id=msg_id,
            role=role,
            content=content,
            timestamp=now_iso,
            sources=sources or [],
        )

    def get_user_memory(self, tenant_id: str, uid: str) -> BotUserMemory | None:
        with self._lock, psycopg.connect(self._url, **_PG_CONNECT_KW) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT tenant_id, uid, last_active_conversation_id, recent_topics_json, preferred_answer_style, updated_at
                    FROM bot_user_memory
                    WHERE tenant_id = %s AND uid = %s
                    """,
                    (tenant_id, uid),
                )
                row = cur.fetchone()
        if row is None:
            return None
        return BotUserMemory(
            tenant_id=row[0],
            uid=row[1],
            last_active_conversation_id=row[2],
            recent_topics=json.loads(row[3] or "[]"),
            preferred_answer_style=row[4],
            updated_at=row[5],
        )

    def upsert_user_memory(
        self,
        *,
        tenant_id: str,
        uid: str,
        last_active_conversation_id: str | None,
        recent_topics: list[str],
        preferred_answer_style: str,
        now_iso: str,
    ) -> BotUserMemory:
        payload = json.dumps(recent_topics[:10])
        with self._lock, psycopg.connect(self._url, **_PG_CONNECT_KW) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO bot_user_memory
                        (tenant_id, uid, last_active_conversation_id, recent_topics_json, preferred_answer_style, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (tenant_id, uid) DO UPDATE SET
                        last_active_conversation_id = EXCLUDED.last_active_conversation_id,
                        recent_topics_json = EXCLUDED.recent_topics_json,
                        preferred_answer_style = EXCLUDED.preferred_answer_style,
                        updated_at = EXCLUDED.updated_at
                    """,
                    (tenant_id, uid, last_active_conversation_id, payload, preferred_answer_style, now_iso),
                )
            conn.commit()
        return self.get_user_memory(tenant_id, uid)  # type: ignore[return-value]

    def _row_to_conversation(self, row: tuple[Any, ...]) -> ConversationSummary:
        return ConversationSummary(
            id=row[0],
            title=row[1],
            preview=row[2],
            created_at=row[3],
            updated_at=row[4],
            message_count=int(row[5]),
        )

    def _row_to_message(self, row: tuple[Any, ...]) -> BotMessage:
        raw_sources = json.loads(row[4] or "[]")
        return BotMessage(
            id=row[0],
            role=row[1],
            content=row[2],
            timestamp=row[3],
            sources=[SourceCitation.model_validate(source) for source in raw_sources],
        )
