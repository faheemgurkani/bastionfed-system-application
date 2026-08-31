#!/usr/bin/env python3
"""
cleanup.py — Wipe all BastionFed development data.

Deletes:
  1. Every row in every Supabase / PostgreSQL app table (public schema)
  2. All objects in every Supabase Storage bucket (buckets kept)
  3. All keys in Redis (UPSTASH_REDIS_URL / REDIS_URL)
  4. All Firebase Auth users      → FIREBASE_SERVICE_ACCOUNT_KEY_JSON + openssl in PATH
     (Identity Toolkit REST; openssl signs OAuth JWT — no firebase_admin / PyJWT).
  5. Firestore documents in named collections (documents only; collections stay).

Usage
─────
  python cleanup.py                      # dry-run
  python cleanup.py --yes                # full wipe including Firebase / Firestore
  python cleanup.py --yes --supabase-redis-only   # Postgres + Storage + Redis only
  python cleanup.py --yes --skip-redis   # skip Redis (e.g. REST connect hangs)
  python cleanup.py --yes --postgres-auth-only    # Postgres only: users + memberships + scopes + invites (keeps tenants, FL, alerts, …)
  python cleanup.py --yes --firebase-only         # Firebase Auth + Firestore only

The script loads .env from the backend root automatically,
regardless of whether you run it as:
  python scripts/cleanup.py --yes
  python cleanup.py --yes
"""

import argparse
import base64
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


# ── Locate .env ────────────────────────────────────────────────────────────────
# Walk up from the script's location until we find a .env file or reach the fs root.
def _find_env() -> Path:
    candidate = Path(__file__).resolve().parent
    for _ in range(4):                        # search at most 4 levels up
        p = candidate / ".env"
        if p.exists():
            return p
        candidate = candidate.parent
    return Path(__file__).resolve().parent / ".env"  # fallback (may not exist)

_env_path = _find_env()

try:
    from dotenv import load_dotenv
    load_dotenv(_env_path)
except ImportError:
    # Fallback: parse the .env file manually
    if _env_path.exists():
        for line in _env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

# ── Helpers ────────────────────────────────────────────────────────────────────

def _hr(title: str = "") -> None:
    print(f"\n{'─' * 62}", flush=True)
    if title:
        print(f"  {title}", flush=True)
        print(f"{'─' * 62}", flush=True)

def _info(msg: str) -> None:  print(f"  • {msg}", flush=True)
def _ok(msg: str) -> None:    print(f"  ✓ {msg}", flush=True)
def _warn(msg: str) -> None:  print(f"  ⚠  {msg}", flush=True)
def _err(msg: str) -> None:   print(f"  ✗ {msg}", file=sys.stderr, flush=True)


# ── 1. PostgreSQL / Supabase ───────────────────────────────────────────────────

# Delete child tables before parent tables (FK constraints).
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
    # schema_migrations is intentionally kept
]


