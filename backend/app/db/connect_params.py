"""Shared psycopg 3 connection parameters: timeouts and application_name (see psycopg docs).

Runtime connections use a generous connect_timeout. Readiness probes use a shorter
timeout plus statement_timeout so a stuck DB cannot block probes indefinitely.
"""

from __future__ import annotations

from typing import Any

# libpq connect_timeout (seconds) for normal app / migration connections
PG_CONNECT_TIMEOUT_S = 15

# Faster failing probe for /health/ready and strict startup checks
PG_PROBE_CONNECT_TIMEOUT_S = 10


def pg_app_connect_kwargs(*, application_name: str) -> dict[str, Any]:
    """Connections used by migrations, BastionBot store, tenant store, etc."""
    return {
        "connect_timeout": PG_CONNECT_TIMEOUT_S,
        "prepare_threshold": None,
        "application_name": (application_name or "bastionfed")[:63],
    }


def pg_probe_connect_kwargs() -> dict[str, Any]:
    """Health/readiness: short connect + server-side cap on the probe query (SELECT 1)."""
    return {
        "connect_timeout": PG_PROBE_CONNECT_TIMEOUT_S,
        "prepare_threshold": None,
        "application_name": "bastionfed_readiness",
        "options": "-c statement_timeout=5000",
    }
