# Contributing to BastionFed

Thank you for helping improve the BastionFed system application. This repo is the **production-style SOC UI + unified FastAPI backend** for the BastionFed FYP.

## Before you start

1. Read [README.md](./README.md) and [SETUP_GUIDE.md](./SETUP_GUIDE.md)
2. Skim [docs/README.md](./docs/README.md) for architecture and runbooks
3. Run the stack locally per [docs/LOCAL_TESTING.md](./docs/LOCAL_TESTING.md)

## How to contribute

### Bug reports and features

Open a **GitHub issue** with:

- Clear title and steps to reproduce (bugs)
- Expected vs actual behavior
- Environment: OS, Node/Python versions, demo vs data-plane mode
- Screenshots or logs when helpful

For **security issues**, see [SECURITY.md](./SECURITY.md) — do not file public issues.

### Pull requests

1. Fork the repo and branch from **`main`**
2. Use descriptive branch names: `fix/audit-export`, `feat/ingest-filter`, `docs/setup-clarity`
3. Keep PRs focused — one logical change per PR when possible
4. Update docs when behavior, env vars, or API contracts change
5. Run checks before requesting review:

```bash
# Backend
cd backend && .venv/bin/python -m pytest -q

# Frontend (lint/build as applicable)
cd frontend && npm run lint && npm run build
```

6. Fill in the PR template (if present) and link related issues

### Code conventions

| Area | Convention |
|------|------------|
| **Backend** | Match existing FastAPI patterns in `backend/app/`; type hints and Pydantic models for API shapes |
| **Frontend** | Next.js App Router, existing component structure under `frontend/components/` |
| **API contracts** | Changes must align with [docs/BACKEND_PRD.md](./docs/BACKEND_PRD.md) or update that doc in the same PR |
| **Commits** | Imperative subject line (`fix:`, `feat:`, `docs:`); complete sentences in body when context is needed |

### Unified backend vs contributor forks

- **Default target:** `backend/` (unified FastAPI)
- **`backend/*_implementation/`** — historical per-member forks; change only when intentionally testing isolated scope
- Merge conflicts and SSE cadence decisions: [docs/UNIFIED_BACKEND_CONFLICTS.md](./docs/UNIFIED_BACKEND_CONFLICTS.md)

### Documentation

- User-facing setup → [SETUP_GUIDE.md](./SETUP_GUIDE.md)
- Technical specs → `docs/`
- New runbooks → add to [docs/README.md](./docs/README.md) index

### Secrets

- Do **not** commit `.env`, `.env.local`, API keys, or malware samples
- Use [frontend/.env.example](./frontend/.env.example) as the template for frontend keys
- Document new env vars in [backend/README.md](./backend/README.md) or [SETUP_GUIDE.md](./SETUP_GUIDE.md)

## Code of conduct

Contributors are expected to follow [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md).

## License

By contributing, you agree that your contributions are licensed under the [MIT License](./LICENSE).
