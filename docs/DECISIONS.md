# DECISIONS.md — PatientCase AI

## Initial decisions — M0 Audit (2026-10-22)

---

### D-001: Repository layout decision
**Decision:** Work within d:\Projects\New PatientCase AI as the workspace root. Both existing repos (PatientCase_AI at d:\Projects\PatientCase_AI and PatientCase-Seminar at d:\Projects\PatientCase-Seminar) are siblings outside this workspace. Starting from M1, all deliverable docs and integration code live in d:\Projects\New PatientCase AI. Application source stays in the original repos.

**Reason:** The workspace policy enforces the work directory. Creating duplicates of source code would cause divergence; symbolic links will be assessed in M1.

---

### D-002: PatientCase-Seminar as sole active frontend
**Decision:** PatientCase-Seminar (React/Vite, localhost:5173) is the one and only active frontend. The old PatientCase_AI/frontend (also React/Vite, localhost:5173) will be retired (moved to legacy/ inside the PatientCase_AI repo) starting M1.

**Reason:** M0 audit confirmed the old frontend is fully independent of the backend serving it — the backend does not serve static files from the old frontend directory; they both run as separate Vite dev servers. The old frontend is superior in using the real API; the Seminar frontend is superior in UX/design and closer to the prototype showcase goal. Merging old frontend API wiring into Seminar is the required approach.

**Evidence old frontend does NOT serve HTML from the backend:** main.py has no StaticFiles mount. The old frontend's ite.config.js (port 5173) is a separate process.

---

### D-003: No Alembic migrations found — using init_db() approach
**Decision:** The backend uses SQLAlchemy Base.metadata.create_all at startup (init_db()) rather than Alembic migrations. This is acceptable for a prototype/SQLite setup. Alembic will be introduced if/when schema changes require migration (M1 onwards if schema changes happen).

**Reason:** No lembic.ini or migrations/ directory was found in PatientCase_AI/backend. The 
equirements.txt lists lembic==1.13.1 (installed but not configured). For the current SQLite prototype, init_db() is sufficient. Adding Alembic is tracked as a follow-up.

---

### D-004: Frontend state is entirely in-memory (no API calls)
**Decision:** The PatientCase-Seminar frontend makes zero API calls. All data lives in React state initialized from mock arrays (PATIENTS, CASES, SAMPLE_DOCS, QUESTIONS constants). Authentication is bypassed with onLogin() accepting any form submission. This is entirely replaced starting M1/M2.

---

### D-005: OCR is a stub — no real OCR in any existing code
**Decision:** The backend document_processing.py is a no-op stub that returns None, {}, None after a 0.1s sleep. The frontend documents.js has a header comment: "SIMULATED OCR output. No real image processing happens in this prototype." Real OCR (Tesseract) is planned for M6.

---

### D-006: Conflict/resolution and doctor-notes endpoints are missing
**Decision:** The backend has no endpoints for:
- Resolving a specific conflict (PUT /api/encounters/{id}/conflicts/{cid}/resolve)
- Saving doctor notes per encounter
- Finalizing an encounter explicitly

These are needed for M8 and must be added in that milestone.

---

### D-007: Permissions matrix (initial, to be enforced from M2)

| Role | Register patient | Create encounter | Run interview | Upload document | View all cases | Doctor review & finalize | Admin functions |
|---|---|---|---|---|---|---|---|
| patient | own only | own only | own only | own only | no | no | no |
| staff | yes | yes | yes | yes | all | no | no |
| doctor | yes | yes | yes | yes | all | yes | no |
| admin | yes | yes | yes | yes | all | yes | yes |

---

### D-008: No patient role exists in current implementation
**Decision:** The existing system has roles: patient, staff, doctor, dmin (defined in UserRole enum in models.py), but the Patient model has no user_id foreign key — patients are not linked to user accounts. Patient-role self-service is therefore not implementable without a schema change. This is tracked for M3.

---

*Document will be updated at each milestone.*

---

## Milestone 1 Decisions — Single-Frontend Integration Foundation (2026-10-23)

---

### D-009: Retirement of old frontend into legacy/frontend
**Decision:** The old frontend directory d:\Projects\PatientCase_AI\frontend has been moved to d:\Projects\PatientCase_AI\legacy\frontend. PatientCase-Seminar is the sole, active frontend. Backend documentation and startup instructions in PatientCase_AI/README.md and docs/RUNBOOK.md have been updated to point exclusively to PatientCase-Seminar.

---

### D-010: Database migrations introduced via Alembic (Async SQLite/PostgreSQL)
**Decision:** Configured Alembic with async SQLAlchemy support (alembic/env.py) connected to the application's declarative metadata (Base.metadata). Generated baseline migration 694c11440dd3_initial_schema.py covering all 11 entities (users, patients, encounters, questions, responses, documents, conflicts, review_flags, case_summaries). Clean database migrations can now be executed with a single command: alembic upgrade head.

---

### D-011: Synthetic seed script skeleton
**Decision:** Created an idempotent synthetic seeding script d:\Projects\PatientCase_AI\backend\app\scripts\seed_synthetic_data.py (runnable via python -m app.scripts.seed_synthetic_data). It seeds demo users (admin, doctor, staff), the complete 16-question bank, and 3 realistic synthetic patients with linked encounters and sample responses.

---

