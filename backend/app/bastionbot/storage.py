from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Union
from uuid import uuid4

from app.models.domain import BotMessage, ConversationSummary, SourceCitation


@dataclass
class BotUserMemory:
    tenant_id: str
    uid: str
    last_active_conversation_id: str | None
    recent_topics: list[str]
    preferred_answer_style: str
    updated_at: str


class BastionBotStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = Path(db_path)
        self._lock = threading.Lock()

    def configure(self, db_path: str) -> None:
        self.db_path = Path(db_path)
        self.initialize()

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS bot_conversations (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    uid TEXT NOT NULL,
                    title TEXT NOT NULL,
                    preview TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS bot_messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    uid TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    sources_json TEXT NOT NULL DEFAULT '[]',
                    context_json TEXT NOT NULL DEFAULT '{}',
                    FOREIGN KEY (conversation_id) REFERENCES bot_conversations(id)
                );

                CREATE TABLE IF NOT EXISTS bot_user_memory (
                    tenant_id TEXT NOT NULL,
                    uid TEXT NOT NULL,
                    last_active_conversation_id TEXT,
                    recent_topics_json TEXT NOT NULL DEFAULT '[]',
                    preferred_answer_style TEXT NOT NULL DEFAULT 'concise',
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, uid)
                );

                CREATE INDEX IF NOT EXISTS idx_bot_conversations_uid_updated_at
                    ON bot_conversations(tenant_id, uid, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_bot_messages_conversation_created_at
                    ON bot_messages(tenant_id, conversation_id, created_at ASC);
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def list_conversations(self, tenant_id: str, uid: str) -> list[ConversationSummary]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT c.id, c.title, c.preview, c.created_at, c.updated_at,
                       (SELECT COUNT(*) FROM bot_messages m WHERE m.tenant_id = c.tenant_id AND m.conversation_id = c.id) AS message_count
                FROM bot_conversations c
                WHERE c.tenant_id = ? AND c.uid = ?
                ORDER BY c.updated_at DESC, c.created_at DESC
                """,
                (tenant_id, uid),
            ).fetchall()
        return [self._row_to_conversation(row) for row in rows]

    def get_conversation(self, tenant_id: str, uid: str, conversation_id: str) -> ConversationSummary | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT c.id, c.title, c.preview, c.created_at, c.updated_at,
                       (SELECT COUNT(*) FROM bot_messages m WHERE m.tenant_id = c.tenant_id AND m.conversation_id = c.id) AS message_count
                FROM bot_conversations c
                WHERE c.tenant_id = ? AND c.uid = ? AND c.id = ?
                """,
                (tenant_id, uid, conversation_id),
            ).fetchone()
        return self._row_to_conversation(row) if row else None

    def get_conversation_history(self, tenant_id: str, uid: str, conversation_id: str) -> list[BotMessage] | None:
        if self.get_conversation(tenant_id, uid, conversation_id) is None:
            return None
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, role, content, created_at, sources_json
                FROM bot_messages
                WHERE tenant_id = ? AND uid = ? AND conversation_id = ?
                ORDER BY created_at ASC, rowid ASC
                """,
                (tenant_id, uid, conversation_id),
            ).fetchall()
        return [self._row_to_message(row) for row in rows]

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
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO bot_conversations (id, tenant_id, uid, title, preview, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
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

        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO bot_messages
                    (id, conversation_id, tenant_id, uid, role, content, created_at, sources_json, context_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (msg_id, conversation_id, tenant_id, uid, role, content, now_iso, serialized_sources, serialized_context),
            )
            current = conn.execute(
                "SELECT title FROM bot_conversations WHERE tenant_id = ? AND id = ? AND uid = ?",
                (tenant_id, conversation_id, uid),
            ).fetchone()
            if current is None:
                raise ValueError(f"Conversation {conversation_id} not found for tenant_id={tenant_id} uid={uid}")

            next_title = current["title"]
            if title and (not next_title or next_title.lower().startswith("new conversation")):
                next_title = title

            conn.execute(
                """
                UPDATE bot_conversations
                SET title = ?, preview = ?, updated_at = ?
                WHERE tenant_id = ? AND id = ? AND uid = ?
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
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT tenant_id, uid, last_active_conversation_id, recent_topics_json, preferred_answer_style, updated_at
                FROM bot_user_memory
                WHERE tenant_id = ? AND uid = ?
                """,
                (tenant_id, uid),
            ).fetchone()
        if row is None:
            return None
        return BotUserMemory(
            tenant_id=row["tenant_id"],
            uid=row["uid"],
            last_active_conversation_id=row["last_active_conversation_id"],
            recent_topics=json.loads(row["recent_topics_json"] or "[]"),
            preferred_answer_style=row["preferred_answer_style"],
            updated_at=row["updated_at"],
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
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO bot_user_memory
                    (tenant_id, uid, last_active_conversation_id, recent_topics_json, preferred_answer_style, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(tenant_id, uid) DO UPDATE SET
                    last_active_conversation_id = excluded.last_active_conversation_id,
                    recent_topics_json = excluded.recent_topics_json,
                    preferred_answer_style = excluded.preferred_answer_style,
                    updated_at = excluded.updated_at
                """,
                (tenant_id, uid, last_active_conversation_id, payload, preferred_answer_style, now_iso),
            )
            conn.commit()
        return self.get_user_memory(tenant_id, uid)  # type: ignore[return-value]

    def _row_to_conversation(self, row: sqlite3.Row) -> ConversationSummary:
        return ConversationSummary(
            id=row["id"],
            title=row["title"],
            preview=row["preview"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            message_count=int(row["message_count"]),
        )

    def _row_to_message(self, row: sqlite3.Row) -> BotMessage:
        raw_sources = json.loads(row["sources_json"] or "[]")
        return BotMessage(
            id=row["id"],
            role=row["role"],
            content=row["content"],
            timestamp=row["created_at"],
            sources=[SourceCitation.model_validate(source) for source in raw_sources],
        )


_impl: Union[BastionBotStore, Any] = BastionBotStore("data/runtime/bastionbot.sqlite3")


class _BastionBotStoreProxy:
    """Delegates to the active store (SQLite or Postgres) after `set_bastionbot_store`."""

    def __getattr__(self, name: str):
        return getattr(_impl, name)


bastionbot_store = _BastionBotStoreProxy()


def set_bastionbot_store(store: Any) -> None:
    global _impl
    _impl = store
