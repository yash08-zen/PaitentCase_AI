# PatientCase AI (SIH26047) — Step-by-Step Build Prompt

> **How to use this file**
> Paste **Part 1 (Master Prompt)** once at the start of your AI coding session (Claude Code, Cursor, etc.) with both repos available.
> Then send **one milestone at a time** from Part 2 using the line:
> *"Execute Milestone M<N> exactly as specified. Stop at the end and send the Milestone Report."*
> Do not move to the next milestone until the current Definition of Done (DoD) is fully ticked.

---

# PART 1 — MASTER PROMPT

## 1. Role

You are a senior full-stack engineer building **PatientCase AI**, a patient case-taking and doctor-handoff web application, as a university major project / SIH prototype (requirement SIH26047). You work incrementally, verify everything by running it, and never claim something works unless you have executed it and seen the result.

## 2. Project context

PatientCase AI digitizes patient history collection before a consultation:

1. A patient (or clinic staff) registers and a unique **encounter** is created.
2. A **guided, rule-based adaptive interview** collects history (chief complaint, symptoms, medications, allergies, history, etc.).
3. The patient uploads a prior **prescription image**; real **OCR** extracts medication name / dosage text when legible.
4. The system builds a **structured case summary**, detects **missing information**, and flags **medication information discrepancies** between patient answers and the prescription using transparent rules.
5. A **doctor** reviews the case, corrects/accepts/rejects extracted fields, resolves discrepancies, adds notes, and **finalizes**. Everything **persists** across refresh and re-login.

Advanced goals (P1/P2): basic local/offline operation, multilingual voice (English, Hindi, Marathi), handwritten/multilingual OCR, full multilingual voice conversation.

## 3. Existing assets (do not rewrite from scratch)

| Asset | Role |
|---|---|
| `PatientCase_AI` | Existing **FastAPI backend** project (models, services, APIs, DB). Also contains an old frontend that must be **retired**. |
| `PatientCase-Seminar` | Existing **seminar frontend**. This becomes the **single, only active frontend**. |

**Integration decision (mandatory):** Use `PatientCase-Seminar` as the only active UI, connect it to the real backend, replace all mock data/simulated OCR with real API calls, and stop serving the old `PatientCase_AI` frontend. Never maintain two competing frontends. Preserve backend models/services/APIs that are still needed.

## 4. Priority levels

- **P0 — Required MVP:** must work end to end and persist.
- **P1 — High priority:** after P0 is stable.
- **P2 — Advanced/stretch:** do not claim complete without evidence from tests.

## 5. Safety and clinical boundaries (non-negotiable)

- The app **must not** diagnose, prescribe, recommend treatment, make triage decisions, or output disease probability/severity/urgency.
- **Missing information ≠ negative answer.** An unreported allergy is displayed as "not provided / unknown", never "no allergies".
- **OCR output is unverified evidence** until a doctor reviews it.
- Medication conflict detection means **information discrepancy** ("Medication information requires verification"), **not** drug-interaction checking. Never assume which source is correct, or that the prescription is current.
- The "completeness / readiness indicator" is deterministic and based only on configured fields + review status.
- Label the product everywhere relevant as **a prototype supporting clinician review, not a diagnostic tool**.
- Use only **synthetic** patient data (or properly permissioned, de-identified samples).

## 6. Engineering rules (apply to every milestone)

1. **Audit before change.** Read existing code first; extend rather than rewrite. Reuse the current stack and schema where practical.
2. **Backend is the single source of truth.** No hard-coded patient/case values in the frontend for core workflows.
3. **Never show success before the backend confirms it** (saves, OCR, voice transcription, doctor actions, finalization).
4. **Persist incrementally** and verify persistence after refresh/restart/re-login.
5. **Validate everything**: inputs, file type/size, IDs, roles. Return controlled, actionable errors; never expose stack traces, secrets, or unnecessary patient data.
6. **Enforce roles in the backend** (not only by hiding UI). Test direct API calls.
7. **Preserve provenance:** every important field carries its source — `patient_reported`, `document_extracted_unverified`, `doctor_verified`, or `missing_unknown`. Never overwrite original OCR text when a doctor corrects a value.
8. **Every UI screen has loading, empty, success, and error states.**
9. **Secrets** live in environment variables / `.env` (git-ignored), never in source or the frontend bundle. Provide `.env.example`.
10. **Tests with each milestone.** Backend: `pytest`. E2E: Playwright (or Cypress if already used). A milestone without passing tests is not done.
11. **Small, reviewable commits** with clear messages: `M<N>: <what>`. Work on a branch per milestone (`milestone/m<N>-<slug>`).
12. **Do not add dependencies** without stating why, license, and that it works offline if relevant. Keep a `docs/DECISIONS.md` log.
13. **Be honest.** If something is partial, mock, or untested, say so in the report. Never advertise languages, document types, or offline features that were not tested.