### D-012: Typed API client with normalized error handling
**Decision:** Implemented d:\Projects\PatientCase-Seminar\src\api\client.js with:
- Configurable base URL via VITE_API_BASE_URL (defaults to http://127.0.0.1:8000)
- Custom ApiError class extending Error with isNetworkError, status, code, and data properties
- Normalization for network failures (status 0), client errors (400/401/403/404/422 with Pydantic detail unpacking), and server errors (500)
- Bearer token authentication injection
- Health check helper method checkHealth()

---

### D-013: Frontend unit and smoke testing with Vitest
**Decision:** Added vitest@2 (compatible with Vite 5) to PatientCase-Seminar devDependencies with npm run test script. Unit tests in src/api/client.test.js cover all error normalization branches, and smoke tests in src/components/ui.smoke.test.jsx verify component rendering via react-dom/server without requiring heavy DOM emulation libraries.

---

### D-014: Prominent clinical boundary notice and live health indicator
**Decision:** Added ClinicalNotice ("Prototype supporting clinician review — not a diagnostic tool") and HealthIndicator (live API + DB status indicator) components to src/components/ui.jsx, styled in src/App.css, and placed into Shell.jsx (main layout) and Login.jsx (unauthenticated view).


---

## Milestone 2 Decisions - Authentication, Roles, and Audit Logging (2026-10-23)

---

### D-015: Formal Permissions Matrix & Role-Based Access Control (RBAC)
**Decision:** All API routes enforce least-privilege role boundaries using FastAPI dependencies (`require_roles(...)` and `get_current_user`). Direct API requests with insufficient roles return `403 Forbidden`. Unauthenticated requests return `401 Unauthorized`. Passwords are encrypted with `bcrypt` (using `bcrypt.gensalt()` with 72-byte safe truncation), and tokens are signed with `HS256` using `APP_SECRET_KEY` loaded from `.env` (git-ignored, never hardcoded).

#### Permissions Matrix

| Endpoint / Operation | HTTP | Patient | Clinic Staff | Doctor | Administrator | Description |
|---|---|---|---|---|---|---|
| `/api/auth/login` | POST | Allow | Allow | Allow | Allow | Authenticates and returns JWT |
| `/api/auth/logout` | POST | Allow | Allow | Allow | Allow | Logs audit event and invalidates session |
| `/api/auth/me` | GET | Allow | Allow | Allow | Allow | Profile of authenticated user |
| `/api/auth/register` | POST | Deny (403) | Deny (403) | Deny (403) | Allow | Creates user account (Admin only) |
| `/api/auth/audit` | GET | Deny (403) | Deny (403) | Deny (403) | Allow | Views audit trail (Admin only) |
| `/api/dashboard/*` | GET | Deny (403) | Allow | Allow | Allow | Clinical metrics & case review queues |
| `/api/patients` (list) | GET | Deny (403) | Allow | Allow | Allow | Search/list all patient records |
| `/api/patients` (create) | POST | Deny (403) | Allow | Allow | Allow | Registers a new patient |
| `/api/patients/{id}` | GET | Own Only | Allow | Allow | Allow | Retrieves individual patient record |
| `/api/patients/{id}` | PUT | Deny (403) | Allow | Allow | Allow | Updates patient demographics |
| `/api/encounters` (list) | GET | Own Only | Allow | Allow | Allow | Lists encounters (patients see own) |
| `/api/encounters` (create) | POST | Own Only | Allow | Allow | Allow | Starts encounter (patients for self only) |
| `/api/encounters/{id}` | GET | Own Only | Allow | Allow | Allow | Retrieves encounter details |
| `/api/encounters/{id}` | PUT | Deny (403) | Allow | Allow | Allow | Updates encounter status |
| `/api/interviews/{id}/*` | GET/POST | Own Only | Allow | Allow | Allow | Adaptive question taking & answering |
| `/api/documents/upload/{p_id}` | POST | Own Only | Allow | Allow | Allow | Uploads prescription/document |
| `/api/documents/{id}` | GET | Own Only | Allow | Allow | Allow | Views uploaded document |
| `/api/documents/{id}/review` | POST | Deny (403) | Deny (403) | Allow | Allow | Clinician document review & verification |
| `/api/encounters/{id}/summary` | GET | Own Only | Allow | Allow | Allow | Structured summary with provenance |

---

### D-016: Record-Level Access Control for Patients (`patients.user_id`)
**Decision:** Added a `user_id` foreign key (`patients.user_id -> users.id`) via Alembic migration `1cc939388310_add_patient_user_id.py`. When an authenticated user has the `patient` role:
1. `GET /api/patients/{id}` checks `patient.user_id == current_user.id`, returning 403 on mismatch.
2. `GET /api/encounters/{id}` checks `encounter.patient.user_id == current_user.id`, returning 403 on mismatch.
3. `GET /api/encounters` scopes query results exclusively to encounters where `Patient.user_id == current_user.id`.
4. `POST /api/encounters` prevents creating an encounter for another patient record.
5. `GET/POST /api/interviews/{id}/*` prevents accessing interview flow of another patient's encounter.
6. `POST /api/documents/upload/{patient_id}` and `GET /api/documents/{id}` prevents accessing documents of another patient.

---

### D-017: Append-Only Audit Trail (`audit_events` & `/api/auth/audit`)
**Decision:** All authentication and security events (`LOGIN_SUCCESS`, `LOGIN_FAILED`, `LOGOUT`, `USER_REGISTERED`, `PATIENT_CREATED`, `ENCOUNTER_CREATED`) are logged into the append-only `audit_events` table via `app.services.audit.log_audit_event`. Plaintext passwords and JWT tokens are never logged or stored in change summaries. Audit logs can be retrieved by administrators at `GET /api/auth/audit` with filtering by action.

---

### D-018: Frontend Role-Based Navigation & Session Expiry Handling
**Decision:**
1. Replaced hardcoded frontend authentication with real API authentication via `apiClient.login(username, password)` in `Login.jsx`.
2. Provided 4 one-click quick-fill preset pills for synthetic demo testing (Doctor, Clinic Staff, Patient, Administrator).
3. Configured automatic session expiry handling: `apiClient` intercepts `401 Unauthorized` responses on protected endpoints and triggers an `onUnauthorized` callback that clears session state, redirects to the login screen, and displays a warning banner.
4. Filtered sidebar navigation links by role in `Shell.jsx`, displaying the user's role badge and identity in the header.
5. Added `AuditLog.jsx` page for administrators to inspect real-time system audit trails directly in the UI.

---

## Milestone 3 Decisions - Patient Registration and Encounters (2026-10-23)

---

### D-019: Real Patient Registration & Linked Encounter Creation
**Decision:** Replaced all simulated/mock registration data in `Register.jsx` and `store.jsx` with real backend API requests (`POST /api/patients` and `POST /api/encounters`). Each patient registered receives an auto-incrementing unique database primary key ID (`P-{id}` in UI) and a linked unique `Encounter` ID (`#{id}`). All demographics and encounter state persist across page reloads and backend restarts.

---

### D-020: Server-Enforced Informed Consent & Interview Gate
**Decision:** Added `consent_given` (Boolean, default=False) and `consent_timestamp` (DateTime) to the `encounters` table via Alembic migration `607ae254263b_add_consent_to_encounters.py`. Added a dedicated endpoint `POST /api/encounters/{encounter_id}/consent` that logs audit event `CONSENT_RECORDED`. In `routers/interviews.py`, the adaptive interview engine strictly blocks (`400 Bad Request: Informed consent must be recorded before starting or resuming the interview.`) any interview requests for encounters where `consent_given` is false. In the UI, the registration form requires checking the informed consent checkbox before submission, recording the consent timestamp immediately.

---

### D-021: Server & Client Duplicate Submission (Idempotency) Protection
**Decision:**
1. **Client-side:** The "Register and continue" button is disabled during submission (`isSubmitting=true`) with an inline loading spinner (`Spinner text="Registering patient & creating encounter..."`) to prevent accidental double-clicks.
2. **Server-side:** In `routers/patients.py` and `routers/encounters.py`, rapid duplicate submissions (matching full_name/patient_id within 15 seconds) return the existing record idempotently instead of creating duplicate database records. Verified with automated concurrent submission tests.

---

### D-022: Dynamic Patient Store Synchronized with Backend
**Decision:** Updated `src/state/store.jsx` to fetch real patients from `GET /api/patients` and encounters from `GET /api/encounters` whenever authenticated. When a user completes registration in `Register.jsx`, the store updates the active patient list, sets the newly created patient as `activeId`, and provides navigation to immediately begin the adaptive interview.

---

## Milestone 4 Decisions — Guided Interview and Adaptive Rule Engine (2026-10-23)

---

### D-023: Canonical Question Bank as Configuration & DB Schema Extensions
**Decision:** Established `app/data/question_bank.json` containing the single source of truth for the clinical question bank (20 questions covering symptoms, severity, location, duration, frequency, chronic conditions, medications, allergies, surgical history, and family background). Extended `questions` and `responses` tables via Alembic migration `2fa2d5d870dc_add_interview_enhancements.py` to add `label`, `section`, `placeholder`, `help`, `because`, and `skip_why` on questions, and provenance tracking `source` (default: `patient_reported`) and `confirmation_status` (default: `confirmed`) on responses.

---

### D-024: Deterministic Rule Engine with Dynamic Downstream Pruning
**Decision:** Built a purely deterministic rule engine in `app.services.adaptive_engine.AdaptiveEngine` supporting `show_if`, `skip_if`, and compound match operators (`equals`, `in`, `contains`, `not_equals`, `answer_contains`). When a patient revisits and changes a previous answer (e.g. switching `current_medications` from "Yes" to "No"), downstream answers that are no longer applicable are automatically purged from the database, preventing invalid stale state from polluting clinical summaries.

---

### D-025: Bidirectional Navigation & Incremental State Endpoints
**Decision:** Implemented dedicated interview endpoints in `routers/interviews.py`:
- `GET /api/interviews/{id}/next-question`: Evaluates current answers, returns the next unanswered applicable question with adaptive justification note and progress.
- `POST /api/interviews/{id}/responses`: Persists answers incrementally with provenance metadata.
- `POST /api/interviews/{id}/back`: Pops the last answered question and recalculates the active flow.
- `GET /api/interviews/{id}/progress`: Provides progress percentages, the ordered active path, and list of skipped questions with clinical rationale.
- `POST /api/interviews/{id}/resume`: Resumes interrupted sessions at the exact right question.
- `GET /api/interviews/{id}/answers`: Returns all recorded responses for pre-submission review.
- `POST /api/interviews/{id}/complete`: Validates that all required questions are answered before transitioning encounter status to `needs_review`.

---

### D-026: Frontend Driven Exclusively by Dynamic Backend Questions
**Decision:** Removed hardcoded question logic and local rule evaluation in `Interview.jsx`. The frontend now dynamically renders questions directly from the API (`apiClient.getNextQuestion`, `apiClient.submitResponse`, `apiClient.backQuestion`, `apiClient.completeInterview`), supporting all answer types (`choice`, `multi`, `scale`, `text`), displaying real-time branch feedback ("Because you answered..."), presenting an editable review summary before final submission, and persisting state across browser reloads.

---

## Milestone 5 Decisions — Structured History, Summary, Missing Info, Completeness (2026-10-24)

---

### D-027: Structured Case Summary & Explicit Field-Level Provenance
**Decision:** `CaseSummaryOut` (`GET /api/encounters/{id}/summary`) now produces both structured clinical sections (`sections` and `structured_findings`) and formatted plain text (`summary_text`). Every clinical finding is explicitly tagged with its provenance source:
- `patient_reported`: directly provided by the patient during the intake interview
- `document_extracted_unverified`: extracted from uploaded medical documents via OCR/parser, awaiting doctor verification
- `doctor_verified`: clinician-confirmed value
- `missing_unknown`: unanswered or skipped item, requiring clinician review

---

### D-028: Honest Handling of Unknowns (Safety Rule: Missing ≠ Negative)
**Decision:** Blanks, skipped questions, and unanswered items are rendered as `"Not provided / unknown"`, NEVER as negative answers (e.g. an unanswered allergy question renders as `"Known allergies: Not provided / unknown"`, never `"No known allergies"` or `"No"`). `detect_missing()` in `missing_information.py` checks 6 critical checklist items (`chief_complaint`, `symptom_duration`, `symptom_severity`, `has_chronic_conditions`, `current_medications`, `has_allergies`) and surfaces each missing field with clinical rationale and status `"Not provided / unknown"`. Completing an answer immediately clears the item from the checklist.

---

### D-029: Deterministic Case Completeness Formula & Clinical Boundary Safety
**Decision:** The completeness score (`GET /api/encounters/{id}/readiness`) uses a deterministic, reproducible mathematical composite:
$$\text{Score} = (\text{required\_score} \times 0.40) + (\text{critical\_missing\_score} \times 0.30) + (\text{conflict\_score} \times 0.20) + (\text{flag\_score} \times 0.10)$$
- **Factor 1 (40%):** $\frac{\text{answered\_required}}{\text{total\_required}}$
- **Factor 2 (30%):** $1.0 - (\text{len}(\text{critical\_missing}) \times 0.2)$, bounded $[0.0, 1.0]$
- **Factor 3 (20%):** $1.0 - (\text{open\_conflicts} \times 0.3)$, bounded $[0.0, 1.0]$
- **Factor 4 (10%):** $1.0 - (\text{open\_flags} \times 0.25)$, bounded $[0.0, 1.0]$

**Categorical labels:**
- Score $\ge 0.80$: `"Ready for Review"`
- Score $\ge 0.50$: `"Partially Ready"`
- Score $< 0.50$: `"Not Ready"`

**Safety Guard:** The score strictly represents **data completeness for review readiness only**. All outputs include the explicit clinical boundary disclaimer: *"This score reflects case data completeness only. It is NOT a measure of diagnostic accuracy or patient health."* No triage priority, urgency, disease severity, or disease probability language is ever produced.

---

## Milestone 6 Decisions — Prescription Upload and Real OCR (2026-10-24)

---

### D-030: Real Local OCR Engine with RapidOCR (ONNX Runtime) & Adaptive Preprocessing
**Decision:** Adopted `rapidocr-onnxruntime` as the primary local OCR engine, complemented by OpenCV preprocessing (`CLAHE` contrast enhancement and bilateral denoising). RapidOCR executes completely offline without external cloud dependencies or API keys, provides high accuracy on printed prescriptions, extracts text line-by-line with bounding boxes and per-line confidence scores, and executes in ~0.3-0.8s on standard CPU hardware.

---

### D-031: Magic-Byte Content Sniffing, Protected Storage & Path Traversal Guards
**Decision:** All document uploads undergo strict server-side validation:
1. **Magic-Byte Sniffing:** Pillow and binary inspection verify file contents rather than trusting user-supplied `Content-Type` headers or file extensions. Disguised executables (`MZ`, `ELF`) or corrupt files are rejected with `415 Unsupported Media Type`.
2. **File Size Enforcement:** Enforces `MAX_UPLOAD_SIZE_MB = 20` directly on the request stream, returning `413 Request Entity Too Large` before memory bloat.
3. **Protected Storage:** Uploaded files are saved outside the web root (`./uploads`) with non-guessable UUID filenames (`{uuid}_{sanitized_basename}`).
4. **Authorized Retrieval:** `GET /api/documents/{id}/file` delivers files only to authenticated users subject to role boundaries (patients may only access their own files; staff/doctors access encounter files). Canonicalized path resolution prevents directory traversal attacks.

---

### D-032: Asynchronous Non-Blocking Execution & Failure Safety
**Decision:** File uploads return immediately with `HTTP 201 Created` and status `"pending"`. OCR runs as a background task via `app.database.AsyncSessionLocal`, freeing the HTTP event loop:
1. Blank images or images with average confidence $< 0.40$ or $< 3$ extracted characters transition to `"needs_review"` rather than failing silently or assuming negative findings.
2. Corrupt or unreadable files transition to `"failed"`.
3. In all error/review scenarios, the original uploaded file on disk is strictly preserved for manual clinician inspection.
4. Outputs are explicitly tagged with provenance `"document_extracted_unverified"`, per-line metrics, and execution time.

---

### D-033: Frontend Integration with Live Status Polling & Non-Diagnostic Badges
**Decision:** Completely replaced simulated `setTimeout` mock extraction in `PatientCase-Seminar/src/pages/Documents.jsx`:
- Integrated real multipart file uploads via `apiClient.uploadDocument`.
- Implemented client-side live status polling (`GET /api/documents/{id}/extraction`) every 1.5 seconds until resolution.
- Added authenticated scan preview rendering via protected blob fetching (`GET /api/documents/{id}/file`).
- Prominently displays the Non-Diagnostic Notice banner and tags all extracted text with the `"Unverified Evidence — Doctor Verification Required"` badge.

---

## Milestone 7 Decisions — Medication Extraction and Discrepancy Rules (2026-10-24)

---

### D-034: Deterministic Clinical Medication & Allergy Extractor
**Decision:** Built `app.services.medication_extraction` to parse raw OCR text into structured medication objects (`name`, `dosage`, `form`, `frequency`, `duration`, `instructions`) using a curated catalog of common generic/brand drugs, dosage regexes (`mg`, `mcg`, `g`, `ml`), and frequency normalizers (e.g., `1-0-1` → `Twice daily (Morning & Night)`, `TID` → `Three times daily`, `PRN` → `As needed`). Allergy triggers (`allergic to`, `allergies:`, `adverse reactions:`) are parsed into distinct allergen references. All entities are tagged with provenance `document_extracted_unverified`.

---

### D-035: Cross-Source Discrepancy Engine with Explicit Rule IDs
**Decision:** Standardized clinical conflict detection in `app.services.contradiction_detection` with 6 explicit, traceable rule identifiers:
1. `RULE-MED-DENIAL`: Patient states no medications, but prescription contains active medications.
2. `RULE-MED-NAME-MISMATCH`: Patient reports taking drug A, but prescription specifies drug B.
3. `RULE-MED-DOSAGE-MISMATCH`: Patient reports taking a drug at dosage X, but prescription specifies dosage Y.
4. `RULE-ALLERGY-CONFLICT`: Critical contraindication warning when an allergic patient is prescribed a cross-reactive compound (e.g. Penicillin allergy vs Amoxicillin prescription).
5. `RULE-ALLERGY-DENIAL`: Patient denies allergies, but document notes known allergies or adverse reactions.
6. `RULE-DOC-LOW-CONFIDENCE`: Document scan has low OCR confidence ($<0.50$) or legibility issues.
Both source values (`source_a`/`value_a` and `source_b`/`value_b`) are strictly preserved without automatic overwriting.

---

### D-036: Clinician Conflict Reconciliation Lifecycle & Audit Logging
**Decision:** Created dedicated endpoint `PUT /api/conflicts/{id}/resolve` restricted to doctors and administrators:
- Supports statuses `resolved` and `dismissed` with mandatory clinician `resolution_note`.
- Automatically populates `resolved_by` (clinician user ID) and `resolved_at` (UTC timestamp).
- Records an immutable `AuditEvent` (`CONFLICT_RESOLVED`) tracking who resolved the discrepancy, when, and with what clinical rationale.
- Integrated into `DoctorReview.jsx` and `Documents.jsx` with real-time UI updates, side-by-side evidence cards, and resolution actions.

---

## Milestone 8 Decisions — Doctor Dashboard, Review, and Persistence (2026-10-24)

---

### D-037: Clinician Review Notes Persistence & Audit Trail
**Decision:** Added `PUT /api/encounters/{id}/notes` and `GET /api/encounters/{id}/notes` restricted to `doctor` and `admin` roles:
- Persists clinician observations, instructions, and review notes into both `encounters.doctor_notes` and `case_summaries.doctor_notes`.
- Automatically logs immutable `AuditEvent` (`DOCTOR_NOTES_UPDATED`) recording actor identity, encounter ID, and change summary.
- Surfaces notes in `CaseSummaryOut` and `DoctorReview.jsx` with manual save, autosync to local store, and disabled edit mode once finalized.

---

### D-038: Intake Case Finalization & Encounter Locking
**Decision:** Added `POST /api/encounters/{id}/finalize` restricted to `doctor` and `admin`:
- Transitions encounter status to `reviewed`, sets `reviewed_at` (UTC timestamp) and `reviewed_by` (clinician user ID).
- Updates `CaseSummary.review_status` to `"reviewed"`.
- Records immutable `AuditEvent` (`CASE_FINALIZED`).
- **Encounter Locking Enforcement:** Both `POST /api/interviews/{id}/responses` and `POST /api/interviews/{id}/back` reject modifications with `HTTP 400 Bad Request` ("Cannot modify responses for a finalized encounter"), ensuring finalized clinical records cannot be tampered with or modified by patients.

---

### D-039: Dashboard Queue Enhancement & Live Fallback
**Decision:** Upgraded `/api/dashboard/summary` and `/api/dashboard/cases`:
- `summary` computes live counts: `total_patients`, `active_encounters`, `completed_cases`, and `cases_needing_review` (encounters not yet reviewed that have open review flags, open discrepancy conflicts, or are completed awaiting review).
- `cases` supports query filters (`status`: `needs_review`, `all`, `reviewed`, `active`) and case search queries, returning `open_flags`, `open_conflicts`, `readiness_score`, and `doctor_notes`.
- Frontend `Dashboard.jsx` fetches live backend summary and queue data on mount, with seamless fallback to store data if the backend is initializing or offline.

---

## Milestone 9 Decisions — Hardening: Validation, Errors, Security, UX States (2026-10-24)

---

### D-040: Comprehensive Defensive Security Headers & Restricted CORS
**Decision:** Added `app.core.security_headers.SecurityHeadersMiddleware`:
- Emits defensive HTTP headers on all responses: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `X-XSS-Protection: 1; mode=block`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy: camera=(), microphone=(), geolocation=()`, and `Content-Security-Policy: frame-ancestors 'none'`.
- Enforces HSTS (`Strict-Transport-Security`) in production mode.
- Restricted `CORSMiddleware` to explicit HTTP methods (`GET`, `POST`, `PUT`, `DELETE`, `OPTIONS`) and specific request headers rather than wildcard asterisks.

---

### D-041: Offline-Safe In-Memory Sliding-Window Rate Limiting
**Decision:** Built `app.core.rate_limiter.InMemoryRateLimiter`:
- Completely offline, thread-safe rate limiter protecting `/api/auth/login` (10 req/min), `/api/auth/register` (20 req/min), and `/api/documents/upload` (30 req/min).
- Emits `HTTP 429 Too Many Requests` with RFC-compliant `Retry-After` header when thresholds are exceeded.
- Automatically bypasses during standard test suite execution while allowing explicit testing via `limiter.enforce_in_tests = True`.

---

### D-042: Centralized Safe Exception Handling, Structured 422s, and PII Redaction
**Decision:** Implemented `app.core.error_handlers.py` and `app.core.logging_config.py`:
- Unhandled 500 exceptions are trapped and returned as clean JSON (`{"detail": "...", "error_code": "INTERNAL_SERVER_ERROR"}`), preventing Python stack traces, server paths, or internal details from leaking to callers.
- Pydantic validation errors (`RequestValidationError`) are parsed into clean structured field lists (`{"errors": [{"field": "...", "message": "..."}]}`).
- `RequestLoggingMiddleware` calculates duration in milliseconds and scrubs sensitive credentials (`Authorization: Bearer [REDACTED]`, `"password": "[REDACTED]"`).
- Frontend `apiClient` adds `AbortController` request timeout handling (HTTP 408) and structured error breakdown formatting.

---

## Milestone 10 Decisions — End-to-End Demo, Test Suite, and P0 Release Gate (2026-10-24)

---

### D-043: Deterministic End-to-End Demo Seeding Strategy (`seed_demo_e2e.py`)
**Decision:** Built `app/scripts/seed_demo_e2e.py` to seed 4 clinically realistic, distinct test scenarios:
- **Case 1 (In-Progress):** Patient with severe headache, partial answers submitted, ready to demonstrate dynamic branch evaluation.
- **Case 2 (Missing Info):** Patient with dry cough, skipped allergy question demonstrating **Missing $\neq$ Negative** and partial completeness score.
- **Case 3 (OCR & Discrepancy):** Patient who reported taking no medications paired with an uploaded prescription scan containing Amoxicillin 500mg, triggering `RULE-MED-DENIAL` for clinician reconciliation.
- **Case 4 (Finalized & Locked):** Suspected appendicitis case with detailed clinical notes from Dr. Mehta, demonstrating post-finalization immutability and `HTTP 400` locking.
- Distinguishes synthetic seeded cases with `(Demo)` naming in logs and clinical handoff documentation.

---

### D-044: Automated 9-Step P0 Release Gate Lifecycle Integration Testing
**Decision:** Implemented `backend/tests/test_e2e_p0_release_gate.py` and `PatientCase-Seminar/src/pages/e2e_p0_workflow.smoke.test.jsx`:
- Automates the full sequential lifecycle: patient registration with consent -> adaptive questioning -> missing information analysis -> real OCR prescription upload -> medication contradiction detection -> doctor dashboard review -> conflict resolution -> doctor notes persistence -> case finalization -> verification of locked interview responses (`HTTP 400`).
- Validates that non-diagnostic boundary notices and field-level provenance labels (`patient_reported`, `document_extracted_unverified`, `doctor_verified`, `missing_unknown`) are maintained throughout the entire intake pipeline.

---

### D-045: Transparent System Boundary & Limitation Documentation
**Decision:** Created `docs/DEMO_SCRIPT.md`, `docs/P0_CHECKLIST.md`, `docs/TEST_REPORT.md`, and `docs/LIMITATIONS.md`:
- Clearly asserts clinical boundaries: intake and documentation assistance only; no disease diagnosis, drug recommendation, or triage severity scoring.
- Honestly documents OCR boundaries (printed vs cursive degradation) and offline operating scope (localhost single clinic workstation, no unverified multi-device cloud sync).
- Audited test results across 82 backend pytest tests and 58 frontend vitest tests (140 / 140 passing, 100% green).

---

## Milestone 11 Decisions — Basic Local / Offline Operation (2026-10-24)

---

### D-046: Zero External Online Dependencies & Local Workstation Architecture
**Decision:** Eliminated all external CDNs, Google Fonts, and external API calls:
- Frontend assets (React, Lucide icons, Inter fonts) are 100% self-contained in the local bundle.
- Backend executes strictly on localhost with zero outbound WAN network calls.
- RapidOCR runs locally via ONNX Runtime without remote OCR cloud endpoints.
- Built `test_air_gapped_network_isolation` to cryptographically trap any attempt to establish non-local socket connections during intake and clinical review.
- Built safety guard endpoint `POST /api/system/sync` returning `HTTP 501 Not Implemented` to actively protect against silent data overwrites across unverified multi-device syncing.

---

## Milestone 12 Decisions — Multilingual Voice Conversation (2026-10-24)

---

### D-047: Trilingual Speech Normalization & Non-Silent Safety Confirmation Gate
**Decision:** Implemented trilingual voice pipeline covering English, Hindi, and Marathi:
- Language selection (`en`, `hi`, `mr`) is stored on encounter and patient records and maintained across all question turns.
- Audio synthesis reads localized question prompts aloud via browser `speechSynthesis` (`en-IN`, `hi-IN`, `mr-IN`).
- Implemented `POST /api/voice/parse-transcript` normalizing spoken utterances into canonical symptoms, pain severity scales (1-10), duration phrases, and affirmative/negative intents.
- **Mandatory Safety Rule:** Transcripts with confidence < 0.85 or containing safety-critical clinical entities (allergies, medications) strictly enforce `requires_confirmation = True`, requiring patient/clinician visual verification before committing to clinical history.

---

## Milestone 13 Decisions — Advanced Stretch & Empirical Benchmarks (2026-10-25)

---

### D-048: Empirical Evaluation Datasets & Human-in-the-Loop Handwriting Safety Policy
**Decision:** Established quantitative evaluation datasets before making any stretch claims:
- Committed 5-sample prescription image dataset (`tests/eval_data/handwritten/`) measuring Character Error Rate (CER), Word Error Rate (WER), and Medication Recall.
- Documented empirical findings: printed prescriptions achieve **100% recall**, while unconstrained doctor cursive scrawl drops to **0%–33.3% recall**.
- Enforced strict non-diagnostic clinical safeguard: automated finalization of handwritten prescriptions is **strictly disabled**; low-confidence scans (< 0.70) or cursive scrawls automatically default to `needs_review`, requiring clinician manual transcription.
- Evaluated code-mixed speech understanding across 25 utterances, proving that Hinglish and Marathish achieve 80–100% intent resolution while triggering mandatory human confirmation (80%–100% confirmation trigger).

---

## Milestone 14 Decisions — Documentation, Final Validation, and Handover (2026-10-25)

---

### D-049: Final Release Packaging & Measured Success Metrics Handover
**Decision:** Prepared full handover deliverables for independent reviewer operation:
- Created root `README.md` containing complete system architecture diagrams, quick-start guide, verified credentials, and measured success metrics table.
- Updated `docs/RUNBOOK.md`, `docs/API_MAP.md`, `docs/DEMO_SCRIPT.md`, and `docs/LIMITATIONS.md` to reflect 100% verified state.
- Executed full clean regression across the combined 170-test suite (97 backend pytest / 73 frontend vitest).
- Tagged release as `v1.0-prototype` with explicit clinical non-diagnostic boundary notices on all interfaces.

---

## Milestone 15 Decisions — Dynamic Trilingual UI Localization & Patient Self-Registration (2026-10-26)

---

### D-050: Active System-Wide Trilingual UI Localization & Patient Self-Registration Flow
**Decision:**
- **Patient Self-Registration vs Existing Patient Login:** Added dedicated Sign In vs New Patient Sign Up tabs to `Login.jsx` and backend endpoint `POST /api/patients/self-register`. New patients supply demographics, language, and symptoms with timestamped consent (`consent_given=True`), auto-logging into an encounter ready for intake. Existing patients retain one-click sign in to their prior records.
- **Active System-Wide UI Localization:** Instead of preferred language being purely a metadata tag for the clinician, selecting English, Hindi (`हिन्दी`), or Marathi (`मराठी`) dynamically translates the entire user interface (Shell navigation, role labels, Login/Signup forms, Patient Portal intake cards, Documents upload dropzone, and Clinical boundary notices).
- **Trilingual Adaptive Question Bank:** Translated all 20 canonical questions in `question_bank.json` (`translations.py` and `i18n.js`) with native Hindi and Marathi texts, choices, help guides, and spoken prompts.
- **Zero-Latency Offline-First Translation:** Built trilingual dictionary in `i18n.js` for instant, flicker-free UI switching while persisting the active language preference to backend encounter records (`/api/voice/encounters/{id}/language`).
- **Regression Pass:** Validated entire system across 173 total tests (98 backend pytest / 75 frontend vitest, 100% green).

---

## Milestone 16 Decisions — Standard Project Layout Restructuring (2026-10-26)

---

### D-051: Standard Full-Stack Workspace Structure & Directory Cleanup
**Decision:**
- **Elimination of Nested/Confusing Folders:** Removed the redundant `PatientCase_AI/` wrapper folder and the legacy `PatientCase-Seminar` directory name.
- **Canonical Root Layout:** Established standard full-stack layout directly under `d:\Projects\New PatientCase AI`:
  - `backend/`: FastAPI application, models, routers, services, SQLite migrations, and pytest test suite.
  - `frontend/`: React 18, Vite, responsive UI components, trilingual i18n, and vitest test suite.
  - `legacy/`: Historical prototypes safely archived without cluttering active directories.
  - `docs/`: Complete architectural documentation, runbooks, test reports, and API maps.
  - `.agents/`: Project rules and progress tracker.
  - `.gitignore`: Unified root gitignore for Python, Node, SQLite, `.env`, and test artifacts.
  - `README.md`: Central system overview and operational guide reflecting clean root paths.
- **Removed Directory Junction Reparse Points:** Replaced previous sibling Windows NTFS junctions with real physical directories directly within the workspace.
- **Verification:** Reinstalled and validated venv script launchers (`pytest.exe`, `uvicorn.exe`) and verified 100% test pass rate across both suites (98 backend pytest + 75 frontend vitest = 173/173 tests passing).


---

## Milestone 17 Decisions — AI Clinical Insights Layer (2026-10-31)

Principle for every decision below: *The LLM proposes. Code verifies. The doctor decides.* Where the task left a choice open, the safest option was taken.

### D-052: Three LLM providers behind one interface
**Decision:** `generate(task, system_prompt, user_content, json_schema, *, images=None)` with `hosted` (official `anthropic` SDK), `local` (Ollama OpenAI-compatible endpoint, ~3B model, `temperature=0`, `num_ctx=4096`, a semaphore of 1) and `mock` (deterministic, used by all tests). `LLM_PROVIDER` selects the provider at call time.
**Why:** the app must work offline on 8 GB RAM / 4 GB VRAM and tests must not touch the network.

### D-053: Structured outputs instead of forced tool use
**Decision:** the hosted provider uses `output_config.format` with a JSON schema. Every schema sets `additionalProperties: false` and lists all properties as required; missing values are empty strings that code converts to `None`.
**Why:** current Sonnet models reject forced `tool_choice` with a 400, and structured outputs guarantee parseable JSON. Retries and timeouts are delegated to the SDK (`max_retries`, `timeout`).

### D-054: Untrusted data never enters the system prompt
**Decision:** system prompts are fixed, versioned strings (`prompts.py`, `PROMPT_VERSION`). Document text and patient answers travel only in the user message inside a `<case_data>` block that the system prompt declares untrusted; a closing tag inside the data is escaped.
**Why:** prompt-injection defense. Red-team tests check that injected text never reaches a system prompt.

### D-055: Evidence catalogue and output validator
**Decision:** the LLM sees an evidence catalogue of grounded facts with refs (`interview:<key>`, `doc:<id>`, `lab:<id>`, `dx:<id>`, `med:<id>`, `trend:<test>`, `score:<name>`). Every claim must cite a ref that exists, any quote must appear in that source, numbers must be traceable to the source or to code-computed values, and definitive or instruction-like wording is rejected. Failing items are dropped (findings) or the whole item is dropped (no supporting evidence); notes are stored on the job.
**Why:** an LLM claim is only kept if code can verify it.

### D-056: Grounding before engines
**Decision:** extracted values are checked against the OCR text; only grounded facts feed the engines. Printed reference limits must also appear in the text, otherwise they are discarded (the row becomes `range_not_available`). Ungrounded items are stored with `needs_review` and are never used. A regex extraction runs alongside and disagreements are stored as `extraction_disagreement`.
**Why:** "never invent a range"; hallucinated values must not turn into flags or scores.

### D-057: Missing inputs are never defaulted
**Decision:** removed the defaults that assumed `air` and `alert` for NEWS2 and the substring checks that turned "no mention of hypertension" into `False` for CHA₂DS₂-VASc. A comorbidity is `True` only when documented or reported, `False` only when the patient explicitly said they have no chronic conditions, otherwise unknown → `not_calculable`. CURB-65 urea is converted only when the unit is known.
**Why:** Missing ≠ Negative. Scores included: qSOFA, CURB-65, NEWS2, CHA₂DS₂-VASc only (the intake does not collect inputs for others).

### D-058: Trend rules need a known time span
**Decision:** a rule with `time_window_days` matches only when both dates are known and within the window. Series are sorted by printed date and include the same patient's earlier encounters; mixed, unconvertible units are not compared.
**Why:** an undated pair could otherwise be labelled "acute".

### D-059: Background job with idempotent re-runs
**Decision:** `POST /run` returns 202 and runs the pipeline as a FastAPI background task with its own DB session; the UI polls `GET /api/analysis/{id}`. A second run while one is active returns 409. Each run deletes the rows it derives (labs, entities, trends, scores, open engine conflicts, open red flags, pending AI insights) and keeps insights a doctor already decided.
**Why:** the UI must not block, and repeated runs must not duplicate data or erase decisions.

### D-060: Graceful degradation when the LLM is down
**Decision:** availability is checked up front and on every call. When unavailable, deterministic engines still run, extraction falls back to the regex path (provenance `regex_extracted_unverified`), AI features are skipped, and the job ends in status `unavailable`. The UI shows a clear message.

### D-061: Guideline library with FTS5 and sample content
**Decision:** passages live in `GUIDELINE_PASSAGES` with an SQLite FTS5 index (`guideline_passages_fts`, bm25 ranking, LIKE fallback). Sample passages are in `config/guidelines_sample.json`, every one labelled `SAMPLE – replace with verified source` and attributed to no real publication. `scripts/ingest_guidelines.py` loads verified sources (`--replace` to remove samples). A dose is shown only if quoted verbatim from the cited passage; drugs named are cross-checked against allergies and the interaction table.

### D-062: Vision path only in hosted mode, never auto-trusted
**Decision:** low-confidence images go to the hosted vision model; results are stored as `vision_fallback` entities with `grounded=false` and `review_status=read_from_handwriting_verify`. Local mode routes them to `needs_review`. The earlier implementation passed the wrong image keys and always failed; fixed.

### D-063: AI follow-up questions behind a flag and a safety filter
**Decision:** `AI_FOLLOWUPS_ENABLED` (default off). A proposal that maps to the question bank is left to the deterministic flow; otherwise it must be one short question with no disease names, no leading phrasing and no definitive wording. AI questions are scoped to their encounter (they were previously visible to every encounter).

### D-064: Rule-based priority alerts are not AI output
**Decision:** red-flag urgency comes from deterministic rules, so it is shown to doctors and staff on the dashboard. AI insights stay doctor/admin-only (403 for patients and staff, tested on every AI endpoint).

### D-065: Honest evaluation
**Decision:** the eval harness runs every case through the real pipeline and generates `docs/AI_EVAL_REPORT.md`; no number is typed in by hand. The previous report contained hard-coded values (vision recall, latency, token usage) and red-team cases counted as passed without checks; it was replaced. Metrics that need a hosted key (vision recall, real token usage) are reported as "not measured".

### D-066: Alembic chain repaired
**Decision:** the AI migration branched from an old revision and created a second head; it now follows `2fa2d5d870dc`. A new revision `8c9d0e1f2a3b` adds job usage/notes, `document_entities.review_status` and the FTS5 table.

---

## Milestone 18 Decisions — Automatic analysis and complaint-driven interview (2026-10-31)

### D-067: Analysis runs automatically
**Decision:** the analysis is triggered by patient activity instead of a doctor's button: debounced on each saved answer, immediate on interview completion and on processed documents. Per encounter at most one run is scheduled or running (a request during a run schedules exactly one more), and all runs (automatic and manual) are serialized globally.
**Why:** the doctor should see a ready analysis when opening the case. Debouncing bounds hosted-API cost; serialization avoids SQLite write contention and protects small local models. Finalized cases and cases without consent are never analysed. Each automatic run writes an `AI_ANALYSIS_AUTO_STARTED` audit event with actor `system`.

### D-068: Analyzed Conclusion is an AI insight, checked like the others
**Decision:** a new `analyzed_conclusion` LLM task writes 2–4 sentences plus cited key findings, next steps and information gaps. Code rejects definitive or instruction-like wording and untraceable numbers, keeps only resolvable findings, and attaches the urgency and the considerations that passed validation (the model cannot add new ones to that list). It is stored as `ai_generated_unverified` with Accept / Edit / Reject and shown to doctors only (dashboard and AI tab). A rule-based overview (reason, urgency, red flags, abnormal labs, conflicts) is always computed so the dashboard has content when the LLM is down.

### D-069: Free-text reason for visit drives the questionnaire
**Decision:** replaced the fixed disease-choice first question and its disease-specific branches with a free-text reason, generic characterisation questions for every complaint, and keyword-selected symptom modules. Matching is deterministic and auditable (keyword lists in `complaint_modules.py`, covering English, transliterated Hindi/Marathi and Devanagari) rather than LLM-generated, so the interview works offline and every patient-facing question is reviewed and translated in advance. AI follow-ups remain optional (`AI_FOLLOWUPS_ENABLED`). Localized choice answers ("हां (Yes)") are mapped to their English value for branching. Removed questions are retired, not deleted, so existing answers survive.

### D-070: New rule-based red flags from module answers
**Decision:** anaphylaxis-type swelling (EMERGENCY), GI bleeding, coughing blood, breathlessness at rest and thoughts of self-harm (URGENT) are detected by code from the new answers.
