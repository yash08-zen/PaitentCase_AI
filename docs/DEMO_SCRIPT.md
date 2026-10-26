# PatientCase AI — End-to-End Demo Script (Milestone M10 / FR-15)

## Overview & Demo Objectives
This script provides an evaluative, step-by-step walkthrough for clinical reviewers, hackathon judges, and evaluators to test and demonstrate **PatientCase AI (SIH26047)** end to end.

**Core Clinical Premise:**
PatientCase AI is an intake and handoff documentation assistant. It strictly adheres to **non-diagnostic boundaries**: it does **not** diagnose conditions, recommend medications, or calculate clinical risk scores. It organizes patient-reported symptoms, extracts prescription text using local offline OCR, calculates data completeness (Missing $\neq$ Negative), flags rule-based discrepancies, and facilitates physician review and case locking.

---

## 1. Demo Credentials & Environment Setup

### Default Accounts
| Role | Username | Password | Purpose / Scoping |
|---|---|---|---|
| **Doctor** | `doctor` | `Doctor@1234` | Clinical dashboard, review notes, conflict reconciliation, encounter finalization |
| **Patient** | `patient` | `Patient@1234` | Self-intake, view own record, answer interview questions |
| **Staff** | `staff` | `Staff@1234` | Patient registration, intake facilitation, document upload |
| **Admin** | `admin` | `Admin@1234` | User management, security monitoring, immutable audit log |

### Pre-Flight Verification
1. **Start Backend Server:**
   ```powershell
   cd "d:\Projects\New PatientCase AI\backend"
   .\.venv312\Scripts\uvicorn.exe app.main:app --port 8000 --reload
   ```
2. **Start Frontend Client:**
   ```powershell
   cd "d:\Projects\New PatientCase AI\frontend"
   npm run dev
   ```
3. **Seed Clean Demo Database (Optional / Idempotent):**
   ```powershell
   cd "d:\Projects\New PatientCase AI\backend"
   .\.venv312\Scripts\python.exe -m app.scripts.seed_demo_e2e
   ```

---

## 2. Walkthrough Steps (Full 9-Step Lifecycle)

### Step 1: Patient Registration & Consent
1. Navigate to `http://localhost:5173` and log in as `staff` (`Staff@1234`).
2. Click **Register Patient** or navigate to `/register`.
3. Fill out the registration form:
   - **Full Name:** `Devendra Joshi`
   - **Age:** `48`
   - **Gender:** `Male`
   - **Contact Number:** `9819922334`
   - **Preferred Language:** `English`
   - **Chief Complaint:** `Persistent dry cough and chest tightness for 5 days`
   - **Informed Consent:** Check the box *(Consent is required before interview can proceed)*.
4. Click **Register and continue**.
5. **Expected Result:** Patient record is persisted with unique integer ID (`P-<id>`). An encounter is automatically created with `consent_given: true` and timestamp. An immutable `ENCOUNTER_CREATED` audit event is recorded.

---

### Step 2: Adaptive Symptom Interview & Deterministic Branching
1. The app automatically enters the **Adaptive Interview** interface.
2. The deterministic rule engine serves Question 1:
   - **Question:** *What is troubling you the most today?*
   - **Action:** Select `Cough`.
3. Question 2:
   - **Question:** *How long have you had this problem?*
   - **Action:** Select `4 to 7 days`.
4. Question 3:
   - **Question:** *How severe is your discomfort right now?*
   - **Action:** Select `6`.
5. Observe **Dynamic Branching**:
   - Because `Cough` was selected, the engine adds follow-up question: *How frequently do you experience this symptom?*
   - **Action:** Select `Daily episodes`.
6. Question 5:
   - **Question:** *Have you had a fever or elevated body temperature?*
   - **Action:** Select `Yes`.
7. Question 6:
   - **Question:** *Do you have any long-term or chronic medical conditions?*
   - **Action:** Select `No` *(Engine immediately skips condition detail follow-ups)*.
8. Question 7:
   - **Question:** *Are you currently taking any prescription medicines, supplements, or regular tablets?*
   - **Action:** Select `No` *(Engine records patient denial of medications)*.

