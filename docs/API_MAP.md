# API Map — PatientCase AI (Final Release / Milestone M14)

> Final comprehensive mapping of every screen, action, and backend endpoint in PatientCase AI.
> Sole active frontend: **Frontend (`frontend/`)** (`http://localhost:5173`)
> Backend: **FastAPI** (`http://127.0.0.1:8000`)
> All endpoints verified 100% operational with real database persistence.

---

## 1. Screen-by-Screen API Mapping

### Screen 1 — Authentication & Session (`Login.jsx`)

| Action | Frontend Handler | Backend Endpoint | Method | Status | Notes |
|---|---|---|---|---|---|
| Authenticate user | `apiClient.login(username, password)` | `/api/auth/login` | `POST` | **Verified (M2)** | Hashed bcrypt check, JWT bearer token, sliding rate limit (10 req/min). |
| New patient self-registration | `apiClient.selfRegister(payload)` | `/api/patients/self-register` | `POST` | **Verified (M15)** | Creates new patient account, encounter with consent, auto-logs in and redirects to intake. |
| Logout session | `apiClient.logout()` | `/api/auth/logout` | `POST` | **Verified (M2)** | Revokes session, scrubs local token, logs audit event. |
| Fetch current profile | `apiClient.getCurrentUser()` | `/api/auth/me` | `GET` | **Verified (M2)** | Returns id, username, email, role, and active status. |
| Inspect audit logs | `apiClient.getAuditLogs()` | `/api/auth/audit` | `GET` | **Verified (M2)** | Role-scoped to `admin` only (returns 403 for others). |

---

### Screen 2 — Doctor Dashboard & Review Queue (`Dashboard.jsx`)

| Action | Frontend Handler | Backend Endpoint | Method | Status | Notes |
|---|---|---|---|---|---|
| Aggregate statistics | `apiClient.getDashboardSummary()` | `/api/dashboard/summary` | `GET` | **Verified (M8)** | Returns total patients, active encounters, completed, and cases needing review. |
| Filtered case review queue | `apiClient.getDashboardCases(params)` | `/api/dashboard/cases` | `GET` | **Verified (M8)** | Supports `status=needs_review|all|reviewed|active`, search query, and pagination. |
| Health indicator badge | `apiClient.checkHealth()` | `/health` | `GET` | **Verified (M1)** | Verifies FastAPI application and SQLite database connection status. |
| Offline workstation banner | `apiClient.getOfflineStatus()` | `/api/system/offline-status` | `GET` | **Verified (M11)** | Surfaces local workstation mode and zero external dependencies. |

---

### Screen 3 — Patient Registration & Consent (`Register.jsx`)

| Action | Frontend Handler | Backend Endpoint | Method | Status | Notes |
|---|---|---|---|---|---|
| Register new patient | `apiClient.registerPatient(payload)` | `/api/patients` | `POST` | **Verified (M3)** | Generates unique patient ID, enforces phone format and age bounds. |
| Create linked encounter | `apiClient.createEncounter(payload)` | `/api/encounters` | `POST` | **Verified (M3)** | Mandatory consent flag and timestamp; debounced duplicate prevention. |
| Search registered patients | `apiClient.getPatients(params)` | `/api/patients` | `GET` | **Verified (M3)** | Search by name, phone, or ID; role-scoped. |

---

### Screen 4 — Patient Directory & Encounters (`PatientList.jsx`)

| Action | Frontend Handler | Backend Endpoint | Method | Status | Notes |
|---|---|---|---|---|---|
| List all patients | `apiClient.getPatients(query)` | `/api/patients` | `GET` | **Verified (M3)** | Scoped to authorized staff/doctors/admins; patients see own record only. |
| Retrieve patient profile | `apiClient.getPatient(patientId)` | `/api/patients/{id}` | `GET` | **Verified (M3)** | Returns demographics, contact, language preference, and history. |
| Encounter readiness score | `apiClient.getEncounterReadiness(id)` | `/api/encounters/{id}/readiness` | `GET` | **Verified (M5)** | Deterministic 4-factor completeness score and missing field count. |

---

### Screen 5 — Adaptive Rule-Based Interview (`Interview.jsx`)

| Action | Frontend Handler | Backend Endpoint | Method | Status | Notes |
|---|---|---|---|---|---|
| Fetch next question | `apiClient.getNextQuestion(encounterId)` | `/api/interviews/{id}/next-question` | `GET` | **Verified (M4)** | Deterministic rule engine evaluates `show_if`, `skip_if`, and current answers. |
| Submit question answer | `apiClient.submitResponse(id, key, val)` | `/api/interviews/{id}/responses` | `POST` | **Verified (M4)** | Upserts response, locks modifications if case is finalized (`HTTP 400`). |
| Back-navigate question | `apiClient.backQuestion(encounterId)` | `/api/interviews/{id}/back` | `POST` | **Verified (M4)** | Safely unwinds interview step, dynamically pruning orphaned branches. |
| Session progress tracking | `apiClient.getInterviewProgress(id)` | `/api/interviews/{id}/progress` | `GET` | **Verified (M4)** | Percentage completed, answered questions count, and total branch count. |
| Resume interrupted session | `apiClient.resumeInterview(encounterId)` | `/api/interviews/{id}/resume` | `POST` | **Verified (M4)** | Restores state from database after reload or disconnect. |
| Mark interview complete | `apiClient.completeInterview(encounterId)`| `/api/interviews/{id}/complete` | `POST` | **Verified (M4)** | Transitions encounter status to `completed` awaiting doctor review. |