## 7. Suggested technical approach (confirm after audit)

| Layer | Approach |
|---|---|
| Frontend | Existing `PatientCase-Seminar` |
| Backend | Existing FastAPI app |
| API | REST, consistent request/response schemas, OpenAPI docs |
| Database | Existing DB; SQLite acceptable for local prototype; use migrations (Alembic) if the project already uses SQLAlchemy |
| OCR | Real engine for clear **printed** prescriptions first (e.g., Tesseract via `pytesseract` with OpenCV preprocessing; evaluate PaddleOCR/EasyOCR only if needed) |
| Medication extraction | Rules/regex/normalization over OCR text + manual correction UI |
| Voice | Start with the simplest tested option (e.g., browser speech APIs or a local model like Whisper) with text/touch fallback always available |
| Auth | Existing secure implementation; hashed passwords; role-based authorization |
| Offline | Local frontend + backend + DB; remote-only features degrade gracefully |
| Deployment | Documented local run steps; Docker optional |

## 8. Required response format after EVERY milestone — "Milestone Report"

When a milestone is finished, stop and output exactly this structure:

```
## Milestone Report — M<N>: <title>
**Status:** Complete | Partial | Blocked
**What was built:** (bullets, with file paths)
**API endpoints added/changed:** (method + path + purpose)
**DB changes / migrations:**
**How to run and verify:** (exact commands)
**Tests added and results:** (command + pass/fail counts)
**DoD checklist:** (copy the milestone's checklist, tick each item, add evidence)
**Known issues / limitations (honest):**
**Deviations from spec and why:**
**Ready for next milestone?** Yes / No (+ reason)
```

Do **not** start the next milestone on your own.

## 9. Target repository conventions

```
PatientCase_AI/                # backend (FastAPI)
  app/ (routers, services, models, schemas, core, rules)
  tests/
  migrations/
  uploads/                     # git-ignored, protected storage
  .env.example
PatientCase-Seminar/           # single active frontend
  src/ (pages, components, api client, state)
docs/
  DECISIONS.md  API_MAP.md  RUNBOOK.md  DEMO_SCRIPT.md  TEST_REPORT.md  LIMITATIONS.md
```

Adapt to the actual structure found in the audit; record any difference in `docs/DECISIONS.md`.

---

# PART 2 — MILESTONES

## Roadmap at a glance

| # | Milestone | Priority | PRD refs |
|---|---|---|---|
| M0 | Audit, plan, and baseline run | P0 | FR-11 (prep) |
| M1 | Single-frontend integration foundation | P0 | FR-11 |
| M2 | Authentication, roles, and audit logging | P0 | FR-14, FR-10 (prep) |
| M3 | Patient registration and encounters | P0 | FR-01 |
| M4 | Guided interview + adaptive rule engine | P0 | FR-02, FR-03 |
| M5 | Structured history, summary, missing info, completeness | P0 | FR-04, FR-05, FR-09 |
| M6 | Prescription upload + real OCR | P0 | FR-07 |
| M7 | Medication extraction + discrepancy rules | P0 | FR-07, FR-08 |
| M8 | Doctor dashboard, review, and persistence | P0 | FR-06, FR-10 |
| M9 | Hardening: validation, errors, security, UX states | P0 | FR-14 |
| M10 | End-to-end demo, test suite, **P0 release gate** | P0 | FR-15 |
| M11 | Basic local / offline operation | P1 | FR-13 |
| M12 | Multilingual voice (English → Hindi → Marathi) | P1 | FR-12 |
| M13 | Advanced stretch (handwriting OCR, full voice conversation) | P2 | FR-07, FR-12 |
| M14 | Documentation, final validation, handover | P0 | all |

