# Hammad local testing — backend + endpoint checks

## 1) Run backend

```bash
cd "/Users/hunain/SEM 7/FYP/bastionfed-system-application/backend/hammad_implementation"
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Useful URLs:
- `http://localhost:8000/health`
- `http://localhost:8000/docs`

---

## 2) Run automated tests

```bash
cd "/Users/hunain/SEM 7/FYP/bastionfed-system-application/backend/hammad_implementation"
pytest -q
```

Current expected status: **23 passed**

---

## 3) Manual smoke checks (Hammad 12 endpoints)

Base:

```bash
BASE="http://localhost:8000"
TOKEN="test-token"
```

Read routes:

```bash
curl -s "$BASE/api/devices?guest=true"
curl -s "$BASE/api/devices/dev-01?guest=true"
curl -s "$BASE/api/fl/drift?guest=true"
curl -s "$BASE/api/fl/models?guest=true"
curl -s "$BASE/api/forensics/rca?guest=true"
curl -s "$BASE/api/bastionbot/conversations/conv-1" \
  -H "Authorization: Bearer $TOKEN"
```

Mutation routes:

```bash
curl -s -X PATCH "$BASE/api/incidents/INC-001" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status":"RESPONDING","assignee":"analyst@bastionfed.ai","notes":"manual update"}'

curl -s -X PATCH "$BASE/api/incidents/INC-001/playbook/steps/s6" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status":"COMPLETED","notes":"done"}'

curl -s -X POST "$BASE/api/incidents/INC-001/playbook/halt" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reason":"manual containment"}'

curl -s -X POST "$BASE/api/forensics/rca" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"incidentId":"INC-001"}'

curl -s -X POST "$BASE/api/network/block-ip" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"ip":"203.0.113.10","reason":"malicious traffic","alertId":"ALT-0047"}'
```

Multipart upload:

```bash
echo "dummy payload" > /tmp/sample.bin
curl -s -X POST "$BASE/api/forensics/samples" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/tmp/sample.bin" \
  -F "deviceId=DEV-001" \
  -F "notes=manual upload test"
```
