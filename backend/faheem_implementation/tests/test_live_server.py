"""Optional black-box checks against a running uvicorn (real TCP).

Set LIVE_SERVER_URL, e.g.:
  uvicorn app.main:app --host 127.0.0.1 --port 8000
  export LIVE_SERVER_URL=http://127.0.0.1:8000
  pytest tests/test_live_server.py -v

Covers what in-process TestClient cannot: SSE bodies on infinite streams.
Skipped by default so CI stays self-contained.
"""

from __future__ import annotations

import os

import httpx
import pytest

LIVE = os.environ.get("LIVE_SERVER_URL", "").strip().rstrip("/")

pytestmark = pytest.mark.integration


@pytest.mark.skipif(not LIVE, reason="LIVE_SERVER_URL not set (e.g. http://127.0.0.1:8000)")
def test_live_health():
    r = httpx.get(f"{LIVE}/health", timeout=5.0)
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


@pytest.mark.skipif(not LIVE, reason="LIVE_SERVER_URL not set")
def test_live_openapi_lists_core_paths():
    r = httpx.get(f"{LIVE}/openapi.json", timeout=5.0)
    assert r.status_code == 200
    paths = r.json().get("paths", {})
    assert "/api/alerts" in paths
    assert "/api/events" in paths
    assert "/api/fl/clients" in paths
    assert "/api/fl-events" in paths


def _read_sse_prefix(url: str, *, max_bytes: int = 96_000) -> bytes:
    timeout = httpx.Timeout(10.0, read=10.0)
    buf = b""
    with httpx.Client(timeout=timeout) as client:
        with client.stream("GET", url) as r:
            r.raise_for_status()
            ct = (r.headers.get("content-type") or "").lower()
            assert "text/event-stream" in ct
            for chunk in r.iter_bytes():
                buf += chunk
                if b": keep-alive" in buf and b"data:" in buf:
                    break
                if len(buf) >= max_bytes:
                    break
    return buf


@pytest.mark.skipif(not LIVE, reason="LIVE_SERVER_URL not set")
def test_live_events_sse_body():
    buf = _read_sse_prefix(f"{LIVE}/api/events?guest=true")
    assert b": keep-alive" in buf
    assert b"data:" in buf


@pytest.mark.skipif(not LIVE, reason="LIVE_SERVER_URL not set")
def test_live_fl_events_sse_body():
    buf = _read_sse_prefix(f"{LIVE}/api/fl-events?guest=true")
    assert b": keep-alive" in buf
    assert b"data:" in buf
    assert b"participationPct" in buf
