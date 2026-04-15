import pytest
from fastapi.testclient import TestClient

from app.auth.deps import set_token_verifier
from app.bastionbot import bastionbot_engine, bastionbot_store
from app.bastionbot.engine import BastionBotEngine
from app.config import settings
from app.main import app
from app.store.tenant_store import MemoryTenantStore, set_tenant_store, tenant_store


class _FakeVerifier:
    def verify(self, token: str):
        uid = token.replace("test-token", "user-faheem").replace("other-token", "user-hunain")
        if uid == token:
            uid = "user-faheem"

        class _Verified:
            def __init__(self, uid: str):
                self.uid = uid
                self.email = f"{uid}@example.test"
                self.name = uid
                self.picture = None
                self.claims = {"sub": uid}

        return _Verified(uid)


@pytest.fixture(autouse=True)
def _reset_state(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "database_url", None)
    monkeypatch.setattr(settings, "redis_url", None)
    monkeypatch.setattr(settings, "supabase_url", None)
    monkeypatch.setattr(settings, "supabase_service_key", None)
    monkeypatch.setattr(settings, "strict_data_plane", False)
    monkeypatch.setattr(settings, "demo_mode", True)

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
    set_token_verifier(_FakeVerifier())
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        current_store = tenant_store
        current_store.ensure_demo_tenant()
        user_a = current_store.ensure_session_user(
            firebase_uid="user-faheem",
            email="user-faheem@example.test",
            display_name="Faheem",
            photo_url=None,
        )
        user_b = current_store.ensure_session_user(
            firebase_uid="user-hunain",
            email="user-hunain@example.test",
            display_name="Hunain",
            photo_url=None,
        )
        memberships = getattr(current_store, "memberships", None)
        if isinstance(memberships, list):
            for membership in memberships:
                if membership["firebase_uid"] in {"user-faheem", "user-hunain"}:
                    membership["is_default"] = False
            memberships.append(
                {"tenant_id": settings.demo_tenant_id, "firebase_uid": user_a.uid, "role": "owner", "is_default": True}
            )
            memberships.append(
                {"tenant_id": settings.demo_tenant_id, "firebase_uid": user_b.uid, "role": "analyst", "is_default": True}
            )
        bastionbot_store.configure(settings.bastionbot_db_path)
        bastionbot_engine.initialize()
        yield c


@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer test-token"}


@pytest.fixture
def other_auth_headers():
    return {"Authorization": "Bearer other-token"}
