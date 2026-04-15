"""Live Upstash / Redis checks (skipped when backend/.env has no TCP URL).

Mapping: docs/FIREBASE_DATA_PLANE_MAPPING.md §4 — `REDIS_URL` or `UPSTASH_REDIS_URL`
(`rediss://…`) for redis-py. Does not use REST URL/token.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from dotenv import dotenv_values


def _backend_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _redis_url_from_backend_env() -> str | None:
    env_path = _backend_root() / ".env"
    if not env_path.is_file():
        return None
    vals = dotenv_values(env_path)
    raw = vals.get("UPSTASH_REDIS_URL") or vals.get("REDIS_URL")
    if not raw:
        return None
    s = str(raw).strip().strip('"').strip("'")
    return s or None


def _skip_if_no_url():
    if not _redis_url_from_backend_env():
        pytest.skip("Set UPSTASH_REDIS_URL or REDIS_URL in backend/.env (see mapping doc §4)")


@pytest.fixture
def redis_url() -> str:
    _skip_if_no_url()
    u = _redis_url_from_backend_env()
    assert u is not None
    return u


def test_upstash_tcp_ping(redis_url: str) -> None:
    import redis as redis_sync

    client = redis_sync.from_url(redis_url, decode_responses=True)
    try:
        try:
            assert client.ping() is True
        except redis_sync.RedisError as exc:
            pytest.skip(f"Live Upstash unreachable from this environment: {exc}")
    finally:
        client.close()


def test_upstash_pubsub_roundtrip(redis_url: str) -> None:
    import redis as redis_sync

    channel = "bastionfed:pytest_verify"
    sub_cli = redis_sync.from_url(redis_url, decode_responses=True)
    pub_cli = redis_sync.from_url(redis_url, decode_responses=True)
    try:
        try:
            pubsub = sub_cli.pubsub()
            pubsub.subscribe(channel)
            first = pubsub.get_message(timeout=10.0)
            assert first is not None
            assert first.get("type") == "subscribe"

            payload = "bastionfed-redis-verify"
            n = pub_cli.publish(channel, payload)
            assert n >= 1

            for _ in range(50):
                msg = pubsub.get_message(timeout=0.2)
                if msg and msg.get("type") == "message":
                    assert msg.get("data") == payload
                    break
            else:
                pytest.fail("no pub/sub message received from Upstash")
        except redis_sync.RedisError as exc:
            pytest.skip(f"Live Upstash unreachable from this environment: {exc}")
    finally:
        pub_cli.close()
        sub_cli.close()


def test_upstash_url_uses_tls_scheme(redis_url: str) -> None:
    """Console `rediss://` matches mapping doc (TLS on)."""
    assert redis_url.startswith("rediss://"), "Use Upstash TCP URL (rediss://), not redis://"
