# BastionFed — System Application

Blue-team SOC platform for healthcare-style IoMT security: alerts, incidents, federated-learning health, forensics, audit, and BastionBot (analyst copilot).

## Quick start

See **[SETUP_GUIDE.md](./SETUP_GUIDE.md)** for clone, env files, and running frontend + backend locally.

| Component | Path | Docs |
|-----------|------|------|
| **Frontend** | `frontend/` (Next.js) | [frontend/README.md](./frontend/README.md) |
| **Unified API** | `backend/` (FastAPI) | [backend/README.md](./backend/README.md) |
| **All documentation** | `docs/` | [docs/README.md](./docs/README.md) |

## Repository layout

```text
bastionfed-system-application/
├── frontend/          Next.js App Router UI
├── backend/           Unified FastAPI (default entrypoint)
│   ├── app/           Production routers, ML, data plane
│   ├── scripts/       Ingest, model upload, maintenance
│   ├── tests/         Unified pytest suite
│   └── *_implementation/   Historical per-contributor forks (optional standalone runs)
├── docs/              Specs, runbooks, team notes
└── SETUP_GUIDE.md     Onboarding for new developers
```

**Local-only paths (gitignored):** `backend/data/` (weights, SQLite, ingest drops), `backend/Fyp2demo/`, `FL/`, env files. See [backend/DATA_DIRECTORY.md](./backend/DATA_DIRECTORY.md).

## Development commands

```bash
# Frontend (port 3000)
cd frontend && npm install && npm run dev

# Backend (port 8000)
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && .venv/bin/python dev_server.py
```

Set `NEXT_PUBLIC_API_URL=http://localhost:8000` in `frontend/.env.local`.

## Governance

| Document | Purpose |
|----------|---------|
| [LICENSE](./LICENSE) | MIT license |
| [CONTRIBUTING.md](./CONTRIBUTING.md) | How to contribute |
| [SECURITY.md](./SECURITY.md) | Vulnerability reporting and secrets policy |
| [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md) | Community standards |
| [CHANGELOG.md](./CHANGELOG.md) | Release history |