**Dependency order:** M0 → M1 → M2 → M3 → M4 → M5 → M6 → M7 → M8 → M9 → M10 (P0 gate) → M11 → M12 → M13 (optional) → M14.

---

## M0 — Audit, Plan, and Baseline Run

**Objective:** Understand exactly what exists before changing anything.

**Tasks**
1. Inventory both repos: languages, frameworks, versions, folder structure, dependencies, DB engine and schema, existing models, routers, services, auth approach, OCR placeholder, any old frontend files in `PatientCase_AI`.
2. Run the backend and `PatientCase-Seminar` locally. Record exact commands, ports, and any errors fixed.
3. For **every screen** in the seminar frontend, list: route/page, what data it shows, whether it uses mock data, and which backend endpoint (existing or missing) should serve it. Produce `docs/API_MAP.md` (table: Screen → Action → Endpoint → Status [exists / needs change / missing]).
4. List every place mock data, hard-coded values, or simulated OCR appear (file + line).
5. Identify whether the backend depends on the old frontend in any way.
6. Produce a gap analysis against FR-01…FR-15 (Done / Partial / Missing).
7. Propose any adjustments to the milestone plan in `docs/DECISIONS.md`.

**Deliverables:** `docs/API_MAP.md`, `docs/DECISIONS.md` (initial), `docs/GAP_ANALYSIS.md`, `docs/RUNBOOK.md` (how to start both apps).

**Do NOT** modify application code in this milestone (except trivial fixes needed just to run).

**Definition of Done**
- [ ] Both projects run locally; commands documented in `docs/RUNBOOK.md`.
- [ ] `API_MAP.md` covers **every** frontend screen with status.
- [ ] All mock/simulated data locations listed.
- [ ] Gap analysis lists each FR as Done/Partial/Missing with evidence.
- [ ] Confirmed (yes/no, with proof) whether backend depends on the old frontend.
- [ ] Milestone Report delivered.

---

## M1 — Single-Frontend Integration Foundation

**Objective:** `PatientCase-Seminar` is the only frontend and can talk to the real backend.

**Tasks**
1. Create a typed **API client** in the frontend (base URL from env, JSON handling, error normalization, auth header injection later).
2. Configure **CORS** and environment settings in the backend; add `.env.example` for both projects.
3. Add `GET /health` (app + DB status) and surface it in the frontend (dev-only indicator ok).
4. Introduce DB **migrations** (or confirm existing mechanism) and a **seed script** skeleton for synthetic data.
5. Retire the old `PatientCase_AI` frontend: remove it from startup/serving; move to `legacy/` or delete **only after** M0 confirmed nothing depends on it. Document in `DECISIONS.md`.
6. Add shared frontend primitives: loading spinner, empty state, error banner, toast for success/failure.
7. Add a visible "Prototype supporting clinician review — not a diagnostic tool" notice in the app layout.

**Definition of Done**
- [ ] Frontend calls `GET /health` on the real backend and shows result; no CORS errors.
- [ ] The old frontend is not served or referenced by startup scripts/README.
- [ ] API client handles network error, 4xx, 5xx with normalized messages (unit-tested).
- [ ] `.env.example` exists for both projects; no secrets committed.
- [ ] Migrations run from a clean DB to current schema with one command.
- [ ] Clinical-boundary notice visible in the layout.
- [ ] Backend tests (health) and a frontend smoke test pass.
- [ ] Milestone Report delivered.

---

## M2 — Authentication, Roles, and Audit Logging

**Objective:** Secure access with backend-enforced roles; audit trail foundation.

**Roles:** Patient, Doctor, Nurse/Clinic staff, Administrator (least privilege).

**Tasks**
1. Review the existing auth. Ensure passwords are **hashed** (bcrypt/argon2), tokens/sessions are managed safely (expiry, refresh or re-login), and no secrets are in code.
2. Implement role-based dependency/guard in FastAPI (e.g., `require_roles("doctor")`) applied to routes; define a **permissions matrix** in `docs/DECISIONS.md`.
3. Record-level access: doctors/staff see only authorized encounters; patients see only their own.
4. Create **audit_event** model + service: actor, action, resource type/id, timestamp, change summary. Log login, logout, failed login, and (later milestones) key actions.
5. Frontend: login screen, protected routes, role-based navigation, session expiry handling, logout.
6. Seed demo users (one per role) with documented synthetic credentials for local only.

