# Local `backend/data/` layout (not in Git)

The directory **`backend/data/`** holds machine-local artifacts: model weights, SQLite, ingest drops, and other bulky or sensitive files. It is **gitignored** at the repo root (`.gitignore`: `backend/data/`) so clones stay small and secrets or `.pth` blobs are not pushed.

After cloning, create the tree on disk (empty dirs are fine until you add files). All paths below are relative to **`backend/`** when you run scripts or `dev_server.py` from the `backend/` folder.

## Directory tree

```text
backend/data/
├── runtime/                      # BastionBot + local SQLite (default BASTIONBOT_DB_PATH)
│   └── bastionbot.sqlite3
├── models/                       # Canonical ML weights + drift reference (see subtree)
│   ├── README.md                 # optional local notes (not tracked if entire data/ ignored)
│   ├── drift/
│   │   └── drift_reference.npz
│   └── pytorch/
│       └── global/
│           ├── fl_global_resnet.pth
│           ├── fl_global_resnet_fp16.pth   # optional FP16 export (~half size)
│           ├── fl_global_dnn.pth
│           └── fl_global_meta.pth
└── batch_ingest/                 # per-client JSON / features for `scripts/ingest_client_data.py`
    ├── client_1/
    ├── client_2/
    └── …
```

## Symlinks (Hunain inference)

The unified Hunain stack loads weights from **`hunain_implementation/app/ml/weights/`**. Point those files (or symlinks) at the copies under **`backend/data/models/`** so a single canonical tree owns the binaries. Inference code: `hunain_implementation/app/ml/inference.py` (`WEIGHTS_DIR`).

## Scripts that read this tree

| Script / code | Uses |
|---------------|------|
| `scripts/upload_generic_models_to_storage.py` | `data/models/` only → Supabase `models` bucket |
| `scripts/quantize_resnet_fp16.py` | `data/models/pytorch/global/fl_global_resnet.pth` |
| `app/store/tenant_store.py` (`sync_global_model_bundles_from_disk`) | Same `data/models/` layout |
| `scripts/ingest_client_data.py` | Default `--ingest-root` = `backend/data/batch_ingest` |
| `app/config.py` / `BASTIONBOT_DB_PATH` | Default `data/runtime/bastionbot.sqlite3` |

## `batch_ingest` sampling (short)

Place files under `data/batch_ingest/client_N/` (see `scripts/ingest_client_data.py` docstring). The script ingests a deterministic **25%** sample of files per folder (sorted by path). JSON and non-JSON rules are described in that script.

## Legacy paths (do not use for new work)

| Path | Notes |
|------|-------|
| `FL/` (repo root) | Old research notebook, CSV, and weight copies — **gitignored**; use `backend/data/models/` instead |
| `backend/Fyp2demo/` | Local forensics demo PNG/JSON drops — **gitignored** |

## Related docs

- Setup: root **`SETUP_GUIDE.md`** (local data + env vars).
- Data plane: **`docs/FIREBASE_DATA_PLANE_MAPPING.md`**.