---

### Step 3: Missing Information Checklist (Missing $\neq$ Negative)
1. Intentionally stop answering before providing allergy status (`has_allergies`).
2. Navigate to **Summary** / Case Review.
3. Observe the **Missing Information** checklist:
   - `has_allergies` is displayed with status: `Not provided / unknown`.
   - The UI explicitly highlights: **Missing $\neq$ Negative** — the clinical record treats omitted allergy data as unknown, never assuming the patient has no allergies.
4. Observe the **Completeness Score**:
   - Readiness score displays partial completeness (e.g., `75% - Partially Ready`).
   - Non-diagnostic boundary disclaimer is prominently shown: *"This score reflects case data completeness only. It is NOT a measure of diagnostic accuracy or patient health."*

---

### Step 4: Prescription Document Upload & Local Offline OCR
1. Navigate to **Medical Documents** (`/documents`).
2. Drag and drop or upload `backend/tests/test_images/rx_sample_1_amoxicillin.png` (or a printed prescription scan).
3. Select Document Type: `Prescription (Printed Rx)`.
4. The backend performs file integrity and content sniffing (preventing executable MIME spoofing).
5. The local RapidOCR / ONNX engine runs asynchronously:
   - Preprocessing: CLAHE contrast enhancement and deskewing.
   - Text detection and recognition.
6. **Expected Result:** Document status updates from `uploaded` to `processed`. Extracted text is displayed in the unverified document card:
   - Extracted text: `Rx: Amoxicillin 500mg capsules TID x 7 days`
   - Confidence score: `92%`
   - Provenance tag: `document_extracted_unverified`

---

### Step 5: Rule-Based Discrepancy Detection
1. The discrepancy engine evaluates clinical rules across sources:
   - Source A (`patient_reported`): Patient answered `current_medications = "No"`.
   - Source B (`document_extracted_unverified`): Uploaded prescription contains `Amoxicillin 500mg`.
2. Rule `RULE-MED-DENIAL` triggers an **Active Conflict**:
   - **Severity:** High
   - **Description:** *"Patient reported taking no medications, but prescription OCR extracted active medication Amoxicillin 500mg."*
   - **Status:** `Open` (Requires doctor verification).

---

### Step 6: Doctor Review & Dashboard Queue
1. Log out from `staff` and log in as `doctor` (`Doctor@1234`).
2. Navigate to **Dashboard** (`/dashboard`).
3. View the **Cases Requiring Review** queue:
   - Devendra Joshi's case is listed under `Needs Review`.
   - Discrepancy badge displays `1 open conflict`.
4. Click **Review Case** to enter the **Doctor Review** interface.

---

### Step 7: Clinician Reconciliation & Notes
1. In the **Doctor Case Review** screen, locate the **Active Discrepancies** card.
2. Click **Reconcile Discrepancy**:
   - Enter clinician reconciliation note: *"Reconciled with patient: prescription was completed last month. Currently not taking."*
   - Click **Mark Resolved**.
3. Locate the **Clinical Review Notes** section:
   - Enter clinician observations: *"Patient presents with subacute cough and evening fevers. Medication discrepancy resolved. Recommended supportive hydration and chest evaluation if symptoms persist. Non-diagnostic intake completed."*
   - Click **Save Notes** (or observe autosave notification).
   - An immutable `DOCTOR_NOTES_UPDATED` audit log is dispatched.

---

### Step 8: Encounter Finalization & Locking
1. Click **Finalize & Lock Case**.
2. A confirmation dialog appears reminding the clinician that finalized encounters cannot be edited by the patient.
3. Confirm finalization.
4. **Expected Result:**
   - Encounter status transitions to `completed` / `reviewed`.
   - Review metadata (`reviewed_at`, `reviewed_by`) is recorded.
   - UI locks into a read-only review view with banner: *"Encounter Finalized & Locked"*.

---

### Step 9: Persistence & Immutability Verification
1. **Refresh the browser window (`F5`):**
   - Doctor notes, resolved conflict status, and finalized badge remain intact.
