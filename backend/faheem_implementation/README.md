# BastionFed FastAPI backend

## Run (development)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API serves at `http://localhost:8000`. Configure the Next.js app with `NEXT_PUBLIC_API_URL=http://localhost:8000`.

## Tests

```bash
cd backend
pytest
```
