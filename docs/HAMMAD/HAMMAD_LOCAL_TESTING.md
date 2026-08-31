# Hammad — local testing

> **Use the unified backend for day-to-day work.** See [docs/LOCAL_TESTING.md](../LOCAL_TESTING.md).

This file is kept for reference when running **`backend/hammad_implementation/`** in isolation.

```bash
cd backend/hammad_implementation
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest -q
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

See also [HAMMAD_BACKEND_IMPLEMENTATION.md](./HAMMAD_BACKEND_IMPLEMENTATION.md).