**Definition of Done**
- [ ] Passwords hashed; plaintext never stored/logged.
- [ ] Each role can access only its permitted routes; **direct API calls** with the wrong role return 403 (tests prove it).
- [ ] Unauthenticated requests return 401.
- [ ] Session expiry redirects to login with a clear message.
- [ ] Audit events written for login/logout/failed login and visible in DB (admin view optional).
- [ ] No tokens/secrets in frontend bundle or logs.
- [ ] Tests: ≥ 1 test per role boundary; all pass.
- [ ] Milestone Report delivered.

---

## M3 — Patient Registration and Encounters (FR-01)

**Objective:** Real registration and encounter creation, persisted.

**Tasks**
1. Backend: `Patient` and `Encounter` models/endpoints — create, read, list (role-scoped), update limited fields. Fields: patient ID, name, age/DOB (if used), gender (if collected), contact, preferred language. Encounter: ID, patient ID, date, status, interview state.
2. Unique IDs; prevent duplicate accidental submissions (idempotency/disable-on-submit + server check).
3. Consent capture (required fields/flag stored with timestamp) before the interview begins.
4. Frontend: registration form wired to the API, validation messages, success/error states, patient selection/search for staff.
5. Replace any mock registration data.

**Definition of Done**
- [ ] A patient registered through the UI exists in the DB with a unique ID and correct linked encounter.
- [ ] Data is still there after browser refresh and backend restart.
- [ ] Missing/invalid fields show clear errors; server also validates (tests for invalid payloads).
- [ ] Double-clicking submit does not create duplicates.
- [ ] Consent is recorded with timestamp; interview cannot start without it.
- [ ] Role scoping verified (patient cannot list other patients).
- [ ] Tests pass; Milestone Report delivered.

---

## M4 — Guided Interview and Adaptive Rule Engine (FR-02, FR-03)

**Objective:** One-question-at-a-time interview with deterministic, testable adaptive follow-ups.

**Tasks**
1. Define the **question bank as configuration** (JSON/YAML/DB): id, text, answer type (text/choice/yes-no/number/date), required flag, section, and **rules** (`show_if`, `skip_if`, follow-up triggers). Cover: chief complaint; symptom location/duration/severity; associated symptoms; relevant medical history; current medications; allergies; previous surgery/treatment; configured extras.
2. Implement the **adaptive engine** in the backend: given encounter state + answers → next question(s) and "interview complete?" decision. Must be deterministic and unit-tested. (An LLM, if ever used, may only help rephrase/normalize — never invent clinical questions.)
3. Endpoints: get next question, submit answer (saved **incrementally**), edit a previous answer, navigate back, get progress, resume interrupted session.
4. Store each answer as a **history response** with: encounter ID, field/question ID, value, source=`patient_reported`, timestamp, confirmation status.
5. Frontend: question screen (one per screen), progress bar, back/edit, large touch targets, simple wording, language selector placeholder, text/touch input.
6. Handle interrupted sessions: resume at the right question or mark incomplete.

**Definition of Done**
- [ ] Each answer is saved to the backend immediately and linked to the correct encounter.
- [ ] Known test inputs trigger the expected follow-up questions (≥ 8 unit tests covering branches, e.g., "pain" → location/severity; "no medications" → skip dosage questions).
- [ ] Already-answered fields are not re-asked; irrelevant branches skipped.
- [ ] Patient can go back, correct an answer, and the flow re-evaluates correctly.
- [ ] Closing the browser mid-interview and returning resumes correctly (or clearly shows "incomplete").
- [ ] Engine determines completion deterministically from configured required fields.
- [ ] No hard-coded questions remain in the frontend.
- [ ] Tests pass; Milestone Report delivered.

---

## M5 — Structured History, Summary, Missing Info, Completeness (FR-04, FR-05, FR-09)

**Objective:** Backend-generated summary with provenance and honest handling of unknowns.

