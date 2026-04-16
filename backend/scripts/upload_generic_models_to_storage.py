#!/usr/bin/env python3
"""
Upload generic ML artifacts from *only* ``backend/data/models`` into the Supabase ``models`` bucket.

Expected layout (see ``backend/DATA_DIRECTORY.md`` and optional local ``data/models/README.md``):
  - ``drift/drift_reference.npz``
  - ``pytorch/global/*.pth`` (e.g. fl_global_resnet.pth, fl_global_dnn.pth, fl_global_meta.pth)

Objects are written as ``global/<basename>`` (flat keys), matching ``PostgresTenantStore.sync_global_model_bundles_from_disk``.

Supabase Python client pattern (Context7 / supabase-py): ``storage.from_(bucket).upload(path, file, {"upsert": "true"})``.
This script uses the app's ``upload_model_bytes`` helper, which performs the same Storage REST upload
(POST ``/storage/v1/object/{bucket}/{path}`` with ``x-upsert: true`` and ``Content-Type: application/octet-stream``).

Usage (project venv)::

  cd backend
  .venv/bin/python scripts/upload_generic_models_to_storage.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.WARNING, format="%(name)s: %(message)s")
try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# Loads backend/.env via app.config
from app.config import settings  # noqa: E402
from app.services.supabase_storage import upload_model_bytes  # noqa: E402

MODELS_ROOT = BACKEND_ROOT / "data" / "models"


def _candidates() -> list[Path]:
    files: list[Path] = []
    drift = MODELS_ROOT / "drift" / "drift_reference.npz"
    if drift.is_file():
        files.append(drift)
    gdir = MODELS_ROOT / "pytorch" / "global"
    if gdir.is_dir():
        files.extend(sorted(p for p in gdir.glob("*.pth") if p.is_file()))
    return files


def main() -> int:
    if not settings.supabase_storage_enabled:
        print("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set (storage disabled).", file=sys.stderr)
        return 1
    bucket = settings.supabase_models_bucket
    if not MODELS_ROOT.is_dir():
        print(f"Missing models directory: {MODELS_ROOT}", file=sys.stderr)
        return 1
    paths = _candidates()
    if not paths:
        print(f"No weight files found under {MODELS_ROOT} (drift/ or pytorch/global/).", file=sys.stderr)
        return 1
    ok = 0
    failed: list[Path] = []
    for path in paths:
        rel = path.relative_to(MODELS_ROOT)
        if not str(rel).replace("\\", "/").startswith(("drift/", "pytorch/")):
            print(f"Skip (outside allowed subtrees): {path}", file=sys.stderr)
            continue
        data = path.read_bytes()
        object_name = f"global/{path.name}"
        out = upload_model_bytes(data=data, object_name=object_name)
        if not out:
            print(f"FAILED: {path.name} -> {bucket}/{object_name}", file=sys.stderr)
            if len(data) > 45 * 1024 * 1024:
                print(
                    "Hint: object too large for current Supabase Storage limit (response often says "
                    "'Payload too large'). In the dashboard: Project Settings → Storage → increase "
                    "the max upload size, then re-run this script for the failed file(s).",
                    file=sys.stderr,
                )
            failed.append(path)
            continue
        print(f"OK: {path} -> {out}")
        ok += 1
    print(f"Uploaded {ok} file(s) to bucket {bucket!r} under global/.")
    if failed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
