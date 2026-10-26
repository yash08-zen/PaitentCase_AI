# GAP_ANALYSIS.md — PatientCase AI (M0 Audit)

## Gap Analysis Against Functional Requirements

Status: Done | Partial | Missing

---

### FR-01 — Patient Registration
**Status: Done (M3)**

Done:
- `POST /api/patients` with Pydantic validation (name, phone format, age limits).
- `POST /api/encounters` creating encounters linked to patient with unique ID (`P-<id>`).
- Mandatory informed consent capture (`consent_given: true` and timestamp) recorded before interview initiation.
- 15-second debounce window preventing duplicate accidental submissions.
- Role-scoping enforced: patients cannot access other patient records (`HTTP 403`).
- Frontend registration form fully wired to API client with validation and error states.

---

### FR-02 — Guided Adaptive Interview
**Status: Done (M4)**

Done:
- Canonical question bank configuration in `question_bank.json` (16 questions covering all clinical intake sections).
- AdaptiveEngine: `get_next_question`, `save_response` (upsert with dynamic pruning), `get_progress`, `back_question`, `resume`, `complete_interview`.
- Bidirectional back navigation and session resume endpoints (`POST /api/interviews/{id}/back`, `POST /api/interviews/{id}/resume`).
- Answers persisted with provenance `source='patient_reported'` and timestamps.
- Frontend `Interview.jsx` driven entirely by API endpoints with review screen and editable summary.
- Gated by mandatory informed consent before interview initiation.

---

### FR-03 — Rule-based Adaptive Follow-ups
**Status: Done (M4)**

Done:
- Purely deterministic rule engine supporting `show_if`, `skip_if`, and compound match operators (`equals`, `in`, `contains`, `not_equals`).
- Granular clinical routing: chest discomfort → exertional exacerbation, headache → frequency pattern, pain → location/severity/associated symptoms, fever → skips redundant fever question.
- Dynamic downstream pruning: changing a previous response automatically purges non-applicable dependent answers.
- 13 comprehensive branching unit tests in `tests/test_adaptive_interview.py` verified and passing.

---

### FR-04 — Structured Case Summary
**Status: Done (M5)**

Done:
- `GET /api/encounters/{id}/summary` returns `CaseSummaryOut` containing both structured clinical domains (`sections` and `structured_findings`) and formatted plain text (`summary_text`).
- Per-field provenance source tags explicitly categorized: `patient_reported`, `document_extracted_unverified`, `doctor_verified`, and `missing_unknown`.
- Safety boundary labels and clinical disclaimers applied to all summary responses ("⚠️ FOR CLINICAL REVIEW ONLY — NOT A DIAGNOSIS ⚠️").
- Both `DoctorReview.jsx` and `Interview.jsx` completion screens wired to this real API endpoint. All mock summary generators removed.

---

### FR-05 — Missing Information Detection
**Status: Done (M5)**

Done:
- `GET /api/encounters/{id}/missing` and `GET /api/encounters/{id}/missing-information` detect missing or skipped required checklist items (`chief_complaint`, `symptom_duration`, `symptom_severity`, `has_chronic_conditions`, `current_medications`, `has_allergies`).
- Critical Safety Rule: Missing information ≠ negative answer. Blanks, skips, and unknowns render as `"Not provided / unknown"`, NEVER as `"No"`.
- Explicit tests prove unanswered allergy question surfaces as `"Not provided / unknown"`, and answering it immediately clears the checklist.
- Frontend displays live checklist in `DoctorReview.jsx` and `Interview.jsx`. Local `missing()` function removed from review screen.

---

### FR-06 — Doctor Review Dashboard
**Status: Done (M8)**

Done:
- `GET /api/dashboard/summary` — total_patients, active_encounters, completed_cases, cases_needing_review (open flags, conflicts, or completed encounters awaiting clinician review).
- `GET /api/dashboard/cases` — filterable by status (`needs_review`, `all`, `reviewed`, `active`) and patient search query, returning open_flags, open_conflicts, readiness score, and doctor notes.
- `GET /api/encounters/{id}/readiness` — 4-factor deterministic score with explicit clinical-boundary disclaimer.
- `PUT /api/encounters/{id}/notes` — clinician notes persistence with role restriction (`doctor`, `admin`) and immutable audit event `DOCTOR_NOTES_UPDATED`.
- `GET /api/encounters/{id}/notes` — retrieves clinician notes and review status.
- `POST /api/encounters/{id}/finalize` — transitions encounter status to `reviewed`, sets `reviewed_at` and `reviewed_by`, records audit event `CASE_FINALIZED`, and permanently locks interview responses against further patient editing (`HTTP 400`).
- Provenance & discrepancy resolution — `PUT /api/conflicts/{id}/resolve` retains original source values (`patient_reported` vs `document_extracted_unverified`) alongside resolution note and resolution timestamp.
- Frontend integration — `DoctorReview.jsx` and `Dashboard.jsx` connected to live API with autosave/manual notes persistence, live finalize flow, case locking, and queue navigation.