def clean_postgres(dry: bool) -> None:
    _hr("PostgreSQL (Supabase)")

    db_url = os.getenv("SUPABASE_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not db_url:
        _warn("DATABASE_URL / SUPABASE_DATABASE_URL not set — skipping.")
        return

    try:
        import psycopg  # type: ignore
        from psycopg.rows import dict_row  # type: ignore
    except ImportError:
        _warn("psycopg not installed.  Run: pip install 'psycopg[binary]'")
        return

    total_rows = 0
    try:
        with psycopg.connect(db_url, row_factory=dict_row) as conn:
            for table in _PG_TABLES:
                with conn.cursor() as cur:
                    try:
                        cur.execute(f"SELECT COUNT(*) AS n FROM {table}")  # noqa: S608
                        n = (cur.fetchone() or {}).get("n", 0)
                    except Exception:
                        n = "?"
                    label = f"{'would delete' if dry else 'deleting'} {str(n):>6} row(s) from  {table}"
                    _info(label)
                    if not dry:
                        cur.execute(f"DELETE FROM {table}")  # noqa: S608
                        total_rows += int(n) if isinstance(n, int) else 0
            if not dry:
                conn.commit()
    except Exception as exc:
        _err(f"PostgreSQL error: {exc}")
        return

    if dry:
        _info("(dry-run — nothing deleted)")
    else:
        _ok(f"PostgreSQL cleaned. ~{total_rows} rows removed.")


def clean_postgres_auth_only(dry: bool) -> None:
    """Delete identity rows only (Firebase sign-in still has users until full cleanup)."""
    _hr("PostgreSQL (auth tables only)")

    db_url = os.getenv("SUPABASE_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not db_url:
        _warn("DATABASE_URL / SUPABASE_DATABASE_URL not set — skipping.")
        return

    try:
        import psycopg  # type: ignore
        from psycopg.rows import dict_row  # type: ignore
    except ImportError:
        _warn("psycopg not installed.  Run: pip install 'psycopg[binary]'")
        return

    # FK-safe order: scopes → memberships → invites → users.
    statements: list[tuple[str, str]] = [
        ("DELETE FROM membership_client_scopes", "membership_client_scopes"),
        ("DELETE FROM memberships", "memberships"),
        ("DELETE FROM client_user_invites", "client_user_invites"),
        ("DELETE FROM users", "users"),
    ]

    try:
        with psycopg.connect(db_url, row_factory=dict_row) as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                for sql, label in statements:
                    try:
                        cur.execute(f"SELECT COUNT(*) AS n FROM {label}")  # noqa: S608
                        n = int((cur.fetchone() or {}).get("n", 0))
                    except Exception:
                        n = "?"
                    _info(f"{'would delete' if dry else 'deleting'} {str(n):>6} row(s) from  {label}")
                    if not dry:
                        try:
                            cur.execute(sql)
                        except Exception as exc:
                            _warn(f"{label}: {exc}")
    except Exception as exc:
        _err(f"PostgreSQL error: {exc}")
        return

    if dry:
        _info("(dry-run — auth tables not cleared)")
    else:
        _ok("PostgreSQL auth-related tables cleared (tenants / FL / devices / alerts unchanged).")


# ── 2. Supabase Storage ────────────────────────────────────────────────────────

def _storage_headers(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}", "apikey": key}


def _storage_http_json(
    method: str,
    url: str,
    *,
    key: str,
    json_body: dict | None = None,
    timeout_s: float = 90.0,
) -> object:
    """Supabase Storage REST via stdlib (avoids httpx/httpcore importing h2, which can hang on init)."""
    headers = dict(_storage_headers(key))
    data: bytes | None = None
    if json_body is not None:
        data = json.dumps(json_body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(url, data=data, method=method.upper())
    for hk, hv in headers.items():
        req.add_header(hk, hv)
    ctx = ssl.create_default_context()
    try:
        with urlopen(req, timeout=timeout_s, context=ctx) as resp:
            raw = resp.read()
    except HTTPError as e:
        detail = ""
        if e.fp is not None:
            try:
                detail = e.read().decode("utf-8", errors="replace")
            except Exception:
                detail = ""
        raise RuntimeError(f"HTTP {e.code} {e.reason}: {detail}") from e
    except URLError as e:
        raise RuntimeError(f"{e}") from e
    if not raw:
        return None
    return json.loads(raw.decode("utf-8"))


def _storage_root_list_has_any_objects(
    base: str,
    key: str,
    bucket_name: str,
    timeout_s: float,
) -> bool | None:
    """Return True if at least one object/folder exists at bucket root; False if none; None on error."""
    enc = quote(bucket_name, safe="")
    url = f"{base}/storage/v1/object/list/{enc}"
    try:
        data = _storage_http_json(
            "POST",
            url,
            key=key,
            json_body={"prefix": "", "limit": 100, "offset": 0},
            timeout_s=timeout_s,
        )
    except Exception:
        return None
    if not isinstance(data, list):
        return None
    return len(data) > 0


def clean_supabase_storage(dry: bool) -> None:
    _hr("Supabase Storage (empty buckets)")

    base = (os.getenv("SUPABASE_PROJECT_URL") or os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
    key = (os.getenv("SUPABASE_SERVICE_KEY") or "").strip()
    if not base or not key:
        _warn("SUPABASE_PROJECT_URL / SUPABASE_URL or SUPABASE_SERVICE_KEY not set — skipping.")
        return

    timeout_s = 90.0

    try:
        _info("GET /storage/v1/bucket (listing buckets)…")
        buckets = _storage_http_json(
            "GET",
            f"{base}/storage/v1/bucket",
            key=key,
            timeout_s=timeout_s,
        )
    except Exception as exc:
        _err(f"Supabase Storage list buckets: {exc}")
        return

    if not isinstance(buckets, list) or not buckets:
        _info("No buckets returned (or empty list).")
        if dry:
            _info("(dry-run — buckets not emptied)")
        return

    for b in buckets:
        if not isinstance(b, dict):
            continue
        name = (b.get("name") or b.get("id") or "").strip()
        if not name:
            continue
        if dry:
            _info(f"would empty bucket: {name}")
            continue

        try:
            _info(f"Checking objects in bucket: {name} …")
            has_any = _storage_root_list_has_any_objects(base, key, name, timeout_s)
        except Exception as exc:
            _warn(f"Could not list objects in {name} ({exc}); trying empty anyway.")
            has_any = None

        if has_any is False:
            _ok(f"Bucket already empty (skipped POST empty): {name}")
            continue

        try:
            enc = quote(name, safe="")
            _info(f"POST /storage/v1/bucket/…/empty → {name} …")
            _storage_http_json(
                "POST",
                f"{base}/storage/v1/bucket/{enc}/empty",
                key=key,
                json_body={},
                timeout_s=timeout_s,
            )
            _ok(f"Bucket emptied (queued or done): {name}")
        except Exception as exc:
            _err(f"empty bucket {name}: {exc}")

    if dry:
        _info("(dry-run — buckets not emptied)")


# ── 3. Redis (e.g. Upstash) ───────────────────────────────────────────────────


def _upstash_rest_command(
    rest_base: str,
    token: str,
    command: list[object],
    *,
    timeout_s: float = 20.0,
    connect_timeout_s: float = 5.0,
) -> dict:
    """POST JSON array command to Upstash REST root URL (no redis-py import).

    Prefer curl when available: urllib on some macOS setups can hang during TLS
    connect; curl honors --connect-timeout / -m reliably.
    """
    url = rest_base.strip().rstrip("/")
    body_json = json.dumps(command)
    curl_bin = shutil.which("curl")
    if curl_bin:
        max_total = max(int(timeout_s), 1)
        connect = max(int(connect_timeout_s), 1)
        try:
            p = subprocess.run(
                [
                    curl_bin,
                    "-sS",
                    "--connect-timeout",
                    str(connect),
                    "-m",
                    str(max_total),
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
                timeout=float(max_total + connect + 5),
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"curl timed out (>{max_total}s)") from exc
        if p.returncode != 0:
            msg = (p.stderr or p.stdout or "curl failed").strip()
            raise RuntimeError(msg[:2000])
        raw = p.stdout.encode("utf-8")
    else:
        body = body_json.encode("utf-8")
        req = Request(url, data=body, method="POST")
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("Content-Type", "application/json")
        ctx = ssl.create_default_context()
        try:
            with urlopen(req, timeout=timeout_s, context=ctx) as resp:
                raw = resp.read()
        except HTTPError as e:
            detail = ""
            if e.fp is not None:
                try:
                    detail = e.read().decode("utf-8", errors="replace")
                except Exception:
                    detail = ""
            raise RuntimeError(f"HTTP {e.code} {e.reason}: {detail}") from e
        except URLError as e:
            raise RuntimeError(f"{e}") from e
    obj = json.loads(raw.decode("utf-8"))
    if not isinstance(obj, dict):
        raise RuntimeError(f"unexpected response: {obj!r}")
    if obj.get("error") is not None:
        raise RuntimeError(str(obj["error"]))
    return obj


def _redis_cli_run(tcp_url: str, *args: str, timeout_s: float = 45.0) -> str:
    """Run redis-cli -u URL … (optional fallback; avoids redis-py import)."""
    p = subprocess.run(
        ["redis-cli", "-u", tcp_url, *args],
        capture_output=True,
        text=True,
        timeout=timeout_s,
    )
    if p.returncode != 0:
        raise RuntimeError((p.stderr or p.stdout or "redis-cli failed").strip())
    return (p.stdout or "").strip()


def clean_redis(dry: bool, skip_redis: bool = False) -> None:
    _hr("Redis (Upstash REST or redis-cli)")

    if skip_redis:
        _warn("Skipping Redis (--skip-redis).")
        return

    rest_url = (os.getenv("UPSTASH_REDIS_REST_URL") or "").strip().strip('"').strip("'")
    rest_token = (os.getenv("UPSTASH_REDIS_REST_TOKEN") or "").strip().strip('"').strip("'")
    tcp_url = (os.getenv("UPSTASH_REDIS_URL") or os.getenv("REDIS_URL") or "").strip().strip('"').strip("'")

    if not tcp_url and not (rest_url and rest_token):
        _warn("UPSTASH_REDIS_REST_URL + TOKEN or UPSTASH_REDIS_URL / REDIS_URL not set — skipping.")
        return

    cli = shutil.which("redis-cli")

    # Prefer TCP + redis-cli first: HTTPS to Upstash REST can hang on connect on some networks.
    if tcp_url and cli:
        try:
            _info("DBSIZE via redis-cli (TCP)…")
            n = int(_redis_cli_run(tcp_url, "DBSIZE", timeout_s=15.0))
        except Exception as exc:
            _warn(f"redis-cli DBSIZE: {exc}")
            if not (rest_url and rest_token):
                _err("No Upstash REST fallback — skipping Redis.")
                return
            _info("Falling back to Upstash REST…")
        else:
            _info(f"{'would remove' if dry else 'removing'} {n} key(s) (FLUSHDB)")
            if dry:
                _info("(dry-run — keys not deleted)")
                return
            if n == 0:
                _ok("Redis already empty (skipped FLUSHDB).")
                return
            try:
                _redis_cli_run(tcp_url, "FLUSHDB", timeout_s=25.0)
                _ok("Redis FLUSHDB completed (redis-cli).")
            except Exception as exc:
                _err(f"redis-cli FLUSHDB: {exc}")
            return

    # Upstash REST (curl preferred inside _upstash_rest_command).
    if rest_url and rest_token:
        try:
            _info("DBSIZE via Upstash REST…")
            r = _upstash_rest_command(rest_url, rest_token, ["DBSIZE"], timeout_s=20.0)
            res = r.get("result")
            n = int(res) if isinstance(res, (int, float)) else int(res or 0)
        except Exception as exc:
            _err(f"Upstash REST DBSIZE: {exc}")
            return

        _info(f"{'would remove' if dry else 'removing'} {n} key(s) (FLUSHDB)")
        if dry:
            _info("(dry-run — keys not deleted)")
            return

        if n == 0:
            _ok("Redis already empty (skipped FLUSHDB — avoids slow/blocked FLUSHDB on some hosts).")
            return

        try:
            _upstash_rest_command(rest_url, rest_token, ["FLUSHDB"], timeout_s=25.0)
            _ok("Redis FLUSHDB completed (Upstash REST).")
        except Exception as exc:
            _err(f"Upstash REST FLUSHDB: {exc}")
        return

    _warn("Install redis-cli for UPSTASH_REDIS_URL / REDIS_URL, or set UPSTASH_REDIS_REST_URL + TOKEN.")
    _warn("Skipping Redis (redis-py import disabled here).")


# ── 4–5. Firebase Auth + Firestore (REST; no firebase_admin / no PyJWT) ───────
# Identity Toolkit / Firestore REST:
#   https://cloud.google.com/identity-platform/docs/reference/rest/v1/projects.accounts/query
#   https://firebase.google.com/docs/firestore/reference/rest/v1/projects.databases.documents
# OAuth JWT is signed with `openssl` (RSA-SHA256) so we never import jwt/cryptography.
# Deletes only Auth users and Firestore documents — not databases, buckets, or projects.


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _gcp_jwt_assertion_openssl(cred_dict: dict) -> str:
    """RS256-signed JWT for service-account OAuth using openssl (avoids PyJWT import)."""
    openssl = shutil.which("openssl")
    if not openssl:
        raise RuntimeError("openssl not in PATH (needed to sign the OAuth JWT without PyJWT).")

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
            err = (p.stderr or p.stdout or b"").decode("utf-8", errors="replace")
            raise RuntimeError(f"openssl sign failed: {err}")
        sig = _b64url_encode(p.stdout)
    finally:
        try:
            os.unlink(key_path)
        except OSError:
            pass

    return f"{signing_input}.{sig}"


def _gcp_access_token_from_service_account(cred_dict: dict) -> str:
    """OAuth2 access token via JWT bearer (service account)."""
    assertion = _gcp_jwt_assertion_openssl(cred_dict)

    body = urlencode(
        {
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": assertion,
        }
    ).encode("utf-8")
    req = Request("https://oauth2.googleapis.com/token", data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    ctx = ssl.create_default_context()
    try:
        with urlopen(req, timeout=30.0, context=ctx) as resp:
            raw = resp.read()
    except HTTPError as e:
        detail = ""
        if e.fp is not None:
            try:
                detail = e.read().decode("utf-8", errors="replace")
            except Exception:
                detail = ""
        raise RuntimeError(f"HTTP {e.code} {e.reason}: {detail}") from e
    except URLError as e:
        raise RuntimeError(f"{e}") from e
    obj = json.loads(raw.decode("utf-8"))
    token = obj.get("access_token")
    if not token:
        raise RuntimeError(f"no access_token in OAuth response: {obj!r}")
    return str(token)


def _google_rest_json(
    method: str,
    url: str,
    *,
    token: str,
    body: dict | None = None,
    timeout_s: float = 60.0,
) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    ctx = ssl.create_default_context()
    try:
        with urlopen(req, timeout=timeout_s, context=ctx) as resp:
            raw = resp.read()
    except HTTPError as e:
        detail = ""
        if e.fp is not None:
            try:
                detail = e.read().decode("utf-8", errors="replace")
            except Exception:
                detail = ""
        raise RuntimeError(f"HTTP {e.code} {e.reason}: {detail}") from e
    except URLError as e:
        raise RuntimeError(f"{e}") from e
    if not raw:
        return {}
    return json.loads(raw.decode("utf-8"))


def _firestore_rest_v1_resource_url(resource_name: str) -> str:
    """Encode Firestore resource name for https://firestore.googleapis.com/v1/{name}."""
    parts = resource_name.split("/")
    enc = "/".join(quote(p, safe="") for p in parts)
    return f"https://firestore.googleapis.com/v1/{enc}"


def clean_firebase_auth(dry: bool) -> None:
    _hr("Firebase Auth")

    cred_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY_JSON", "").strip()
    if not cred_json:
        _warn("FIREBASE_SERVICE_ACCOUNT_KEY_JSON not set.")
        print()
        print("  To delete Firebase Auth users manually:")
        print("    1. Open  https://console.firebase.google.com")
        print("    2. Select project: bastionfed")
        print("    3. Authentication → Users tab")
        print("    4. Tick the checkbox in the header row (select all)")
        print("    5. Click 'Delete account' in the action bar → confirm")
        print()
        return

    try:
        cred_dict = json.loads(cred_json)
    except json.JSONDecodeError as exc:
        _err(f"FIREBASE_SERVICE_ACCOUNT_KEY_JSON is not valid JSON: {exc}")
        return

    project_id = cred_dict.get("project_id")
    if not project_id:
        _err("Service account JSON missing project_id.")
        return

    try:
        token = _gcp_access_token_from_service_account(cred_dict)
    except Exception as exc:
        _err(f"OAuth token ({exc})")
        return

    _info("Listing Auth users (Identity Toolkit REST)…")
    uids: list[str] = []
    labels: list[str] = []
    offset = 0
    page_limit = 500
    while True:
        try:
            resp = _google_rest_json(
                "POST",
                f"https://identitytoolkit.googleapis.com/v1/projects/{project_id}/accounts:query",
                token=token,
                body={
                    "returnUserInfo": True,
                    "limit": str(page_limit),
                    "offset": str(offset),
                },
                timeout_s=60.0,
            )
        except Exception as exc:
            _err(f"accounts:query: {exc}")
            return

        batch = resp.get("userInfo") or []
        if not batch:
            break

        for u in batch:
            uid = u.get("localId") or u.get("local_id")
            if not uid:
                continue
            uids.append(uid)
            email = u.get("email") or ""
            labels.append(f"{email or uid}")

        offset += len(batch)
        if len(batch) < page_limit:
            break

    for uid, label in zip(uids, labels):
        _info(f"{'would delete' if dry else 'deleting'} Auth user: {label}")

    if not uids:
        _ok("No Firebase Auth users found.")
        return

    if dry:
        _info(f"(dry-run — {len(uids)} user(s) would be deleted)")
        return

    deleted = 0
    for i in range(0, len(uids), 1000):
        chunk = uids[i : i + 1000]
        try:
            r = _google_rest_json(
                "POST",
                f"https://identitytoolkit.googleapis.com/v1/projects/{project_id}/accounts:batchDelete",
                token=token,
                body={"localIds": chunk, "force": True},
                timeout_s=120.0,
            )
        except Exception as exc:
            _err(f"accounts:batchDelete: {exc}")
            continue
        errors = r.get("errors") or []
        if errors:
            for e in errors[:20]:
                _warn(f"batchDelete error: {e}")
            if len(errors) > 20:
                _warn(f"… and {len(errors) - 20} more batchDelete error(s)")
        deleted += int(r.get("successCount", len(chunk) - len(errors)))

    _ok(f"Deleted {deleted} Firebase Auth user(s).")


# ── 5. Firestore ───────────────────────────────────────────────────────────────

_FIRESTORE_COLLECTIONS = ["users"]


def clean_firestore(dry: bool) -> None:
    _hr("Firestore")

    cred_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY_JSON", "").strip()
    if not cred_json:
        _warn("FIREBASE_SERVICE_ACCOUNT_KEY_JSON not set — skipping.")
        print("  To clean manually: Firebase Console → Firestore → 'users' collection → delete all docs.")
        return

    try:
        cred_dict = json.loads(cred_json)
    except json.JSONDecodeError as exc:
        _err(f"FIREBASE_SERVICE_ACCOUNT_KEY_JSON is not valid JSON: {exc}")
        return

    project_id = cred_dict.get("project_id")
    if not project_id:
        _err("Service account JSON missing project_id.")
        return

    try:
        token = _gcp_access_token_from_service_account(cred_dict)
    except Exception as exc:
        _err(f"OAuth token ({exc})")
        return

    total = 0
    for col in _FIRESTORE_COLLECTIONS:
        db_seg = quote("(default)", safe="")
        list_url = (
            f"https://firestore.googleapis.com/v1/projects/{quote(project_id, safe='')}"
            f"/databases/{db_seg}/documents/{quote(col, safe='')}"
        )
        page_token: str | None = None
        doc_ids: list[str] = []
        while True:
            q = "pageSize=300"
            if page_token:
                q += f"&pageToken={quote(page_token, safe='')}"
            try:
                resp = _google_rest_json(
                    "GET",
                    f"{list_url}?{q}",
                    token=token,
                    body=None,
                    timeout_s=60.0,
                )
            except Exception as exc:
                _err(f"Firestore list {col}: {exc}")
                break

            for doc in resp.get("documents") or []:
                name = doc.get("name") or ""
                if not name:
                    continue
                seg = name.rsplit("/", 1)[-1]
                doc_ids.append(name)
                _info(f"{'would delete' if dry else 'deleting'} Firestore {col}/{seg}")

            page_token = resp.get("nextPageToken")
            if not page_token:
                break

        if not doc_ids:
            _info(f"Collection '{col}' is already empty (no documents).")

        if not dry:
            for name in doc_ids:
                del_url = _firestore_rest_v1_resource_url(name)
                try:
                    _google_rest_json("DELETE", del_url, token=token, body=None, timeout_s=60.0)
                except Exception as exc:
                    _err(f"delete {name}: {exc}")

        total += len(doc_ids)

    if dry:
        _info(f"(dry-run — {total} Firestore document(s) would be deleted)")
    else:
        _ok(f"Deleted {total} Firestore document(s).")


# ── Main ───────────────────────────────────────────────────────────────────────

# def main(
#     dry: bool,
#     supabase_redis_only: bool,
#     skip_redis: bool = False,
#     postgres_auth_only: bool = False,
#     firebase_only: bool = False,
# ) -> None:
#     print()
#     if dry:
#         print("  ⚡ DRY RUN — nothing will be deleted.  Re-run with  --yes  to commit.")
#     else:
#         print("  🗑  LIVE DELETE — data will be permanently removed.")
#     if firebase_only and not dry:
#         print("  (Firebase Auth + Firestore only — Postgres / Storage / Redis unchanged.)\n")
#     elif postgres_auth_only and not dry:
#         print("  (Postgres auth tables only — tenants / product data / Firebase unchanged.)\n")
#     elif supabase_redis_only and not dry:
#         print("  (Supabase + Redis only — Firebase / Firestore skipped.)\n")

#     if firebase_only:
#         clean_firebase_auth(dry)
#         clean_firestore(dry)
#         _hr()
#         if dry:
#             print("  Dry run complete.  Pass  --yes  to actually delete.\n")
#         else:
#             print("  Firebase-only cleanup finished.\n")
#         return

#     if postgres_auth_only:
#         clean_postgres_auth_only(dry)
#         _hr()
#         if dry:
#             print("  Dry run complete.  Pass  --yes  to actually delete.\n")
#         else:
#             print("  Postgres auth-only cleanup finished.\n")
#         return

#     clean_postgres(dry)
#     clean_supabase_storage(dry)
#     clean_redis(dry, skip_redis=skip_redis)
#     if not supabase_redis_only:
#         clean_firebase_auth(dry)
#         clean_firestore(dry)

#     _hr()
#     if dry:
#         print("  Dry run complete.  Pass  --yes  to actually delete.\n")
#     else:
#         if supabase_redis_only:
#             print("  Supabase + Redis cleanup finished.\n")
#         else:
#             print("  All done.  BastionFed data has been wiped.\n")


# if __name__ == "__main__":
#     parser = argparse.ArgumentParser(
#         description="Wipe all BastionFed development data (dry-run by default).",
#     )
#     parser.add_argument(
#         "--yes",
#         action="store_true",
#         help="Actually delete. Omit this flag for a safe dry-run.",
#     )
#     parser.add_argument(
#         "--supabase-redis-only",
#         action="store_true",
#         help="Only wipe Postgres, Storage buckets, and Redis; skip Firebase Auth and Firestore.",
#     )
#     parser.add_argument(
#         "--skip-redis",
#         action="store_true",
#         help="Skip Redis cleanup (use if Upstash REST or TCP hangs).",
#     )
#     parser.add_argument(
#         "--postgres-auth-only",
#         action="store_true",
#         help="Only clear Postgres users, memberships, client scopes, and invites (keeps tenants and app data).",
#     )
#     parser.add_argument(
#         "--firebase-only",
#         action="store_true",
#         help="Only wipe Firebase Auth users and Firestore documents; skip Postgres, Storage, and Redis.",
#     )
#     args = parser.parse_args()
#     if args.postgres_auth_only and args.supabase_redis_only:
#         parser.error("--postgres-auth-only cannot be combined with --supabase-redis-only")
#     if args.firebase_only and (args.supabase_redis_only or args.postgres_auth_only):
#         parser.error("--firebase-only cannot be combined with --supabase-redis-only or --postgres-auth-only")
#     main(
#         dry=not args.yes,
#         supabase_redis_only=args.supabase_redis_only,
#         skip_redis=args.skip_redis,
#         postgres_auth_only=args.postgres_auth_only,
#         firebase_only=args.firebase_only,
#     )

def main(
    dry: bool,
    supabase_redis_only: bool,
    skip_redis: bool = False,
    postgres_auth_only: bool = False,
    firebase_only: bool = False,
    redis_only: bool = False,
) -> None:
    print()
    if dry:
        print("  ⚡ DRY RUN — nothing will be deleted.  Re-run with  --yes  to commit.")
    else:
        print("  🗑  LIVE DELETE — data will be permanently removed.")
    if redis_only and not dry:
        print("  (Redis only — Postgres / Storage / Firebase / Firestore unchanged.)\n")
    elif firebase_only and not dry:
        print("  (Firebase Auth + Firestore only — Postgres / Storage / Redis unchanged.)\n")
    elif postgres_auth_only and not dry:
        print("  (Postgres auth tables only — tenants / product data / Firebase unchanged.)\n")
    elif supabase_redis_only and not dry:
        print("  (Supabase + Redis only — Firebase / Firestore skipped.)\n")

    if redis_only:
        clean_redis(dry, skip_redis=False)
        _hr()
        if dry:
            print("  Dry run complete.  Pass  --yes  to actually delete.\n")
        else:
            print("  Redis-only cleanup finished.\n")
        return

    if firebase_only:
        clean_firebase_auth(dry)
        clean_firestore(dry)
        _hr()
        if dry:
            print("  Dry run complete.  Pass  --yes  to actually delete.\n")
        else:
            print("  Firebase-only cleanup finished.\n")
        return

    if postgres_auth_only:
        clean_postgres_auth_only(dry)
        _hr()
        if dry:
            print("  Dry run complete.  Pass  --yes  to actually delete.\n")
        else:
            print("  Postgres auth-only cleanup finished.\n")
        return

    clean_postgres(dry)
    clean_supabase_storage(dry)
    clean_redis(dry, skip_redis=skip_redis)
    if not supabase_redis_only:
        clean_firebase_auth(dry)
        clean_firestore(dry)

    _hr()
    if dry:
        print("  Dry run complete.  Pass  --yes  to actually delete.\n")
    else:
        if supabase_redis_only:
            print("  Supabase + Redis cleanup finished.\n")
        else:
            print("  All done.  BastionFed data has been wiped.\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Wipe all BastionFed development data (dry-run by default).",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Actually delete. Omit this flag for a safe dry-run.",
    )
    parser.add_argument(
        "--supabase-redis-only",
        action="store_true",
        help="Only wipe Postgres, Storage buckets, and Redis; skip Firebase Auth and Firestore.",
    )
    parser.add_argument(
        "--skip-redis",
        action="store_true",
        help="Skip Redis cleanup (use if Upstash REST or TCP hangs).",
    )
    parser.add_argument(
        "--postgres-auth-only",
        action="store_true",
        help="Only clear Postgres users, memberships, client scopes, and invites (keeps tenants and app data).",
    )
    parser.add_argument(
        "--firebase-only",
        action="store_true",
        help="Only wipe Firebase Auth users and Firestore documents; skip Postgres, Storage, and Redis.",
    )
    parser.add_argument(
        "--redis-only",
        action="store_true",
        help="Only flush Redis; skip Postgres, Storage, Firebase Auth, and Firestore.",
    )
    args = parser.parse_args()
    if args.postgres_auth_only and args.supabase_redis_only:
        parser.error("--postgres-auth-only cannot be combined with --supabase-redis-only")
    if args.firebase_only and (args.supabase_redis_only or args.postgres_auth_only):
        parser.error("--firebase-only cannot be combined with --supabase-redis-only or --postgres-auth-only")
    if args.redis_only and (args.supabase_redis_only or args.postgres_auth_only or args.firebase_only or args.skip_redis):
        parser.error("--redis-only cannot be combined with --supabase-redis-only, --postgres-auth-only, --firebase-only, or --skip-redis")
    main(
        dry=not args.yes,
        supabase_redis_only=args.supabase_redis_only,
        skip_redis=args.skip_redis,
        postgres_auth_only=args.postgres_auth_only,
        firebase_only=args.firebase_only,
        redis_only=args.redis_only,
    )