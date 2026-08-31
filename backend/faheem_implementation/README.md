# Faheem standalone backend (historical fork)

> **Default entrypoint:** use the unified backend at [`../`](../) — see [`../README.md`](../README.md) and [`../../docs/LOCAL_TESTING.md`](../../docs/LOCAL_TESTING.md).

Run this fork only for isolated Faheem-scope pytest:

```bash
cd backend/faheem_implementation
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
pytest tests/test_faheem_endpoints.py -q
```

Set `NEXT_PUBLIC_API_URL=http://localhost:8000` in the frontend. This fork does **not** mount all routes required for full UI coverage.
