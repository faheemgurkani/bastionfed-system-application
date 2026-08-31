from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from app.models.domain import SourceCitation

STOPWORDS = {
    "the",
    "and",
    "for",
    "that",
    "with",
    "this",
    "from",
    "into",
    "what",
    "when",
    "where",
    "your",
    "about",
    "have",
    "does",
    "how",
    "can",
    "use",
    "show",
    "tell",
    "give",
    "please",
    "help",
    "mode",
    "read",
    "only",
}


@dataclass
class KnowledgeEntry:
    id: str
    label: str
    source_type: str
    path: str
    text: str
    excerpt: str
    keywords: set[str]


def _tokenize(text: str) -> list[str]:
    return [tok for tok in re.findall(r"[a-z0-9]+", text.lower()) if len(tok) > 2 and tok not in STOPWORDS]


def _compact(text: str, limit: int = 260) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"


class KnowledgeRegistry:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self.entries: list[KnowledgeEntry] = []

    def reload(self) -> None:
        self.entries = []
        for rel_path in self._doc_paths():
            self.entries.extend(self._load_markdown_sections(rel_path))
        self.entries.extend(self._metadata_entries())

    def search(self, query: str, limit: int = 4, boosts: list[str] | None = None) -> list[KnowledgeEntry]:
        query_tokens = set(_tokenize(query))
        boost_tokens = set(_tokenize(" ".join(boosts or [])))
        scored: list[tuple[int, KnowledgeEntry]] = []
        for entry in self.entries:
            overlap = len(query_tokens & entry.keywords)
            if overlap == 0 and not (boost_tokens & entry.keywords):
                continue
            boost = len(boost_tokens & entry.keywords)
            label_bonus = sum(1 for token in query_tokens if token in entry.label.lower())
            source_bonus = 1 if entry.source_type in ("ui", "api") else 0
            scored.append((overlap * 4 + boost * 2 + label_bonus + source_bonus, entry))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [entry for _, entry in scored[:limit]]

    def to_citation(self, entry: KnowledgeEntry, ordinal: int) -> SourceCitation:
        return SourceCitation(
            id=f"src_{ordinal}",
            label=entry.label,
            source_type=entry.source_type,
            path=entry.path,
            excerpt=entry.excerpt,
        )

    def _doc_paths(self) -> list[str]:
        return [
            "README.md",
            "SETUP_GUIDE.md",
            "CONTRIBUTING.md",
            "SECURITY.md",
            "CODE_OF_CONDUCT.md",
            "CHANGELOG.md",
            "docs/README.md",
            "docs/LOCAL_TESTING.md",
            "docs/BACKEND_PRD.md",
            "docs/API_ENDPOINTS_IMPLEMENTATION_SPLIT.md",
            "docs/TODO.md",
            "docs/BASTIONBOT_ASK_MODE.md",
            "docs/FAHEEM/FAHEEM_BACKEND_IMPLEMENTATION.md",
            "docs/FAHEEM/FAHEEM_BACKEND_TODO.md",
            "backend/README.md",
            "frontend/README.md",
        ]

    def _load_markdown_sections(self, rel_path: str) -> list[KnowledgeEntry]:
        path = self.repo_root / rel_path
        if not path.exists():
            return []
        text = path.read_text(encoding="utf-8", errors="ignore")
        sections: list[tuple[str, str]] = []
        current_heading = path.name
        buffer: list[str] = []

        for line in text.splitlines():
            if line.startswith("#"):
                if buffer:
                    sections.append((current_heading, "\n".join(buffer).strip()))
                    buffer = []
                current_heading = line.lstrip("#").strip() or path.name
            else:
                buffer.append(line)
        if buffer:
            sections.append((current_heading, "\n".join(buffer).strip()))

        entries: list[KnowledgeEntry] = []
        for idx, (heading, body) in enumerate(sections, start=1):
            if len(body.strip()) < 40:
                continue
            excerpt = _compact(body)
            keywords = set(_tokenize(" ".join([heading, rel_path, body[:1200]])))
            entries.append(
                KnowledgeEntry(
                    id=f"{rel_path}:{idx}",
                    label=f"{heading} ({rel_path})",
                    source_type="doc",
                    path=rel_path,
                    text=body,
                    excerpt=excerpt,
                    keywords=keywords,
                )
            )
        return entries

    def _metadata_entries(self) -> list[KnowledgeEntry]:
        items = [
            (
                "screen_dashboard",
                "Dashboard / Threat Map",
                "ui",
                "frontend/app/dashboard",
                "The Dashboard shows KPI cards, live threat posture, active threats, open incidents, and FL round status. It is backed by GET /api/dashboard/kpis and the alerts context.",
            ),
            (
                "screen_alerts",
                "Alerts screen and triage flow",
                "ui",
                "frontend/app/alerts + frontend/components/alerts",
                "The Alerts page uses GET /api/alerts and the /api/events SSE stream. Signed-in analysts can PATCH alert status and quarantine devices; guests can view but not mutate.",
            ),
            (
                "screen_fl_health",
                "FL Health screen",
                "ui",
                "frontend/app/fl-health + frontend/components/fl-health",
                "FL Health combines GET /api/fl/status, GET /api/fl/clients, GET /api/fl/clients/{id}, and GET /api/fl-events to show current federated learning status and client participation updates.",
            ),
            (
                "screen_incidents",
                "Incidents workflow",
                "ui",
                "frontend/app/incidents + frontend/components/incidents",
                "Incidents uses GET /api/incidents for the board and incident detail APIs for deep inspection. Playbook actions are separate mutation endpoints owned by the unified backend.",
            ),
            (
                "screen_forensics",
                "Forensics screen",
                "ui",
                "frontend/app/forensics",
                "Forensics surfaces malware samples, RCA reports, and investigation details from the backend. It is used for malware analysis, RCA review, and analyst context-building.",
            ),
            (
                "screen_audit",
                "Audit screen",
                "ui",
                "frontend/app/audit",
                "Audit uses GET /api/audit/logs for the log table and GET /api/audit/verify for the tamper-evident chain check. Verify is non-mutating and intended as a trust validation workflow.",
            ),
            (
                "api_audit_verify",
                "Audit verification endpoint",
                "api",
                "/api/audit/verify",
                "GET /api/audit/verify checks the tamper-evident audit hash chain and returns whether the log sequence is valid, plus the checked timestamp and failure point if integrity breaks.",
            ),
            (
                "screen_bastionbot",
                "BastionBot Ask Mode",
                "ui",
                "frontend/app/bastionbot",
                "BastionBot is a signed-in analyst assistant for product help, implementation guidance, and live platform questions. In this milestone it is read-only and must not trigger mutations.",
            ),
            (
                "api_bastionbot",
                "BastionBot API contract",
                "api",
                "/api/bastionbot/*",
                "BastionBot exposes list conversations, get conversation history, and chat. Chat may create a new conversation when conversationId is omitted and returns sources plus memoryUsed metadata.",
            ),
        ]
        entries: list[KnowledgeEntry] = []
        for item_id, label, source_type, path, text in items:
            entries.append(
                KnowledgeEntry(
                    id=item_id,
                    label=label,
                    source_type=source_type,
                    path=path,
                    text=text,
                    excerpt=_compact(text),
                    keywords=set(_tokenize(" ".join([label, path, text]))),
                )
            )
        return entries