**Tasks**
1. Summary service builds a **structured case summary** from saved data only, grouped by sections, with each value labelled by source: patient-reported / document-extracted (unverified) / doctor-verified / missing-unknown.
2. **Missing-information detection:** for each configured required/relevant field that is missing/unknown/incomplete, produce a checklist item. Treat blanks as **"Not provided / unknown"**, never as "No".
3. **Completeness indicator:** deterministic formula from configured fields + review status; document the formula in `DECISIONS.md`. It must **not** imply risk, severity, or probability.
4. Endpoints: `GET /encounters/{id}/summary`, `GET /encounters/{id}/missing`.
5. Frontend: patient-facing completion screen and summary view; missing-info checklist that updates when fields are completed. Remove any hard-coded demo summary values.

**Definition of Done**
- [ ] Summary content changes when answers change (test: edit answer → summary updates).
- [ ] An unanswered allergy question renders "Not provided / unknown" and appears in the missing list (explicit test).
- [ ] Completing the field removes it from the missing list.
- [ ] Each summary field shows its source label.
- [ ] Completeness indicator is reproducible: same inputs → same value (unit tests); no medical-risk wording anywhere.
- [ ] No hard-coded summary values remain in the frontend.
- [ ] Tests pass; Milestone Report delivered.

---

## M6 — Prescription Upload and Real OCR (FR-07)

**Objective:** Real file upload and a real OCR engine processing clear printed prescriptions.

**Tasks**
1. Upload endpoint: accept supported image formats (and PDF only if the stack supports it). **Validate type (by content, not just extension) and size**; store originals in protected storage outside the web root; link to encounter; generate non-guessable filenames.
2. Replace the OCR placeholder with a **real OCR engine**. Add image preprocessing (grayscale, denoise, deskew/threshold) as needed.
3. Document model: file location, type, upload time, OCR status (`pending`, `processing`, `completed`, `needs_review`, `failed`), raw OCR text, confidence/metadata.
4. Run OCR asynchronously (background task/queue) so the UI never freezes; expose status polling.
5. **Failure safety:** OCR exceptions/empty results set `failed`/`needs_review`, **keep the original upload**, and never crash the app.
6. Frontend: upload UI with preview, progress/status, error messages, and display of raw OCR text with an "unverified" label.
7. Create a **test set** of ≥ 5 clear printed prescription images (synthetic/permissioned) plus negative cases (blurry, rotated, wrong type, empty).

**Definition of Done**
- [ ] A real test image is uploaded via the UI, processed by the backend OCR engine, and the extracted text is stored and displayed (no simulated output remains in code).
- [ ] Unsupported file type and oversize files are rejected with clear messages (tests).
- [ ] OCR failure leaves the original upload intact and shows `failed`/`needs_review` (test with a corrupt/blank image).
- [ ] Status transitions pending → processing → completed/failed are visible in the UI.
- [ ] Uploaded files are not publicly accessible without authorization (tested by direct URL access).
- [ ] OCR time on a clear image is recorded (target: under ~15 s on test hardware, if feasible).
- [ ] Tests pass; Milestone Report delivered with OCR results on the test set (honest accuracy notes).

---

## M7 — Medication Extraction and Discrepancy Rules (FR-07, FR-08)

**Objective:** Pull limited structured medication fields from OCR text and flag information discrepancies transparently.

**Tasks**
1. Extraction rules over OCR text: **medication name/text**, **dosage/strength text**, and **frequency/instructions/date** when legible. Store as `medication_item` with source=`document_extracted_unverified`, link to the document, and mark uncertain fields `needs_review`.
2. Normalization (units, common abbreviations such as OD/BD/TDS) — rule-based, with the **raw text always preserved**.
3. **Conflict engine** (rule-based, transparent). Required rules at minimum:
   - Patient reports **no current medication** but the document lists a medicine → flag **"Medication information requires verification."**
   - Patient-reported medication name/dosage differs from the extracted one → flag.
   - Prescription is old/undated or unreadable → flag as unverifiable (not a conflict verdict).
   - Matching data → no flag.
4. `conflict` records: encounter ID, compared sources and values, rule ID triggered, status (`open`/`resolved`), resolution note.
5. **Never** infer which source is correct, that the patient is taking the drug, or recommend any clinical action. This is not drug-interaction checking.
6. Frontend: show extracted fields with uncertainty markers and the conflict list with the exact rule/sources shown.

