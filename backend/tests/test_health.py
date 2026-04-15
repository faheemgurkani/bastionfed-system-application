from fastapi.testclient import TestClient

from app.main import app
from app.services.supabase_storage import parse_bucket_and_object


def test_health_shallow_ok():
    with TestClient(app) as c:
        r = c.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data.get("status") == "ok"
        assert "demo_mode" in data
        assert isinstance(data.get("demo_mode"), bool)


def test_health_ready_demo_mode():
    """No data plane configured in tests → status demo, 200."""
    with TestClient(app) as c:
        r = c.get("/health/ready")
        assert r.status_code == 200
        data = r.json()
        assert data.get("status") == "demo"
        assert "postgres" in data and "redis" in data and "storage" in data


def test_parse_storage_path_for_signed_url():
    assert parse_bucket_and_object("forensics/sub/file.bin") == ("forensics", "sub/file.bin")
    assert parse_bucket_and_object("bad") is None
