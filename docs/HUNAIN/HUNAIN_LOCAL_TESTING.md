# Hunain local testing — backend + endpoint checks

## 1) Run backend

```bash
cd "/Users/hunain/SEM 7/FYP/bastionfed-system-application/backend/hunain_implementation"
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Useful URLs:
- `http://localhost:8000/health`
- `http://localhost:8000/docs`

---

## 2) Run automated tests

```bash
cd "/Users/hunain/SEM 7/FYP/bastionfed-system-application/backend/hunain_implementation"
pytest -q
```

Current expected status: **22 passed**

---

## 3) Manual smoke checks (Hunain 12 endpoints)

Base:

```bash
BASE="http://localhost:8000"
TOKEN="test-token"
```

Read routes:

```bash
curl -s "$BASE/api/alerts/ALT-0047?guest=true"
curl -s "$BASE/api/incidents?guest=true"
curl -s "$BASE/api/fl/rounds?guest=true"
curl -s "$BASE/api/fl/clients?guest=true"
curl -s "$BASE/api/forensics/samples/MAL-001?guest=true"
curl -s "$BASE/api/bastionbot/conversations?guest=true"
curl -s "$BASE/api/audit/logs?guest=true&limit=5"
```

Mutation routes:

```bash
curl -s -X POST "$BASE/api/alerts/ALT-0047/escalate" -H "Authorization: Bearer $TOKEN"
curl -s -X POST "$BASE/api/incidents/INC-001/playbook/run" -H "Authorization: Bearer $TOKEN"
curl -s -X POST "$BASE/api/fl/models/v4.2.1-DNN/activate" -H "Authorization: Bearer $TOKEN"
curl -s -X POST "$BASE/api/bastionbot/chat" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message":"What does ALT-0047 indicate?","conversationId":"conv-1","context":{"alertId":"ALT-0047","incidentId":null}}'
```

SSE:

```bash
curl -N "$BASE/api/fl-events?token=$TOKEN"
```

Stop stream with `Ctrl + C`.
