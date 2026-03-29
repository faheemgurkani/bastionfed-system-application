from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from app.bastionbot.knowledge import KnowledgeRegistry
from app.bastionbot.storage import BotUserMemory
from app.config import settings
from app.models.domain import Alert, BotChatContext, Device, Incident, SourceCitation
from app.store.memory import AppState
import httpx


@dataclass
class AskResult:
    answer: str
    sources: list[SourceCitation]
    topics: list[str]
    memory_used: bool


def _find_repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "SETUP_GUIDE.md").exists() and (parent / "frontend").exists():
            return parent
        if parent.name == "backend" and (parent.parent / "SETUP_GUIDE.md").exists():
            return parent.parent
    return current.parents[4]


class BastionBotEngine:
    def __init__(self, repo_root: Path) -> None:
        self.registry = KnowledgeRegistry(repo_root)

    def initialize(self) -> None:
        self.registry.reload()

    def answer(
        self,
        *,
        query: str,
        state: AppState,
        memory: BotUserMemory | None,
        history: list[str],
        context: BotChatContext | None = None,
    ) -> AskResult:
        classification = self._classify_query(query)
        context_terms = list(history[-2:]) if history else []
        if memory and memory.recent_topics:
            context_terms.extend(memory.recent_topics[:3])
        if context and context.alert_id:
            context_terms.append(context.alert_id)
        if context and context.incident_id:
            context_terms.append(context.incident_id)

        doc_entries = self.registry.search(query, limit=4, boosts=context_terms)
        live_citations, live_points = self._live_context(query=query, state=state, context=context)
        sources = live_citations + [self.registry.to_citation(entry, idx + len(live_citations) + 1) for idx, entry in enumerate(doc_entries)]
        memory_used = bool(history or (memory and memory.recent_topics))
        topics = self._derive_topics(query=query, classification=classification, sources=sources)

        if not sources and not live_points:
            return AskResult(
                answer=(
                    "I could not ground that question confidently in BastionFed's current docs, code map, "
                    "or live platform state.\n\n"
                    "**Try asking about:** alerts, incidents, FL Health, audit verification, forensics, "
                    "BastionBot behavior, or specific IDs like `ALT-0047` or `INC-001`."
                ),
                sources=[],
                topics=topics,
                memory_used=memory_used,
            )

        answer = self._generate_grounded_answer(
            query=query,
            classification=classification,
            sources=sources[:6],
            live_points=live_points,
            history=history,
            memory=memory,
        )

        return AskResult(answer=answer, sources=sources[:6], topics=topics, memory_used=memory_used)

    def _classify_query(self, query: str) -> str:
        q = query.lower()
        live = any(token in q for token in ("alert", "incident", "device", "fl", "audit", "current", "latest", "open "))
        impl = any(token in q for token in ("endpoint", "api", "backend", "frontend", "router", "component", "implementation", "code"))
        if live and impl:
            return "mixed"
        if impl:
            return "implementation_help"
        if live:
            return "live_data"
        return "product_help"

    def _workflow_guidance(self, classification: str, query: str) -> list[str]:
        q = query.lower()
        guidance: list[str] = []
        if "alert" in q:
            guidance.append("Use the Alerts page for live triage. Guests can inspect alerts, but only signed-in analysts can change alert status or quarantine devices.")
        if "incident" in q:
            guidance.append("Use the Incidents board for the list view, then open incident detail for timelines and playbook context.")
        if "audit" in q:
            guidance.append("Use the Audit page to inspect the chain verification result and the audit log table side by side.")
        if "fl" in q or "federated" in q:
            guidance.append("Use FL Health for round status, client participation, and live FL patch updates.")
        if "forensic" in q or "sample" in q or "rca" in q:
            guidance.append("Use the Forensics page for malware sample review and RCA-oriented investigation context.")
        if not guidance:
            guidance.append("Use BastionBot for read-only product guidance, then move to the relevant BastionFed screen to inspect or act manually.")
        if classification in ("implementation_help", "mixed"):
            guidance.append("For implementation-level details, the source citations point you to the exact docs or code areas that define the current behavior.")
        return guidance[:4]

    def _generate_grounded_answer(
        self,
        *,
        query: str,
        classification: str,
        sources: list[SourceCitation],
        live_points: list[str],
        history: list[str],
        memory: BotUserMemory | None,
    ) -> str:
        if settings.groq_api_key:
            try:
                return self._generate_with_groq(
                    query=query,
                    classification=classification,
                    sources=sources,
                    live_points=live_points,
                    history=history,
                    memory=memory,
                )
            except Exception:
                pass
        return self._local_fallback_answer(
            query=query,
            classification=classification,
            sources=sources,
            live_points=live_points,
            history=history,
            memory=memory,
        )

    def _generate_with_groq(
        self,
        *,
        query: str,
        classification: str,
        sources: list[SourceCitation],
        live_points: list[str],
        history: list[str],
        memory: BotUserMemory | None,
    ) -> str:
        system_prompt = (
            "You are BastionBot, a Blue Team BastionFed product and platform assistant. "
            "You operate in read-only ask mode. "
            "Only answer from the provided grounding. "
            "Do not claim to have executed any action. "
            "If the grounding is insufficient, say so clearly. "
            "Be concise, technical, and practical. "
            "Use markdown with short sections."
        )
        payload = {
            "classification": classification,
            "question": query,
            "recentHistory": history[-4:],
            "recentTopics": memory.recent_topics[:6] if memory else [],
            "livePoints": live_points,
            "sources": [
                {
                    "label": source.label,
                    "type": source.source_type,
                    "path": source.path,
                    "excerpt": source.excerpt,
                }
                for source in sources
            ],
            "responseRequirements": [
                "Answer the user's question directly.",
                "Reference BastionFed screens, APIs, or workflows when relevant.",
                "Keep BastionBot read-only.",
                "End with a short 'Sources' section listing the cited labels.",
            ],
        }

        response = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.groq_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.groq_model,
                "temperature": 0.2,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(payload)},
                ],
            },
            timeout=20.0,
        )
        response.raise_for_status()
        body = response.json()
        return body["choices"][0]["message"]["content"].strip()

    def _local_fallback_answer(
        self,
        *,
        query: str,
        classification: str,
        sources: list[SourceCitation],
        live_points: list[str],
        history: list[str],
        memory: BotUserMemory | None,
    ) -> str:
        intros = {
            "product_help": "Here is the grounded BastionFed product answer based on the current app docs and UI structure.",
            "implementation_help": "Here is the grounded implementation answer based on the current BastionFed backend/frontend structure.",
            "live_data": "Here is the grounded answer using BastionFed's current in-process platform data plus the relevant docs.",
            "mixed": "Here is the grounded answer using both BastionFed's implementation docs and the current platform state.",
        }
        lines = [intros.get(classification, intros["mixed"]), ""]

        if live_points:
            lines.append("**Current BastionFed state**")
            for point in live_points:
                lines.append(f"- {point}")
            lines.append("")

        if sources:
            lines.append("**Grounded details**")
            for source in sources[:3]:
                lines.append(f"- {source.excerpt}")
            lines.append("")

        lines.append("**How to use this in BastionFed**")
        lines.extend(f"- {item}" for item in self._workflow_guidance(classification, query))
        if history or (memory and memory.recent_topics):
            lines.append("")
            lines.append("**Context continuity**")
            lines.append("- I used your existing BastionBot conversation or recent topics to keep this answer in-context.")

        lines.append("")
        lines.append("**Sources**")
        for idx, source in enumerate(sources, start=1):
            lines.append(f"- [{idx}] {source.label}")
        return "\n".join(lines).strip()

    def _derive_topics(self, *, query: str, classification: str, sources: list[SourceCitation]) -> list[str]:
        q = query.lower()
        topics: list[str] = [classification]
        keyword_topics = {
            "alerts": ("alert", "alerts", "triage"),
            "incidents": ("incident", "playbook"),
            "audit": ("audit", "verify", "chain"),
            "fl-health": ("fl", "federated", "model", "round"),
            "forensics": ("forensic", "sample", "rca", "malware"),
            "bastionbot": ("bastionbot", "assistant", "ask mode"),
        }
        for topic, words in keyword_topics.items():
            if any(word in q for word in words):
                topics.append(topic)
        for source in sources:
            if source.source_type in ("api", "ui"):
                topics.append(source.label.lower().split()[0])
        deduped: list[str] = []
        for topic in topics:
            if topic and topic not in deduped:
                deduped.append(topic)
        return deduped[:8]

    def _live_context(
        self,
        *,
        query: str,
        state: AppState,
        context: BotChatContext | None,
    ) -> tuple[list[SourceCitation], list[str]]:
        citations: list[SourceCitation] = []
        points: list[str] = []
        q = query.upper()

        alert_id = context.alert_id if context and context.alert_id else self._first_match(r"ALT-[A-Z0-9-]+", q)
        incident_id = context.incident_id if context and context.incident_id else self._first_match(r"INC-[A-Z0-9-]+", q)
        device_id = self._first_match(r"DEV-[A-Z0-9-]+", q)

        if alert_id:
            alert = state.get_alert(alert_id)
            if alert:
                citations.append(self._alert_citation(alert))
                points.append(
                    f"`{alert.id}` is a {alert.severity} alert on {alert.device.name} in {alert.device.wing}, "
                    f"currently `{alert.status}` with MITRE technique `{alert.technique.id} - {alert.technique.name}`."
                )
        if incident_id:
            incident = state.get_incident(incident_id)
            if incident:
                citations.append(self._incident_citation(incident))
                points.append(
                    f"`{incident.id}` is `{incident.status}` with severity `{incident.severity}` and "
                    f"{len(incident.affected_devices)} affected device(s)."
                )
        if device_id:
            device = state.get_device(device_id)
            if device:
                citations.append(self._device_citation(device))
                points.append(
                    f"`{device.id}` is `{device.status}` for {device.name} in {device.wing} with IP `{device.ip}`."
                )

        lowered = query.lower()
        if any(token in lowered for token in ("dashboard", "kpi", "current threats", "open incidents")):
            kpis = state.dashboard_kpis()
            citations.append(
                SourceCitation(
                    id=f"src_live_kpi_{len(citations) + 1}",
                    label="Live dashboard KPI snapshot",
                    source_type="live_data",
                    path="live://dashboard/kpis",
                    excerpt=(
                        f"Active threats: {kpis['activeThreats']}, open incidents: {kpis['openIncidents']}, "
                        f"critical alerts: {kpis['criticalAlerts']}."
                    ),
                )
            )
            points.append(
                f"The current KPI snapshot shows {kpis['activeThreats']} active threats, {kpis['openIncidents']} open incidents, "
                f"and {kpis['criticalAlerts']} critical alerts."
            )

        if any(token in lowered for token in ("fl", "federated", "client participation", "model round")):
            fl = state.fl_status_dict()
            citations.append(
                SourceCitation(
                    id=f"src_live_fl_{len(citations) + 1}",
                    label="Live FL status snapshot",
                    source_type="live_data",
                    path="live://fl/status",
                    excerpt=(
                        f"Current FL round {fl['currentRound']} with {fl['activeClients']} active clients out of "
                        f"{fl['totalClients']} total clients."
                    ),
                )
            )
            points.append(
                f"FL is on round {fl['currentRound']} with {fl['activeClients']}/{fl['totalClients']} active clients and "
                f"aggregator status `{fl['aggregatorStatus']}`."
            )

        if "audit" in lowered and ("verify" in lowered or "verif" in lowered or "chain" in lowered):
            audit = state.verify_audit_chain()
            citations.append(
                SourceCitation(
                    id=f"src_live_audit_{len(citations) + 1}",
                    label="Live audit verification result",
                    source_type="live_data",
                    path="live://audit/verify",
                    excerpt=f"Audit chain valid={audit['valid']} across {audit['totalLogs']} log(s).",
                )
            )
            if audit["valid"]:
                points.append(f"The current audit chain verifies cleanly across {audit['totalLogs']} log(s).")
            else:
                points.append(f"The current audit chain is broken at `{audit['firstBreakAt']}`.")

        return citations, points

    def _first_match(self, pattern: str, text: str) -> str | None:
        match = re.search(pattern, text)
        return match.group(0) if match else None

    def _alert_citation(self, alert: Alert) -> SourceCitation:
        return SourceCitation(
            id=f"src_live_alert_{alert.id}",
            label=f"Live alert {alert.id}",
            source_type="live_data",
            path=f"live://alerts/{alert.id}",
            excerpt=(
                f"{alert.id} is {alert.severity} / {alert.status} on {alert.device.name} in {alert.device.wing} "
                f"with tactic {alert.tactic}."
            ),
        )

    def _incident_citation(self, incident: Incident) -> SourceCitation:
        return SourceCitation(
            id=f"src_live_incident_{incident.id}",
            label=f"Live incident {incident.id}",
            source_type="live_data",
            path=f"live://incidents/{incident.id}",
            excerpt=(
                f"{incident.id} is {incident.status} with severity {incident.severity}, "
                f"assignee {incident.assignee}, priority {incident.priority}."
            ),
        )

    def _device_citation(self, device: Device) -> SourceCitation:
        return SourceCitation(
            id=f"src_live_device_{device.id}",
            label=f"Live device {device.id}",
            source_type="live_data",
            path=f"live://devices/{device.id}",
            excerpt=f"{device.id} is {device.status} for {device.name} at {device.ip} in {device.wing}.",
        )

bastionbot_engine = BastionBotEngine(_find_repo_root())
