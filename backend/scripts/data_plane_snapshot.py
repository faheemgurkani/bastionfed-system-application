#!/usr/bin/env python3
"""
data_plane_snapshot.py — Read-only inventory of BastionFed data-plane stores.

Uses the same .env discovery as scripts/cleanup.py and probes:
  • PostgreSQL (SUPABASE_DATABASE_URL / DATABASE_URL) — row counts + short samples
  • Supabase Storage — buckets + whether objects exist at root
  • Redis (redis-cli TCP or Upstash REST DBSIZE)
  • Local BastionBot SQLite (BASTIONBOT_DB_PATH / default backend/data/runtime/bastionbot.sqlite3 from cwd backend/)
  • Firebase Auth — user count + emails (Identity Toolkit REST + openssl JWT, same idea as cleanup.py)
  • Firestore — document count in `users` collection

No writes. Safe to run while app servers are stopped (cloud DBs must still be reachable).
"""

from __future__ import annotations

import json
import os
import shutil
import ssl
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


def _find_env() -> Path:
    candidate = Path(__file__).resolve().parent
    for _ in range(4):
        p = candidate / ".env"
        if p.exists():
            return p
        candidate = candidate.parent
    return Path(__file__).resolve().parent / ".env"


_env_path = _find_env()
try:
    from dotenv import load_dotenv

    load_dotenv(_env_path)
except ImportError:
    if _env_path.exists():
        for line in _env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _hr(title: str) -> None:
    print(f"\n{'─' * 62}\n  {title}\n{'─' * 62}", flush=True)


def _info(msg: str) -> None:
    print(f"  • {msg}", flush=True)


def _warn(msg: str) -> None:
    print(f"  ⚠  {msg}", flush=True)


def _err(msg: str) -> None:
    print(f"  ✗ {msg}", file=sys.stderr, flush=True)


_PG_TABLES = [
    "membership_client_scopes",
    "client_user_invites",
    "memberships",
    "rca_reports",
    "malware_samples",
    "bot_messages",
    "bot_conversations",
    "bot_user_memory",
    "ingest_events",
    "ingest_sources",
    "incident_events",
    "incidents",
    "alerts",
    "audit_log",
    "fl_rounds",
    "fl_clients",
    "devices",
    "model_registry",
    "tenants",
    "users",
]