2. **Log out and log back in as `patient` (`Patient@1234`):**
   - Attempting to submit or modify interview answers returns **`HTTP 400 Bad Request`**: *"Cannot modify responses for a finalized encounter"*.
   - Attempting back-navigation returns **`HTTP 400 Bad Request`**.
3. **Audit Log Inspection (Admin):**
   - Log in as `admin` (`Admin@1234`) and view `/audit`.
   - Verify complete chronological trace:
     - `ENCOUNTER_CREATED`
     - `RESPONSE_RECORDED`
     - `DOCUMENT_UPLOADED`
     - `CONFLICT_RESOLVED`
     - `DOCTOR_NOTES_UPDATED`
     - `ENCOUNTER_FINALIZED`

---

### Step 10: Multilingual Voice Intake (M12 & M13)
1. In the **Adaptive Interview** screen, locate the language switcher bar at the top right.
2. Select **Hindi (हिंदी)**:
   - Question text immediately switches to localized Hindi prompt: *"आज आपको सबसे ज्यादा क्या परेशानी या तकलीफ हो रही है?"*.
   - Click **Listen question**: The browser speech synthesis reads the prompt aloud in Hindi (`hi-IN`).
3. Click **Voice answer** and speak (or test via transcript simulator):
   - Utterance: `"मुझे बहुत तेज सिर दर्द हो रहा है"`.
   - The normalized parser recognizes `"Headache"` canonical entity.
4. Test Code-Mixed Dialect (**Hinglish**):
   - Speak: `"Mujhe 2 days se severe headache aur fever hai"`.
   - Heuristic dialect detection flags `detected_dialect = "hinglish"` and triggers an explicit **Visual Confirmation Card**.
   - Review the card and click **Confirm Transcript** to record response.
5. Safety Non-Silent Confirmation:
   - On the allergy question, answering via voice triggers mandatory confirmation regardless of confidence score, protecting against misheard medications or allergies.

---

### Step 11: Offline Operation & Empirical Benchmarks (M11 & M13)
1. **Offline Workstation Mode:**
   - Disconnect workstation network or verify via `GET /api/system/offline-status`.
   - Observe the top `OfflineBanner` displaying: *"Local Workstation Mode — Zero External WAN Dependencies — SQLite Persistence Active"*.
   - Complete an interview and save doctor notes entirely offline.
2. **Database Integrity Verification:**
   - Click **Verify Storage Integrity** in settings or call `GET /api/system/backup/verify`.
   - SQLite executes `PRAGMA integrity_check` returning status `ok`.
3. **Empirical Benchmarks Display:**
   - Navigate to `/benchmarks` or inspect `GET /api/system/benchmarks/summary`.
   - View transparent quantitative metrics:
     - **Printed Hospital Prescriptions:** 100.0% medication recall.
     - **Unconstrained Doctor Handwriting:** 0%–33.3% recall, with automated finalization strictly disabled and `needs_review` enforced.
     - **Speech Dialects:** 92.0% aggregate intent resolution with mandatory human confirmation for code-mixed speech.

---

## 3. Seeded Scenario Showcase
For rapid reviewer evaluation without manual intake, four realistic clinical cases are pre-seeded:

| Case | Patient Name | Condition / Scenario | Key Feature Demonstrated |
|---|---|---|---|
| **Case 1** | Aarav Sharma (Demo) | Acute severe headache, photophobia | **Active Interview:** In-progress interview with partial branch responses ready for resumption. |
| **Case 2** | Sunita Patil (Demo) | Recurrent dry cough, evening fever | **Missing Information Checklist:** Skipped allergy question renders as unknown (Missing $\neq$ Negative, 75% completeness). |
| **Case 3** | Vikram Malhotra (Demo) | Exertional chest tightness, shortness of breath | **OCR & Discrepancy Engine:** Patient denied meds, but prescription scan extracted Amoxicillin 500mg (`RULE-MED-DENIAL`). |
| **Case 4** | Meera Nair (Demo) | RLQ abdominal pain (suspected appendicitis) | **Finalized Case & Lock:** Fully reviewed by Dr. Mehta with clinical notes; encounter permanently locked against patient modification. |