---

### FR-07 — Prescription Upload and OCR
**Status: Done (M6 & M13)**

Done:
- Real local OCR engine via `RapidOCR` (ONNX Runtime) with OpenCV preprocessing (grayscale, bilateral denoising, CLAHE contrast enhancement).
- Image & PDF uploads (`POST /api/documents/upload/{patient_id}`) with magic-byte content sniffing (Pillow/binary inspection rejecting disguised executables with 415) and 20MB size enforcement (413).
- Protected file storage outside web root (`./uploads`) with non-guessable UUID filenames.
- Authorized file retrieval endpoint (`GET /api/documents/{id}/file`) with path traversal guards and role boundaries.
- Asynchronous non-blocking background OCR worker (`app.database.AsyncSessionLocal`) with live polling endpoint (`GET /api/documents/{id}/extraction`).
- Empirical benchmarks (M13): printed hospital prescriptions achieve 100% medication recall; cursive handwriting drops to 0–33% recall and strictly defaults to `status="needs_review"` for manual doctor entry.
- Comprehensive test suite: 6 backend tests in `tests/test_prescription_ocr.py`, 5 benchmark tests in `tests/test_advanced_stretch_benchmarks.py`, 5 frontend tests in `src/pages/documents.smoke.test.jsx`.

---

### FR-08 — Medication Extraction and Discrepancy Rules
**Status: Done (M7)**

Done:
- Deterministic clinical medication extractor (`app/services/medication_extraction.py`) parsing generic/brand drug names, strengths/dosages (mg, mcg, g, ml), pharmaceutical forms, frequencies (OD, BD, TID, 1-0-1), and allergen mentions with provenance `document_extracted_unverified`.
- Discrepancy engine (`app/services/contradiction_detection.py`) evaluating 6 traceable clinical conflict rules (`RULE-MED-DENIAL`, `RULE-MED-NAME-MISMATCH`, `RULE-MED-DOSAGE-MISMATCH`, `RULE-ALLERGY-CONFLICT`, `RULE-ALLERGY-DENIAL`, `RULE-DOC-LOW-CONFIDENCE`).
- Preserves both source values (`source_a`/`value_a` and `source_b`/`value_b`) without overwriting.
- Conflict lifecycle & management endpoints (`PUT /api/conflicts/{id}/resolve` with doctor resolution note, status `resolved`/`dismissed`, and audit trail).
- Tests: 8 backend tests in `tests/test_medication_discrepancy.py`, 4 frontend tests in `conflicts.smoke.test.jsx`.

---

### FR-09 — Completeness / Readiness Indicator
**Status: Done (M5)**

Done:
- `GET /api/encounters/{id}/readiness` calculates a deterministic, 4-factor composite data-completeness score (required checklist 40%, critical missing 30%, open conflicts 20%, review flags 10%).
- Full mathematical formula and weights formally documented in `docs/DECISIONS.md` under D-029.
- Explicit non-diagnostic disclaimer delivered in every API response and displayed in UI.
- All clinical risk, urgency, and disease probability language strictly prohibited.
- `DoctorReview.jsx` and `Interview.jsx` display live completeness indicator and factor breakdown from this backend endpoint.

---

### FR-10 — Audit Logging
**Status: Done (M2)**

Done:
- Immutable `AuditEvent` entity and service recording actor ID, username, action type, resource type/ID, timestamp, and details JSON.
- Audit events logged on: user login, logout, failed login, patient registration, encounter creation, document upload, conflict resolution, doctor notes update, and case finalization.
- Scoped endpoint `GET /api/auth/audit` restricted to `admin` role with role boundary tests (`HTTP 403` for non-admin).

---

### FR-11 — Integration Foundation / Single Frontend
**Status: Done (M1)**

Done:
- `PatientCase-Seminar` established as the sole active frontend; old prototype retired to `legacy/frontend`.
- Typed `ApiClient` in `src/api/client.js` with normalized error handling, bearer token injection, and timeout handling.
- Non-diagnostic clinical boundary banner rendered across all pages in layout.
- Clean database migrations configured via Alembic (`alembic upgrade head`).
- Health check endpoints (`/health` and `/api/health`) verified with frontend DevHealthIndicator.

