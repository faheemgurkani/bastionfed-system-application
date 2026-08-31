# Faheem — local testing

> **Use the unified backend for day-to-day work.** See [docs/LOCAL_TESTING.md](../LOCAL_TESTING.md).

This file is kept for reference when running **`backend/faheem_implementation/`** in isolation.

```bash
cd backend/faheem_implementation
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest tests/test_faheem_endpoints.py -q
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The standalone fork does **not** include all Hunain/Hammad routes. For full UI coverage, run the unified backend from `backend/` instead.

See also [FAHEEM_BACKEND_IMPLEMENTATION.md](./FAHEEM_BACKEND_IMPLEMENTATION.md).