---

### Screen 6 — Medical Documents & Local Offline OCR (`Documents.jsx`)

| Action | Frontend Handler | Backend Endpoint | Method | Status | Notes |
|---|---|---|---|---|---|
| Upload prescription image | `apiClient.uploadDocument(id, file, type)`| `/api/documents/upload/{patient_id}` | `POST` | **Verified (M6)** | Content-sniffed (blocks executable spoofing), 20MB limit. |
| Poll OCR processing status| `apiClient.getDocument(docId)` | `/api/documents/{id}` | `GET` | **Verified (M6)** | On-device RapidOCR / ONNX inference runs locally; returns status. |
| Extracted entity payload | `apiClient.getDocumentExtraction(id)` | `/api/documents/{id}/extraction` | `GET` | **Verified (M6)** | Extracted medication, dosage, confidence, and provenance tags. |
| List encounter documents | `apiClient.getDocuments(params)` | `/api/documents` | `GET` | **Verified (M6)** | Filter by `patient_id` or `encounter_id`. |

---

### Screen 7 — Doctor Case Review & Finalization (`DoctorReview.jsx`)

| Action | Frontend Handler | Backend Endpoint | Method | Status | Notes |
|---|---|---|---|---|---|
| Load structured summary | `apiClient.getCaseSummary(encounterId)` | `/api/encounters/{id}/summary` | `GET` | **Verified (M5)** | Structured findings tagged with source provenance (`patient_reported`, `document_extracted_unverified`, `doctor_verified`). |
| Missing information list | `apiClient.getMissingInformation(id)` | `/api/encounters/{id}/missing-information`| `GET` | **Verified (M5)** | Identifies unprovided fields; strictly enforces **Missing $\neq$ Negative**. |
| Detect discrepancies | `apiClient.getContradictions(id)` | `/api/encounters/{id}/contradictions` | `GET` | **Verified (M7)** | Deterministic 6-rule contradiction engine (e.g., `RULE-MED-DENIAL`). |
| Reconcile discrepancy | `apiClient.resolveConflict(cid, notes)` | `/api/conflicts/{id}/resolve` | `PUT` | **Verified (M8)** | Doctor resolution note, updates flag, emits audit trail. |
| Persist doctor notes | `apiClient.saveDoctorNotes(id, notes)` | `/api/encounters/{id}/notes` | `PUT` | **Verified (M8)** | Persists clinical review observations to encounter record. |
| Finalize & lock encounter | `apiClient.finalizeEncounter(id, notes)`| `/api/encounters/{id}/finalize` | `POST` | **Verified (M8)** | Permanently locks encounter against patient tampering (`HTTP 400`). |

---

## 2. Specialized Services & Innovation Endpoints

### Multilingual Voice Assistant (`VoiceAssistant.jsx` / M12 & M13)

| Endpoint | Method | Description | Status |
|---|---|---|---|
| `/api/voice/languages` | `GET` | Returns supported language roster (`en`, `hi`, `mr`). | **Verified (M12)** |
| `/api/voice/questions/{key}` | `GET` | Localized question text, choices, and spoken prompt audio text. | **Verified (M12)** |
| `/api/voice/parse-transcript` | `POST` | Normalizes speech transcripts, extracts symptom/severity entities, identifies code-mixing, and enforces mandatory safety confirmations. | **Verified (M12/M13)** |
| `/api/voice/encounters/{id}/language` | `POST` | Persists patient language preference on encounter and profile. | **Verified (M12)** |

### System Safety, Offline & Benchmarks (`system.py` / M11 & M13)

| Endpoint | Method | Description | Status |
|---|---|---|---|
| `/api/system/offline-status` | `GET` | Reports local workstation operating mode, zero external WAN sockets, and local ONNX OCR engine. | **Verified (M11)** |
| `/api/system/backup/verify` | `GET` | Executes SQLite disk integrity check (`PRAGMA integrity_check`) to confirm database consistency. | **Verified (M11)** |
| `/api/system/sync` | `POST` | Safely rejects remote multi-device cloud synchronization (`HTTP 501 Not Implemented`) to prevent silent overwrites. | **Verified (M11)** |
| `/api/system/benchmarks/summary`| `GET` | Reports empirical printed vs. handwritten OCR metrics and code-mixed speech accuracy/confirmation rates. | **Verified (M13)** |

---

*Verified: Milestone M14 Handover — 2026-10-25*
