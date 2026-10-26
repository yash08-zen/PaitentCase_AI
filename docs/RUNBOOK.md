# RUNBOOK.md — PatientCase AI

## Prerequisites

- Python 3.12+
- Node.js 18+ / npm 10+
- Windows PowerShell (or adapt paths for bash)

---

## 1. Project Locations

- Root: `d:\Projects\New PatientCase AI`
- Backend: `d:\Projects\New PatientCase AI\backend`
- Frontend: `d:\Projects\New PatientCase AI\frontend` (Sole active frontend; old prototype retired to `legacy/frontend`)
- Docs: `d:\Projects\New PatientCase AI\docs`

---

## 2. Backend Setup & Run

Open a PowerShell terminal:

```powershell
cd "d:\Projects\New PatientCase AI\backend"

# 1. Virtual environment & dependencies
.\.venv312\Scripts\Activate.ps1
pip install -r requirements.txt

# 2. Environment configuration (first time)
if (-not (Test-Path .env)) { Copy-Item .env.example .env }

# 3. Database migrations (from clean DB to current schema in one command)
.\.venv312\Scripts\alembic.exe upgrade head

# 4. (Optional) Seed synthetic demo data
.\.venv312\Scripts\python.exe -m app.scripts.seed_demo_e2e

# 5. Start API server
.\.venv312\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Health check endpoints:
- Primary: http://127.0.0.1:8000/health (verifies app + DB status)
- Legacy: http://127.0.0.1:8000/api/health
- Swagger interactive documentation: http://127.0.0.1:8000/docs

---

## 3. Frontend Setup & Run (React + Vite)

Open a second PowerShell terminal:

```powershell
cd "d:\Projects\New PatientCase AI\frontend"

# 1. Environment configuration
if (-not (Test-Path .env)) { Copy-Item .env.example .env }

# 2. Install dependencies (first time only)
npm install

# 3. Start development server
npm run dev
```

Application URL: http://localhost:5173

---

## 4. Run Test Suites

### Backend Tests (pytest)
```powershell
cd "d:\Projects\New PatientCase AI\backend"
.\.venv312\Scripts\python.exe -m pytest -v
```
Expected: **98 passed** (100% green across all backend test suites, including health, RBAC, registration, consent, idempotency, audit, adaptive interview, structured summary, real RapidOCR ONNX inference, medication discrepancy rules, doctor review persistence, rate limiting, air-gapped isolation, multilingual voice, and advanced empirical benchmarks).

### Frontend Tests (vitest)
```powershell
cd "d:\Projects\New PatientCase AI\frontend"
npm run test
```
Expected: **75 passed across 14 test suites** (client.test.js, ui.smoke.test.jsx, auth.smoke.test.jsx, registration.smoke.test.jsx, interview.smoke.test.jsx, summary.smoke.test.jsx, documents.smoke.test.jsx, conflicts.smoke.test.jsx, dashboard_review.smoke.test.jsx, hardening_security.smoke.test.jsx, e2e_p0_workflow.smoke.test.jsx, offline_operation.smoke.test.jsx, multilingual_voice.smoke.test.jsx, advanced_benchmarks.smoke.test.jsx).

**Combined Total: 173 / 173 tests passing (100% Green).**

---

## 5. Demo Accounts (backend)

| Username | Password | Role |
|---|---|---|
| admin | Admin@1234 | admin |
| doctor | Doctor@1234 | doctor |
| staff | Staff@1234 | staff |
| patient | Patient@1234 | patient |

*Change these passwords immediately in any shared environment.*

---

## 6. Verified Ports

| Service | URL | Status |
|---|---|---|
| FastAPI backend | http://127.0.0.1:8000 | Verified running M1 |
| PatientCase-Seminar frontend | http://localhost:5173 | Verified running M1 |

---

## 7. Milestone 8 Verification (Doctor Review & Persistence)

1. **Doctor records clinical notes:**
   ```bash
   PUT /api/encounters/{id}/notes
   Headers: Authorization: Bearer <doctor_token>
   Body: {"doctor_notes": "Clinical assessment complete. Patient advised follow-up."}
   ```
2. **Doctor finalizes intake review:**
   ```bash
   POST /api/encounters/{id}/finalize
   Headers: Authorization: Bearer <doctor_token>
   Body: {"doctor_notes": "Case finalized and verified."}
   ```
3. **Verify interview locking:**
   ```bash
   POST /api/interviews/{id}/responses
   Headers: Authorization: Bearer <patient_token>
   Body: {"question_key": "symptom_duration", "answer": "1 week"}
   # Returns 400 Bad Request: "Cannot modify responses for a finalized encounter"
   ```
4. **Dashboard queue and statistics:**
   ```bash
   GET /api/dashboard/summary
   GET /api/dashboard/cases?status=needs_review
   GET /api/dashboard/cases?status=all&search=John
   ```

---

## 8. Milestone 9 Verification (Hardening, Security & Resilience)

1. **Defensive security headers on any response:**
   ```bash
   curl -I http://127.0.0.1:8000/health
   # Verify X-Content-Type-Options: nosniff
   # Verify X-Frame-Options: DENY
   # Verify X-XSS-Protection: 1; mode=block
   # Verify Content-Security-Policy: frame-ancestors 'none'
   ```
2. **Rate limiting trigger & Retry-After:**
   ```bash
   # Rapid requests to /api/auth/login triggers HTTP 429 Too Many Requests with Retry-After: <seconds>
   ```
3. **Safe unhandled 500 error (no stack trace leak):**
   ```bash
   # Unhandled exceptions return {"detail": "...", "error_code": "INTERNAL_SERVER_ERROR"} without tracebacks
   ```
4. **Structured 422 validation:**
   ```bash
   POST /api/patients with invalid format
   # Returns 422 with {"errors": [{"field": "...", "message": "..."}]}
   ```

---

## 9. Troubleshooting

**Port 8000 already in use:**
```powershell
netstat -ano | findstr :8000
taskkill /PID <pid> /F
```

**Port 5173 already in use:**
```powershell
netstat -ano | findstr :5173
taskkill /PID <pid> /F
```

## 10. Running in Offline / Air-Gapped Environments (Milestone M11 / FR-13)

PatientCase AI is engineered for local-first clinic workstation execution with zero external WAN network dependencies:

1. **Verify Offline Workstation Status:**
   ```powershell
   Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/system/offline-status" -Method GET
   # Returns mode: local_workstation, offline_capable: true, external_dependencies: []
   ```

2. **Verify Database Integrity on Local Disk:**
   ```powershell
   # Authenticated call:
   $headers = @{ Authorization = "Bearer <token>" }
   Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/system/backup/verify" -Headers $headers -Method GET
   # Returns integrity_check: ok, storage: local_sqlite
   ```

3. **Multi-Device Sync Safeguard:**
   ```powershell
   # Any external sync invocation safely returns HTTP 501 to prevent silent overwrites:
   Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/system/sync" -Method POST
   # HTTP 501: Multi-device synchronization is not supported in this offline single-workstation release.
   ```

4. **Air-Gapped Simulation Test:**
   ```powershell
   cd "d:\Projects\New PatientCase AI\backend"
   .\.venv312\Scripts\python.exe -m pytest tests/test_offline_persistence.py -v
   ```

---

*Updated: M11 (Offline-First Workstation) — 2026-10-24.*