**Definition of Done**
- [ ] ≥ 6 documented test cases (table in `docs/TEST_REPORT.md`) produce the expected flags: no-meds-vs-prescription, name mismatch, dosage mismatch, matching, old/undated, unreadable.
- [ ] Each flag stores the compared sources/values and the rule ID (verified in DB and UI).
- [ ] Raw OCR text is retained after normalization.
- [ ] Wording audit: no diagnosis/treatment/interaction language anywhere in rules, API, or UI.
- [ ] Uncertain extractions are marked for review rather than silently accepted.
- [ ] Tests pass; Milestone Report delivered.

---

## M8 — Doctor Dashboard, Review, and Persistence (FR-06, FR-10)

**Objective:** Doctors can review everything and every action persists reliably.

**Tasks**
1. Doctor dashboard: list of authorized encounters with status/completeness; open case view.
2. Case view shows: patient/encounter details, history by section with source labels, missing fields, **original document viewer beside extracted fields**, extracted medication fields, conflicts, review status.
3. Actions (all through backend APIs): edit/correct a field, accept/reject an extracted field, resolve a conflict with note, add general notes, save draft, **finalize**.
4. `doctor_review` model: encounter ID, reviewer ID, action, changed fields/decision, notes, status, timestamp. Corrections must **not erase** the original OCR/patient value (keep history/versioning).
5. Use **transactions**; on failure roll back to a consistent state and show an error. Add idempotency so duplicate submits do not create duplicate actions.
6. Write an **audit event** for each doctor action.
7. After finalization, define and enforce behavior (e.g., read-only unless explicitly reopened, with audit).

**Definition of Done**
- [ ] Edits, accept/reject, conflict resolution, notes, and finalization **survive refresh and re-login** (E2E test).
- [ ] A forced backend failure (simulated) shows an error and does **not** display success; DB remains consistent (test).
- [ ] Duplicate submission does not create duplicate review actions (test).
- [ ] Every action targets the selected encounter (test with two encounters).
- [ ] Original OCR text and original patient values remain retrievable after correction.
- [ ] Audit events exist for each action type.
- [ ] Only doctors (and authorized roles) can perform review actions — direct API test with other roles returns 403.
- [ ] Tests pass; Milestone Report delivered.

---

## M9 — Hardening: Validation, Errors, Security, UX States (FR-14)

**Objective:** The P0 app behaves safely under bad input and failures.

**Tasks**
1. Server-side validation schemas on all endpoints; length limits; sanitized outputs (XSS-safe rendering).
2. Global exception handler: controlled JSON errors, correlation IDs, **no stack traces or secrets** to clients; structured server logs with **no sensitive patient data**.
3. Security checks: rate limiting on login/upload (basic), secure headers, safe file handling (path traversal, content sniffing), CORS restricted to the frontend origin, token expiry.
4. Frontend: verify **loading / empty / success / error** states on every screen; handle network loss and API timeouts gracefully; disable buttons while submitting.
5. Run a checklist pass over each FR-14 requirement and fix gaps.
6. Dependency check (known vulnerabilities) and remove unused packages.

**Definition of Done**
- [ ] Fuzz/negative tests: invalid payloads, wrong types, oversized input, SQL-injection and script strings return controlled errors (no 500s).
- [ ] No stack traces or secrets in any API response (tested).
- [ ] Logs contain no passwords/tokens/full patient records (manual log review documented).
- [ ] Direct API requests cannot bypass role restrictions (full role × endpoint matrix test, documented in `TEST_REPORT.md`).
- [ ] Every screen demonstrably has loading/empty/error states (screenshot checklist or E2E assertions).
- [ ] Uploads cannot be fetched without authorization and cannot escape the storage directory.
- [ ] Dependency audit run and results recorded.
- [ ] Tests pass; Milestone Report delivered.

---

## M10 — End-to-End Demo, Test Suite, and P0 Release Gate (FR-15)

**Objective:** Prove the whole P0 workflow works repeatedly and honestly.

**Tasks**
1. Seed script: **synthetic** patients + a documented set of prescription test images; distinguish seeded examples from live processing in the UI/docs.
2. Write the E2E test(s) (Playwright) that automate the full demo sequence:
   1. Register a sample patient and create an encounter (with consent).
   2. Complete an adaptive symptom interview.
   3. Leave a required field incomplete → missing-information flag appears.
   4. Upload a clear prescription image → real OCR runs.
   5. Extracted medication text/dosage shown where legible.
   6. Patient says no current medication → discrepancy flagged.
   7. Doctor logs in, opens the case.
   8. Doctor corrects/accepts extraction, resolves the conflict, adds a note, finalizes.
   9. Refresh/reopen → everything persisted.
