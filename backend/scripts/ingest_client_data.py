#!/usr/bin/env python3
"""
Ingest a 25% sample of per-client data files into BastionFed (Supabase/Postgres).

Convention
----------
- Place raw JSON files under ``backend/data/batch_ingest/client_1``, ``client_2``, … — one folder per
  **DEVICE**-type FL client, in the same order as ``fl_clients.id`` sorted ascending
  (only DEVICE rows are mapped; PERSON clients are skipped — they do not own IoT devices).
- Each **file** is one ingest unit. The script takes the first ``ceil(0.25 * N)`` files
  (sorted by path) deterministically.
- Files may live in subfolders (e.g. ``benign/``, ``malware/``); all files are discovered
  recursively, sorted by path, then the first ``ceil(25% × N)`` are ingested.
- **JSON** files: ``{"eventType": "alert"|"ticket", "payload": { ... }}`` or a flat alert
  payload; ``flClientId`` is forced to the mapped client.
- **Non-JSON** (e.g. ``.png`` image features): ingested as synthetic **alert** rows with
  metadata (path, benign/malware label from parent folder); binary file content is not
  stored in Postgres (only references / device stubs for threat-map scoping).

Requires DATABASE_URL (or SUPABASE_DATABASE_URL), and uses ``PostgresTenantStore``.

Usage::

  cd backend && python scripts/ingest_client_data.py --tenant-id <uuid> [--dry-run]

  # or resolve tenant by slug (from ``tenants.slug``)::

  python scripts/ingest_client_data.py --tenant-slug my-org-slug
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

# Ensure backend package is importable
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.config import settings  # noqa: E402
from app.store.tenant_store import PostgresTenantStore  # noqa: E402


def _find_env() -> Path:
    p = _BACKEND_ROOT / ".env"
    if p.exists():
        return p
    return Path(__file__).resolve().parent / ".env"


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv(_find_env())
    except ImportError:
        env = _find_env()
        if env.exists():
            import os

            for line in env.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _resolve_tenant_id(store: PostgresTenantStore, tenant_id: str | None, slug: str | None) -> str | None:
    if tenant_id:
        with store._connect() as conn, conn.cursor() as cur:  # noqa: SLF001
            cur.execute("SELECT id FROM tenants WHERE id = %s", (tenant_id,))
            row = cur.fetchone()
        return str(row["id"]) if row else None
    if slug:
        with store._connect() as conn, conn.cursor() as cur:  # noqa: SLF001
            cur.execute("SELECT id FROM tenants WHERE slug = %s", (slug,))
            row = cur.fetchone()
        return str(row["id"]) if row else None
    return None


def _device_clients_ordered(store: PostgresTenantStore, tenant_id: str) -> list[str]:
    clients = store.list_fl_clients(tenant_id)
    device_ids = [
        c.id
        for c in clients
        if str(getattr(c.client_type, "value", c.client_type)) == "DEVICE"
    ]
    return sorted(device_ids)


def _collect_data_files(client_folder: Path) -> list[Path]:
    """All regular files under client_N (recursive), excluding dotfiles."""
    out: list[Path] = []
    if not client_folder.is_dir():
        return out
    for p in client_folder.rglob("*"):
        if not p.is_file():
            continue
        if p.name.startswith(".") or p.name == ".gitkeep":
            continue
        out.append(p)
    out.sort(key=lambda x: x.as_posix().lower())
    return out


def _sample_files(files: list[Path]) -> list[Path]:
    n = len(files)
    if n == 0:
        return []
    take = max(1, math.ceil(0.25 * n))
    return files[:take]


def _label_from_path(rel: Path) -> str:
    parts = rel.parts
    if len(parts) >= 1 and parts[0].lower() in ("benign", "malware"):
        return parts[0].lower()
    return "unknown"


def _synthetic_alert_payload(
    fpath: Path,
    client_folder: Path,
    fl_client_id: str,
) -> dict[str, object]:
    """PNG/other binaries: metadata-only alert for dataset provenance + scoping."""
    try:
        rel = fpath.relative_to(client_folder)
    except ValueError:
        rel = Path(fpath.name)
    label = _label_from_path(rel)
    stem = fpath.stem
    safe_id = "".join(c if c.isalnum() else "-" for c in stem)[:48]
    device_id = f"ds-{safe_id or 'file'}-{hashlib.sha256(str(fpath).encode()).hexdigest()[:8]}"
    return {
        "deviceId": device_id,
        "deviceName": f"Dataset-{label}",
        "ip": "0.0.0.0",
        "wing": label.upper(),
        "deviceType": "DATASET_SAMPLE",
        "deviceStatus": "SUSPICIOUS" if label == "malware" else "NORMAL",
        "alertType": "DATASET_FILE_INGEST",
        "summary": f"Sample ({label}): {rel.as_posix()}",
        "severity": "HIGH" if label == "malware" else "LOW",
        "confidence": 0.85 if label == "malware" else 0.2,
        "tactic": "Collection",
        "techniqueName": "Automated Dataset Ingest",
        "techniqueId": "T1530",
        "flClientId": fl_client_id,
        "sourceRef": rel.as_posix(),
    }


def _build_event_from_json(data: dict, fl_client_id: str) -> tuple[str, dict[str, object]]:
    """Return (event_type, payload) for ingest_event."""
    if "eventType" in data and "payload" in data and isinstance(data["payload"], dict):
        et = str(data["eventType"]).lower()
        payload = dict(data["payload"])
    else:
        et = str(data.get("eventType") or "alert").lower()
        payload = dict(data)
    payload["flClientId"] = fl_client_id
    if et not in ("alert", "ticket"):
        et = "alert"
    return et, payload


def main() -> int:
    _load_dotenv()
    parser = argparse.ArgumentParser(description="Ingest 25% of client data files per folder.")
    parser.add_argument("--tenant-id", default=None, help="Tenant UUID")
    parser.add_argument("--tenant-slug", default=None, help="Tenant slug (alternative to --tenant-id)")
    parser.add_argument(
        "--data-root",
        default=str(_BACKEND_ROOT / "data" / "batch_ingest"),
        help="Root folder containing client_1, client_2, … (default: data/batch_ingest)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print actions only; no DB writes")
    parser.add_argument(
        "--list-tenants",
        action="store_true",
        help="Print tenant id and slug from DB, then exit",
    )
    args = parser.parse_args()

    if not settings.database_url:
        print("ERROR: DATABASE_URL / SUPABASE_DATABASE_URL not set.", file=sys.stderr)
        return 1

    store = PostgresTenantStore(settings.database_url)
    if args.list_tenants:
        with store._connect() as conn, conn.cursor() as cur:  # noqa: SLF001
            cur.execute("SELECT id, slug, name FROM tenants ORDER BY id ASC")
            rows = cur.fetchall()
        for row in rows:
            print(f"{row['id']}\t{row['slug']}\t{row['name']}")
        return 0

    tid = _resolve_tenant_id(store, args.tenant_id, args.tenant_slug)
    if not tid:
        print("ERROR: Tenant not found (check --tenant-id or --tenant-slug).", file=sys.stderr)
        return 1

    device_client_ids = _device_clients_ordered(store, tid)
    if not device_client_ids:
        print("ERROR: No DEVICE-type fl_clients for this tenant; nothing to map folders to.", file=sys.stderr)
        return 1

    data_root = Path(args.data_root)
    source = None
    secret = None
    if not args.dry_run:
        source, secret = store.create_ingest_source(
            tid,
            name="Client data batch (script)",
            source_type="CLIENT_DATA",
            connector_kind="FILE_BATCH",
            actor_uid="system-script",
        )
        print(f"Ingest source: {source.id} (store this secret securely if re-running outside dry-run)")

    total_ingested = 0
    for idx, fl_id in enumerate(device_client_ids):
        folder = data_root / f"client_{idx + 1}"
        if not folder.is_dir():
            print(f"Skip: no folder {folder} for fl_client {fl_id}")
            continue
        all_files = _collect_data_files(folder)
        sampled = _sample_files(all_files)
        print(
            f"Folder {folder.name} -> fl_client_id={fl_id}: "
            f"{len(sampled)} / {len(all_files)} files (25% sample)"
        )
        for fpath in sampled:
            ext = fpath.suffix.lower()
            ext_id = hashlib.sha256(f"{tid}:{fl_id}:{fpath.resolve()}".encode()).hexdigest()[:40]
            try:
                if ext in (".json", ".ndjson"):
                    raw = fpath.read_text(encoding="utf-8", errors="replace")
                    data = json.loads(raw)
                    if not isinstance(data, dict):
                        print(f"  skip (root not object): {fpath.name}")
                        continue
                    event_type, payload = _build_event_from_json(data, fl_id)
                else:
                    event_type = "alert"
                    payload = _synthetic_alert_payload(fpath, folder, fl_id)
                external_id = f"cd-{ext_id}"
                if args.dry_run:
                    print(f"  [dry-run] {fpath.relative_to(folder)} -> {event_type}")
                    continue
                assert source is not None and secret is not None
                result = store.ingest_event(
                    source_id=source.id,
                    source_secret=secret,
                    external_id=external_id,
                    event_type=event_type,
                    payload=payload,
                    occurred_at=None,
                )
                if result:
                    total_ingested += 1
                    if total_ingested % 200 == 0:
                        print(f"  ... {total_ingested} events so far ({folder.name})")
                else:
                    print(f"  FAIL {fpath.name} (ingest returned None)", file=sys.stderr)
            except json.JSONDecodeError as e:
                print(f"  skip invalid JSON {fpath.name}: {e}", file=sys.stderr)
            except Exception as e:  # pragma: no cover
                print(f"  ERROR {fpath}: {e}", file=sys.stderr)

    if not args.dry_run:
        print(f"Done. Ingested events (accepted rows): {total_ingested}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
