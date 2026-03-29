import pytest
from fastapi.testclient import TestClient

from app.bastionbot import bastionbot_engine, bastionbot_store
from app.bastionbot.engine import BastionBotEngine
from app.config import settings
from app.main import app
from app.store.memory import state


@pytest.fixture(autouse=True)
def _reset_state(tmp_path, monkeypatch):
    settings.bastionbot_db_path = str(tmp_path / "bastionbot.sqlite3")
    settings.groq_api_key = "test-groq-key"
    settings.groq_model = "llama-3.1-8b-instant"

    def _fake_groq(
        self: BastionBotEngine,
        *,
        query: str,
        classification: str,
        sources,
        live_points,
        history,
        memory,
    ) -> str:
        lines = [f"Groq-backed BastionBot answer for: {query}", f"Classification: {classification}"]
        if live_points:
            lines.append("Live context:")
            lines.extend(f"- {point}" for point in live_points[:3])
        if sources:
            lines.append("Sources:")
            lines.extend(f"- {source.label}" for source in sources[:3])
        if history or (memory and memory.recent_topics):
            lines.append("Context continuity:")
            lines.append("- Prior BastionBot context was used.")
        return "\n".join(lines)

    monkeypatch.setattr(BastionBotEngine, "_generate_with_groq", _fake_groq)
    bastionbot_store.configure(settings.bastionbot_db_path)
    bastionbot_engine.initialize()
    state.reset()
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer test-token", "X-BastionFed-UID": "user-faheem"}


@pytest.fixture
def other_auth_headers():
    return {"Authorization": "Bearer test-token", "X-BastionFed-UID": "user-hunain"}