3. Write `docs/DEMO_SCRIPT.md` (step-by-step with expected screens) and `docs/TEST_REPORT.md` (all test results, OCR results on the test set, known failures).
4. Clean-machine run: from a fresh clone, follow `RUNBOOK.md` and get the demo working.
5. Walk through every P0 item and record complete/partial evidence in `docs/P0_CHECKLIST.md`.

**P0 Release Gate — Definition of Done**
- [ ] `PatientCase-Seminar` is the sole active frontend and uses the real backend; **no mock data** remains in core flows (grep evidence).
- [ ] Registration and adaptive case-taking work with persisted data.
- [ ] Summary and missing-information indicators reflect backend state.
- [ ] A real clear prescription image is processed by actual OCR.
- [ ] Medication text/dosage can be reviewed and corrected.
- [ ] Rule-based discrepancies are flagged for doctor verification.
- [ ] Doctor review actions persist across refresh and re-login.
- [ ] Basic authorization and error handling pass tests.
- [ ] The full demo sequence passes as an automated E2E test **and** manually, repeatedly (≥ 3 consecutive runs).
- [ ] A fresh-clone setup works by following `RUNBOOK.md` only.
- [ ] All claims in docs match what was tested (no inflated language/offline/OCR claims).
- [ ] Milestone Report delivered with the completed P0 checklist.

---

## M11 — Basic Local / Offline Operation (FR-13) — P1

**Objective:** Essential case-taking works on one device without continuous internet.

**Tasks**
1. Inventory every external/online dependency (CDNs, fonts, APIs, cloud OCR/voice). Bundle assets locally; remove CDN reliance for core flows.
2. Ensure frontend + backend + local DB run entirely on `localhost` with no internet (test with network disabled).
3. For online-only features (remote speech, any cloud OCR), show an explicit **"unavailable offline"** state and offer text/touch or manual-review alternatives.
4. If any synchronization is attempted, it must surface failures/conflicts and never silently overwrite data. **Multi-device sync is not implied**; if not built, say so in `LIMITATIONS.md`.
5. Restart persistence tests.

**Definition of Done**
- [ ] With the network disabled: registration, interview, summary, and doctor review work (E2E run offline).
- [ ] Data remains after restarting the local app.
- [ ] Online-only dependencies are listed; each has a visible unavailable state and fallback.
- [ ] No silent overwrite on any sync path (or sync explicitly not implemented and documented).
- [ ] `LIMITATIONS.md` lists exactly which functions are offline-capable (only tested ones).
- [ ] Tests pass; Milestone Report delivered.

---

## M12 — Multilingual Voice Conversation (FR-12) — P1

**Objective:** Voice input and spoken questions for a *tested* subset of languages, never blocking text/touch.

**Phases**
- **12a — English end-to-end:** language selection, microphone permission handling, recording indicator, silence/timeout handling, speech-to-text, **transcript confirmation/correction**, repeat/re-record, text-to-speech for questions, text/touch fallback.
- **12b — Hindi, then 12c — Marathi:** repeat the same tested loop for each language, only if the chosen speech tools genuinely support it.

**Tasks**
1. Language selection stored on the patient/encounter and **maintained** across the interview.
2. Voice loop: question displayed + spoken → patient speaks → transcript shown → confirm/edit → mapped to the structured field → saved to backend → adaptive engine selects next question.
3. **Low-confidence or uncertain transcripts must be confirmed** — never silently accepted (especially for medications/allergies).
4. Error handling: mic denied, no speech, noise, service unavailable → clear message + text/touch fallback with progress preserved.
5. Evaluate per language on a small defined question set (5–10 questions × several utterances): record success rate, mixed-language, accent, and medical-term issues in `TEST_REPORT.md`.

**Definition of Done**
- [ ] **Per enabled language**, a defined set of questions completes the full voice loop end to end and answers persist.
- [ ] Language choice is maintained across questions.
- [ ] Denied microphone, silence, noise, and service-unavailable cases each show a controlled message and the text/touch fallback works without losing progress (tests/manual evidence).
- [ ] Uncertain transcripts require confirmation.
- [ ] Evaluation results (per language/condition) are recorded honestly; **only tested languages are advertised in the UI/docs**.
- [ ] Tests pass; Milestone Report delivered.