def snapshot_postgres() -> None:
    _hr("PostgreSQL (Supabase)")
    db_url = os.getenv("SUPABASE_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not db_url:
        _warn("DATABASE_URL / SUPABASE_DATABASE_URL not set — skipping.")
        return
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError:
        _warn("psycopg not installed. pip install 'psycopg[binary]'")
        return

    try:
        with psycopg.connect(db_url, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                for table in _PG_TABLES:
                    try:
                        cur.execute(f"SELECT COUNT(*) AS n FROM {table}")  # noqa: S608
                        n = int((cur.fetchone() or {}).get("n", 0))
                    except Exception as exc:
                        _info(f"{table}: (unreadable) {exc}")
                        continue
                    _info(f"{table}: {n} row(s)")
                _info("— samples (bounded) —")
                for q, label in (
                    ("SELECT id, name FROM tenants ORDER BY id LIMIT 8", "tenants"),
                    (
                        "SELECT u.firebase_uid, u.email, u.display_name, m.tenant_id, m.role "
                        "FROM users u LEFT JOIN memberships m ON u.firebase_uid = m.firebase_uid "
                        "ORDER BY u.firebase_uid, m.tenant_id NULLS LAST LIMIT 12",
                        "users (+ membership)",
                    ),
                    (
                        "SELECT tenant_id, id, department, participation_pct, last_round, "
                        "status::text, model_version FROM fl_clients ORDER BY tenant_id, id LIMIT 12",
                        "fl_clients",
                    ),
                    ("SELECT id, tenant_id, name, status::text FROM devices ORDER BY tenant_id, id LIMIT 8", "devices"),
                    (
                        "SELECT id, tenant_id, type, severity::text, status::text FROM alerts "
                        "ORDER BY created_at DESC NULLS LAST LIMIT 5",
                        "alerts (latest)",
                    ),
                ):
                    try:
                        cur.execute(q)
                        rows = cur.fetchall()
                    except Exception as exc:
                        _info(f"{label}: {exc}")
                        conn.rollback()
                        continue
                    if not rows:
                        _info(f"{label}: (empty)")
                        continue
                    _info(f"{label}: {len(rows)} row(s) shown")
                    for r in rows:
                        _info(f"    {dict(r)}")
    except Exception as exc:
        _err(f"PostgreSQL: {exc}")


def _storage_headers(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}", "apikey": key}


def _storage_http_json(method: str, url: str, *, key: str, json_body: dict | None = None, timeout_s: float = 60.0) -> object:
    headers = dict(_storage_headers(key))
    data: bytes | None = None
    if json_body is not None:
        data = json.dumps(json_body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(url, data=data, method=method.upper())
    for hk, hv in headers.items():
        req.add_header(hk, hv)
    ctx = ssl.create_default_context()
    with urlopen(req, timeout=timeout_s, context=ctx) as resp:
        raw = resp.read()
    if not raw:
        return None
    return json.loads(raw.decode("utf-8"))


def snapshot_storage() -> None:
    _hr("Supabase Storage")
    base = (os.getenv("SUPABASE_PROJECT_URL") or os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
    key = (os.getenv("SUPABASE_SERVICE_KEY") or "").strip()
    if not base or not key:
        _warn("SUPABASE_PROJECT_URL / SUPABASE_SERVICE_KEY not set — skipping.")
        return
    try:
        buckets = _storage_http_json("GET", f"{base}/storage/v1/bucket", key=key)
    except Exception as exc:
        _err(f"list buckets: {exc}")
        return
    if not isinstance(buckets, list):
        _warn(f"unexpected bucket list: {type(buckets)}")
        return
    for b in buckets:
        if not isinstance(b, dict):
            continue
        name = (b.get("name") or b.get("id") or "").strip()
        if not name:
            continue
        enc = quote(name, safe="")
        url = f"{base}/storage/v1/object/list/{enc}"
        try:
            data = _storage_http_json(
                "POST",
                url,
                key=key,
                json_body={"prefix": "", "limit": 50, "offset": 0},
            )
        except Exception as exc:
            _info(f"bucket {name}: list error {exc}")
            continue
        nobj = len(data) if isinstance(data, list) else "?"
        _info(f"bucket {name}: up to {nobj} listing entries at root (first page)")


def _upstash_rest_command(rest_base: str, token: str, command: list[object], *, timeout_s: float = 20.0) -> dict:
    url = rest_base.strip().rstrip("/")
    body_json = json.dumps(command)
    curl_bin = shutil.which("curl")
    if curl_bin:
        p = subprocess.run(
            [
                curl_bin,
                "-sS",
                "--connect-timeout",
                "5",
                "-m",
                str(int(timeout_s)),
                "-X",
                "POST",
                "-H",
                f"Authorization: Bearer {token}",
                "-H",
                "Content-Type: application/json",
                "-d",
                body_json,
                url,
            ],
            capture_output=True,
            text=True,
            timeout=float(timeout_s + 15),
        )
        if p.returncode != 0:
            raise RuntimeError((p.stderr or p.stdout or "curl failed").strip()[:500])
        raw = p.stdout.encode("utf-8")
    else:
        body = body_json.encode("utf-8")
        req = Request(url, data=body, method="POST")
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("Content-Type", "application/json")
        ctx = ssl.create_default_context()
        with urlopen(req, timeout=timeout_s, context=ctx) as resp:
            raw = resp.read()
    obj = json.loads(raw.decode("utf-8"))
    if not isinstance(obj, dict) or obj.get("error") is not None:
        raise RuntimeError(str(obj.get("error", obj)))
    return obj


def snapshot_redis() -> None:
    _hr("Redis")
    rest_url = (os.getenv("UPSTASH_REDIS_REST_URL") or "").strip().strip('"').strip("'")
    rest_token = (os.getenv("UPSTASH_REDIS_REST_TOKEN") or "").strip().strip('"').strip("'")
    tcp_url = (os.getenv("UPSTASH_REDIS_URL") or os.getenv("REDIS_URL") or "").strip().strip('"').strip("'")
    cli = shutil.which("redis-cli")

    if tcp_url and cli:
        try:
            p = subprocess.run(
                ["redis-cli", "-u", tcp_url, "DBSIZE"],
                capture_output=True,
                text=True,
                timeout=20.0,
            )
            if p.returncode == 0:
                _info(f"DBSIZE (redis-cli TCP): {(p.stdout or '').strip()}")
                return
        except Exception as exc:
            _warn(f"redis-cli: {exc}")

    if rest_url and rest_token:
        try:
            r = _upstash_rest_command(rest_url, rest_token, ["DBSIZE"], timeout_s=20.0)
            _info(f"DBSIZE (Upstash REST): {r.get('result')}")
        except Exception as exc:
            _err(f"Upstash REST: {exc}")
        return

    _warn("No Redis URL / REST credentials — skipping.")


def snapshot_sqlite_bastionbot() -> None:
    _hr("BastionBot SQLite (local)")
    raw = os.getenv("BASTIONBOT_DB_PATH", "").strip()
    if raw:
        p = Path(raw)
        if not p.is_absolute():
            p = Path(__file__).resolve().parents[1] / p
    else:
        p = Path(__file__).resolve().parents[1] / "data" / "runtime" / "bastionbot.sqlite3"
    if not p.exists():
        _info(f"No file at {p} (no local bot DB yet).")
        return
    try:
        import sqlite3

        con = sqlite3.connect(str(p))
        cur = con.cursor()
        for t in ("bot_conversations", "bot_messages", "bot_user_memory"):
            try:
                cur.execute(f"SELECT COUNT(*) FROM {t}")  # noqa: S608
                n = cur.fetchone()[0]
                _info(f"{t}: {n} row(s)")
            except Exception as exc:
                _info(f"{t}: {exc}")
        con.close()
    except Exception as exc:
        _err(str(exc))


def _b64url_encode(raw: bytes) -> str:
    import base64

    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _gcp_jwt_assertion_openssl(cred_dict: dict) -> str:
    openssl = shutil.which("openssl")
    if not openssl:
        raise RuntimeError("openssl not in PATH")
    now = int(time.time())
    sa_email = cred_dict["client_email"]
    private_key = cred_dict["private_key"]
    header = {"alg": "RS256", "typ": "JWT"}
    payload = {
        "iss": sa_email,
        "sub": sa_email,
        "aud": "https://oauth2.googleapis.com/token",
        "iat": now,
        "exp": now + 3600,
        "scope": "https://www.googleapis.com/auth/cloud-platform",
    }

    def _jc(d: dict) -> bytes:
        return json.dumps(d, separators=(",", ":")).encode("utf-8")

    signing_input = f"{_b64url_encode(_jc(header))}.{_b64url_encode(_jc(payload))}"
    fd, key_path = tempfile.mkstemp(suffix=".pem", text=True)
    try:
        with os.fdopen(fd, "w") as wf:
            wf.write(private_key)
        os.chmod(key_path, 0o600)
        p = subprocess.run(
            [openssl, "dgst", "-binary", "-sha256", "-sign", key_path],
            input=signing_input.encode("utf-8"),
            capture_output=True,
            timeout=30.0,
        )
        if p.returncode != 0:
            raise RuntimeError((p.stderr or b"").decode()[:200])
        sig = _b64url_encode(p.stdout)
    finally:
        try:
            os.unlink(key_path)
        except OSError:
            pass
    return f"{signing_input}.{sig}"


def _gcp_access_token(cred_dict: dict) -> str:
    assertion = _gcp_jwt_assertion_openssl(cred_dict)
    body = urlencode(
        {"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertion}
    ).encode("utf-8")
    req = Request("https://oauth2.googleapis.com/token", data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    ctx = ssl.create_default_context()
    with urlopen(req, timeout=30.0, context=ctx) as resp:
        obj = json.loads(resp.read().decode("utf-8"))
    token = obj.get("access_token")
    if not token:
        raise RuntimeError("no access_token")
    return str(token)


def _google_rest_json(method: str, url: str, *, token: str, body: dict | None = None, timeout_s: float = 60.0) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    ctx = ssl.create_default_context()
    with urlopen(req, timeout=timeout_s, context=ctx) as resp:
        raw = resp.read()
    if not raw:
        return {}
    return json.loads(raw.decode("utf-8"))


def snapshot_firebase() -> None:
    _hr("Firebase Auth + Firestore (read-only)")
    cred_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY_JSON", "").strip()
    if not cred_json:
        _warn("FIREBASE_SERVICE_ACCOUNT_KEY_JSON not set — skipping Auth/Firestore.")
        return
    try:
        cred_dict = json.loads(cred_json)
    except json.JSONDecodeError as exc:
        _err(f"Invalid service account JSON: {exc}")
        return
    project_id = cred_dict.get("project_id")
    if not project_id:
        _err("project_id missing in service account JSON")
        return
    try:
        token = _gcp_access_token(cred_dict)
    except Exception as exc:
        _err(f"OAuth: {exc}")
        return

    # Auth: list users (first page only for snapshot)
    try:
        resp = _google_rest_json(
            "POST",
            f"https://identitytoolkit.googleapis.com/v1/projects/{project_id}/accounts:query",
            token=token,
            body={"returnUserInfo": True, "limit": "100", "offset": "0"},
        )
        users = resp.get("userInfo") or []
        _info(f"Auth users (first 100): {len(users)}")
        for u in users[:20]:
            email = u.get("email") or ""
            uid = u.get("localId") or ""
            verified = u.get("emailVerified", False)
            _info(f"    {email or '(no email)'}  uid={uid[:12]}…  emailVerified={verified}")
        if len(users) > 20:
            _info(f"    … and {len(users) - 20} more in first page")
    except (HTTPError, URLError, RuntimeError, KeyError, json.JSONDecodeError) as exc:
        _err(f"Auth list: {exc}")

    # Firestore users collection count (first 300 docs)
    db_seg = quote("(default)", safe="")
    col = "users"
    list_url = (
        f"https://firestore.googleapis.com/v1/projects/{quote(str(project_id), safe='')}"
        f"/databases/{db_seg}/documents/{quote(col, safe='')}"
    )
    try:
        resp = _google_rest_json("GET", f"{list_url}?pageSize=300", token=token, body=None)
        docs = resp.get("documents") or []
        _info(f"Firestore collection '{col}': {len(docs)} document(s) in first page")
        for d in docs[:10]:
            name = (d.get("name") or "").rsplit("/", 1)[-1]
            _info(f"    doc id: {name}")
    except Exception as exc:
        _warn(f"Firestore list: {exc}")


def main() -> None:
    print("\n  BastionFed data-plane snapshot (read-only)\n  .env:", _env_path, flush=True)
    snapshot_postgres()
    snapshot_storage()
    snapshot_redis()
    snapshot_sqlite_bastionbot()
    snapshot_firebase()
    _hr("Done")
    print("  End of snapshot.\n", flush=True)


if __name__ == "__main__":
    main()
