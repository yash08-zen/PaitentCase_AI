# PatientCase AI — System Limitations & Clinical Boundary Statement

## 1. Non-Diagnostic Clinical Boundary Statement
**IMPORTANT CLINICAL NOTICE:**
PatientCase AI is strictly an **information intake, document structuring, and clinical handoff assistant**.
- The system **does NOT diagnose diseases, disorders, or medical conditions**.
- The system **does NOT recommend treatments, drugs, or clinical interventions**.
- The system **does NOT calculate clinical triage urgency, emergency severity scores, or disease mortality risks**.
- The completeness score is a measure of **data intake completeness only** (i.e. whether required intake fields have been provided) and is **never a measure of diagnostic accuracy or patient health status**.
- All machine-generated document extractions are tagged with the provenance label `document_extracted_unverified` and must be reviewed, reconciled, and approved by a licensed medical practitioner before any clinical reliance.

---

## 2. Document Processing & OCR Limitations
- **Supported Document Types:**
  - Printed prescription slips and pharmacy labels (standard Latin text, English/medical terminology).
  - Diagnostic lab reports (standard key-value formatting).
  - Formats: JPEG, PNG, WebP, TIFF, and PDF (scanned/vector) up to 20 MB.
- **Recognized Limitations & Empirical Benchmarks (M13):**
  - **Severe Cursive Handwriting & Degradation:** Measured on the empirical benchmark dataset (`tests/eval_data/handwritten/`), printed hospital prescriptions achieve **100.0% medication recall**, whereas unconstrained doctor cursive achieves only **33.3%** on slanted cursive and **0.0%** on degraded cursive scrawl.
  - **Mandatory Clinician Transcription Safeguard:** Automated finalization is strictly disabled for unconstrained doctor handwriting; documents with mean confidence < 0.70 or unparseable cursive scrawl automatically default to status `needs_review` requiring clinician verification.
  - **Damaged / Folded Physical Paper:** Severe creases, coffee stains, or low-light shadows can reduce text recognition accuracy.
  - **Non-Latin Scripts in Prescriptions:** Current OCR models are optimized for Latin script medical terms and brand names commonly used in Indian prescription practice. Vernacular handwritten drug names may have lower confidence.

---

## 3. Medication & Discrepancy Engine Scope
- **Rule Scope:**
  - The discrepancy engine executes 6 deterministic rules (`RULE-MED-DENIAL`, `RULE-MED-NAME-MISMATCH`, `RULE-MED-DOSAGE-MISMATCH`, `RULE-ALLERGY-CONFLICT`, `RULE-DUPLICATE-THERAPY`, `RULE-UNVERIFIED-EXTRACTION`).
  - It detects explicit contradictions between patient-reported statements and uploaded prescription text.
- **Limitations:**
  - It does not perform comprehensive pharmacokinetics, CYP450 metabolic pathway cross-reactions, or pediatric weight-based micro-dosing checks.
  - Clinician judgment is always required to contextualize whether an apparent mismatch represents discontinued therapy, a dosage titration, or an erroneous patient recall.

---

## 4. Offline Capabilities & Networking Scope (FR-13 / Milestone M11)
- **Fully Offline Capable & Tested:**
  - **Local FastAPI Backend Server:** Runs on loopback (`localhost:8000`) with zero outbound WAN socket connections.
  - **Local Vite / React Single-Page Application:** All JS, CSS, and SVG iconography assets are self-contained and bundled locally; zero external CDNs, fonts, or tracking scripts.
  - **Local SQLite Database (`aiosqlite`):** Zero external database server dependencies. Data remains 100% persisted across workstation shutdowns and app restarts.
  - **Local Neural OCR Inference:** RapidOCR executes on-device via ONNX Runtime using local weights; zero prescription scans or patient records leave the clinic machine.
  - **Air-Gapped Operation:** Verified via automated tests (`test_air_gapped_network_isolation`) ensuring zero external network calls are made during intake, interview, summary, and doctor review.
- **Explicit Exclusions & Safeguards:**
  - **Multi-Device Cloud Synchronization:** The system operates strictly as a single-workstation local clinic system. Peer-to-peer or cloud sync is intentionally not implemented. Any attempt to invoke remote sync (`POST /api/system/sync`) returns `HTTP 501 Not Implemented` with an explanatory payload to actively prevent silent data overwrites or merge discrepancies.
  - **Cloud Voice / Remote Telemedicine:** Remote speech synthesis/recognition services are unavailable offline; the UI explicitly falls back to keyboard/touch input with all data stored locally.

---

## 5. Voice & Multilingual Scope (FR-12 / Milestone M12)
- **Verified Multilingual Capabilities:**
  - **Language Selection & Persistence:** Preferred languages (`English`, `Hindi / हिंदी`, `Marathi / मराठी`) are stored on patient profile and encounter records, maintaining the selected language across all adaptive interview turns.
  - **Localized Intake Question Bank:** Structured question text, help hints, choices, and audio prompts provided in English, Hindi, and Marathi.
  - **Spoken Question Audio (TTS):** Spoken prompt audio using browser speech synthesis (`en-IN`, `hi-IN`, `mr-IN`) with instant text fallback.
  - **Spoken Utterance Mapping:** Normalized recognition for English, Hindi, and Marathi symptom names, numbers (1 to 10), duration phrases, and affirmative/negative intent.
  - **Mandatory Human Confirmation Safeguard:**
    - Any transcript with speech confidence below 85% requires explicit patient confirmation (`requires_confirmation = True`).
    - Critical safety fields (allergies and medications) **always require explicit human confirmation** regardless of confidence score; transcripts are never silently committed.
  - **Persistent Touch/Keyboard Fallback:** Voice input never blocks touch selection or keyboard typing; progress is 100% preserved if speech recognition is unavailable or denied.
- **Recognized Speech Limitations & Dialect Scope (M13):**
  - **Code-Mixed Dialects (Hinglish & Marathish):** Evaluated across 25 representative utterances. Standard dialects achieve 80–100% intent resolution. Code-mixed utterances achieve 80–100% resolution with mandatory confirmation enforced (100% for Hinglish, 80% for Marathish). Unverified commitments are strictly prevented.
  - **Extreme Ambient Noise:** Heavy background noise (e.g., loud hospital waiting halls) can degrade microphone signal-to-noise ratio; the system flags low confidence and prompts for keyboard/touch entry.
  - **Unregistered Vernacular Dialects:** Multilingual mapping is calibrated and tested against Standard Indian English, Modern Standard Hindi, and Standard Marathi, with heuristic code-mixed detection. Non-standard regional colloquialisms require manual keyboard entry or confirmation.