---

## M13 — Advanced Stretch (P2) — only with evidence

**Objective:** Attempt advanced capabilities without overclaiming.

**Candidate items (pick only if time permits)**
- Handwritten prescription OCR across handwriting styles / Indian languages.
- Robust mixed-language and regional-accent speech understanding.
- Full multilingual voice conversation across the whole adaptive interview.
- Offline OCR/voice for selected functions and safe sync on reconnect.
- Multi-device synchronization.

**Rules**
1. Build an **evaluation set first** (representative documents/utterances) and a scoring script.
2. Report measured results (precision/recall or success rate) per language/document type.
3. Keep uncertainty visible in the UI and require human review.
4. If results are weak, document the limitation instead of claiming support.

**Definition of Done (per item attempted)**
- [ ] Evaluation dataset and scoring script committed (synthetic/permissioned data only).
- [ ] Measured results recorded in `TEST_REPORT.md`.
- [ ] UI shows uncertainty/low-confidence states and human-review path.
- [ ] `LIMITATIONS.md` states exactly what is and is not supported.
- [ ] No feature described as "complete" without passing evidence.

---

## M14 — Documentation, Final Validation, and Handover

**Objective:** A reviewer can run, understand, and evaluate the project without you.

**Tasks**
1. Final docs: `README.md` (overview, architecture, setup), `RUNBOOK.md`, `API_MAP.md` (final), `DEMO_SCRIPT.md`, `TEST_REPORT.md`, `LIMITATIONS.md`, `DECISIONS.md`.
2. Architecture and workflow diagrams updated to match the final implementation (system architecture, end-to-end flow, OCR/discrepancy flow, data model).
3. Success-metrics table with **measured** values: workflows completed end to end, persistence after reload, missing fields correctly identified, OCR extraction results on the test set, discrepancies correctly flagged, speech success by language/condition, offline workflow completion, authorization/error test pass counts.
4. Final regression: run the entire test suite and the E2E demo on a fresh clone.
5. Tag a release (`v1.0-prototype`).

**Definition of Done**
- [ ] A new person can set up and run the demo from the README alone.
- [ ] All docs match what is actually implemented and tested.
- [ ] Success metrics are measured numbers, not estimates.
- [ ] `LIMITATIONS.md` honestly lists: partial/not-implemented items, supported languages/document types, offline limits, and the clinical-boundary statement.
- [ ] Full test suite + E2E pass on a fresh clone; release tagged.
- [ ] Final Milestone Report delivered.

---

# PART 3 — GLOBAL DEFINITION OF DONE (project level)

The project is complete for demonstration when **all** are true:

- [ ] `PatientCase-Seminar` is the sole active frontend and uses the actual backend.
- [ ] Registration and adaptive case-taking work with persisted data.
- [ ] Summary and missing-information indicators reflect backend state.
- [ ] A real, clear prescription image is processed by actual OCR.
- [ ] Medication text/dosage can be reviewed and corrected.
- [ ] Rule-based medication discrepancies are flagged for doctor verification.
- [ ] Doctor review actions persist across refresh and re-login.
- [ ] Basic authorization and error handling pass tests.
- [ ] The sample scenario can be repeated end to end.
- [ ] Voice and offline claims match exactly what has been implemented **and tested**.
- [ ] No feature diagnoses, prescribes, recommends treatment, or implies medical risk.

---

# PART 4 — QUICK-START MESSAGES (copy/paste)

**Kick-off (send first, after pasting Part 1):**
> Acknowledge the master prompt in 5 bullet points (role, priorities, safety rules, report format, working rules). Then execute **Milestone M0** exactly as specified. Stop at the end and send the Milestone Report.

**For each next step:**
> M<N−1> is approved. Execute **Milestone M<N>** exactly as specified (paste the milestone section). Follow all engineering rules. Run all tests. Stop at the end and send the Milestone Report.

**If a milestone is rejected:**
> M<N> is not approved because: <reason>. Fix only these items, re-run the tests, and re-send the Milestone Report with updated evidence.

**If you get stuck / drift:**
> Stop. Re-read the Master Prompt sections 5 and 6. List which rules you may have violated, fix them, and continue the current milestone only.
