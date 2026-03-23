import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.store.memory import state


@pytest.fixture(autouse=True)
def _reset_state():
    state.reset()
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer test-token"}