---

### FR-12 — Multilingual Voice
**Status: Done (M12 & M13)**

Done:
- Trilingual question bank and speech synonyms in English, Hindi, and Marathi (`app/data/translations.py`).
- Audio question prompts using browser `speechSynthesis` (`en-IN`, `hi-IN`, `mr-IN`).
- Normalized transcript parser (`POST /api/voice/parse-transcript`) mapping spoken utterances into canonical symptoms, pain severity scale (1-10), duration, and intent.
- Dialect detector `detect_speech_dialect()` classifying standard vs code-mixed speech (Hinglish/Marathish).
- Mandatory safety confirmation card (`VoiceAssistant.jsx`): transcripts with confidence < 0.85, code-mixed speech, or critical fields (allergies/medications) strictly require visual confirmation before committing.
- Touch and keyboard input remains 100% accessible at all times without blocking.
- Verified on 25-utterance evaluation dataset achieving 92% aggregate intent resolution.

---

### FR-13 — Offline Operation
**Status: Done (M11)**

Done:
- 100% zero external online dependencies: no CDNs, external Google fonts, or cloud OCR/voice APIs.
- Backend, frontend, and SQLite database execute entirely on `localhost`.
- Air-gapped network isolation verified via automated socket trap (`test_air_gapped_network_isolation`).
- Data persists across hard database reconnections and app restarts (`test_offline_persistence.py`).
- Safe multi-device sync guard (`POST /api/system/sync` returns `HTTP 501 Not Implemented`) preventing silent data corruption.
- Storage disk integrity check (`GET /api/system/backup/verify`) executing SQLite `PRAGMA integrity_check`.

---

### FR-14 — Security, Validation, Error Handling
**Status: Done (M9)**

Done:
- JWT authentication (python-jose), bcrypt passwords, and role-based access control (4 roles).
- Defensive security headers on all responses via `SecurityHeadersMiddleware`: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `X-XSS-Protection: 1; mode=block`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy`, and `Content-Security-Policy: frame-ancestors 'none'`.
- In-memory sliding-window rate limiter protecting auth and upload endpoints with `HTTP 429` and `Retry-After`.
- Safe global exception handling intercepting unhandled 500s without stack trace or server path leaks.
- Structured Pydantic 422 validation formatting (`{"errors": [{"field": "...", "message": "..."}]}`).
- PII and credential scrubbing (`[REDACTED]`) in request access logging.

---

### FR-15 — End-to-End Demo and Test Suite
**Status: Done (M10 & M14)**

Done:
- Comprehensive 9-step automated clinical lifecycle integration test (`tests/test_e2e_p0_release_gate.py`).
- Deterministic seeding script (`seed_demo_e2e.py`) producing 4 realistic clinical intake scenarios.
- Detailed step-by-step evaluator walkthrough in `docs/DEMO_SCRIPT.md`.
- Complete test report in `docs/TEST_REPORT.md` (170 / 170 tests passing, 100% green).
- P0 checklist fully verified in `docs/P0_CHECKLIST.md`.

---

## Summary Table

| FR | Title | Status | Priority | Verified In |
|---|---|---|---|---|
| FR-01 | Patient Registration | **Done** | P0 | M3 |
| FR-02 | Guided Interview | **Done** | P0 | M4 |
| FR-03 | Adaptive Rule Engine | **Done** | P0 | M4 |
| FR-04 | Structured Summary | **Done** | P0 | M5 |
| FR-05 | Missing Info Detection | **Done** | P0 | M5 |
| FR-06 | Doctor Review Dashboard | **Done** | P0 | M8 |
| FR-07 | Prescription Upload + OCR | **Done** | P0 | M6 & M13 |
| FR-08 | Medication Extraction + Discrepancy | **Done** | P0 | M7 |
| FR-09 | Completeness Indicator | **Done** | P0 | M5 |
| FR-10 | Audit Logging | **Done** | P0 | M2 |
| FR-11 | Integration Foundation | **Done** | P0 | M1 |
| FR-12 | Multilingual Voice | **Done** | P1 | M12 & M13 |
| FR-13 | Offline Operation | **Done** | P1 | M11 |
| FR-14 | Security / Validation | **Done** | P0 | M9 |
| FR-15 | E2E Demo + Tests | **Done** | P0 | M10 & M14 |

---

*Verified: Milestone M14 Handover — 2026-10-25*
