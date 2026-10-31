# PatientCase AI — System Limitations & Clinical Boundary Statement

## 1. Clinical Boundary Statement
**IMPORTANT CLINICAL NOTICE:**
PatientCase AI provides source-cited, AI-generated suggestions for clinician review. It makes no autonomous decisions. All AI output is unverified until a licensed clinician accepts it.
- AI suggestions (possible considerations, treatment reference, case summary, trend sentences, questions to ask) are visible to doctors only, carry the provenance `ai_generated_unverified`, and become `doctor_verified` only after the doctor clicks Accept or Edit.
- Possible considerations are not diagnoses. The validator rejects definitive wording ("definitely", "the diagnosis is", …).
- Risk and urgency scores (qSOFA, CURB-65, NEWS2, CHA₂DS₂-VASc) and red-flag alerts are computed by code. They are decision support for a clinician, not triage decisions, and their thresholds have not been clinically validated for this deployment.
- The completeness score measures **intake data completeness only** and is never a measure of diagnostic accuracy or patient health status.
- All machine extractions carry provenance (`document_extracted_unverified`, `regex_extracted_unverified`, `vision_fallback`) and must be reviewed by a licensed practitioner before clinical reliance.
- **Regulatory status:** software that suggests diagnoses or treatment may be regulated as a medical device (Software as a Medical Device) in India under the Medical Devices Rules, 2017 administered by CDSCO. PatientCase AI has not been assessed or registered. It is a **research prototype for synthetic data only** and must not be used for real patients.

---

## 2. Document Processing & OCR Limitations
- **Supported Document Types:**
  - Printed prescription slips and pharmacy labels (standard Latin text, English/medical terminology).
  - Diagnostic lab reports (standard key-value formatting).
  - Formats: JPEG, PNG, WebP, TIFF, and PDF (scanned/vector) up to 20 MB.
- **Recognized Limitations & Empirical Benchmarks (M13):**
  - **Severe Cursive Handwriting & Degradation:** On the benchmark images (`backend/tests/eval_data/handwritten/`), the AI eval harness measured RapidOCR + regex medication recall of 100% on the clean printed prescription, 50% on the bilingual printed one, and **0%** on all three handwritten images (see `docs/AI_EVAL_REPORT.md`). An older benchmark script reported 33.3% on slanted cursive using a different matcher.
  - **Confidence gate gap (measured):** two of the three handwritten images scored OCR confidence ≥ 0.70 (0.90 and 0.95) while losing every medication. The 0.70 gate therefore does **not** reliably detect handwriting: such pages are neither sent to the vision path nor flagged `needs_review` by the gate. Extracted medications still pass grounding and appear as unverified, but clinicians must check handwritten scans themselves.
  - **Mandatory Clinician Transcription Safeguard:** documents with mean confidence < 0.70 or no readable text default to `needs_review`. In hosted mode they are additionally read by the vision model and flagged *read from handwriting, verify*.
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
- **LLM provider modes:** the statements below hold for `LLM_PROVIDER=local` and `LLM_PROVIDER=mock`. With `LLM_PROVIDER=hosted`, the AI layer sends **de-identified clinical text** to the configured provider (Anthropic API), and for low-confidence images it sends the **page image itself**, which cannot be de-identified. See §6.
- **Fully Offline Capable & Tested (local / mock modes):**
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

---

## 6. AI Clinical Insights Layer Limitations

- **Hosted-mode privacy.** De-identification is regex-based (names given to it, phone, Aadhaar, ABHA, email, MRN/UHID, PIN, address lines). It can miss identifiers written in unusual formats or embedded in free text (for example a relative's name). Page images sent for handwriting reading are not de-identified at all. Hosted mode is therefore for **synthetic data only**; the server prints a startup warning and the UI shows a consent line. Every external call writes an `LLM_EXTERNAL_CALL` audit event (no clinical text is logged).
- **Small local models.** `local` mode targets a ~3B instruct model on 8 GB RAM / 4 GB VRAM with `num_ctx ≤ 4096`, one job at a time. Expect weaker extraction, more items dropped by the validator, and possible JSON failures (these surface as validation notes, not crashes). Long documents may exceed the context window. Hindi/Marathi summaries are disabled in local mode (English only).
- **Vision path unavailable offline.** Handwriting reading needs the hosted provider. In local mode low-confidence pages go straight to `needs_review`. Vision recall has **not been measured** yet (no API key was available during evaluation).
- **Offline evaluation is not a model evaluation.** The automated tests and the default eval run use the `mock` provider, a deterministic regex/dictionary stand-in. Its scores say nothing about how a hosted or local LLM performs. The eval dataset and the mock were written by the same team, so offline scores are an upper bound for the stand-in.
- **Sample guideline content.** All passages in `backend/config/guidelines_sample.json` are labelled `SAMPLE – replace with verified source`. They are placeholders, are not taken from any real guideline, and must be replaced with verified sources (`scripts/ingest_guidelines.py`) before any real use. The treatment panel shows only what retrieval returns; if nothing relevant is retrieved it says so.
- **Thresholds need clinician review.** Trend rules (`backend/config/trend_rules.yaml`), critical-value thresholds (`app/engines/lab_flagging.py`), red-flag rules, the interaction table and the brand→generic map are small, hand-written samples. They are marked as requiring clinician review and are not exhaustive (e.g. no renal dose adjustment, no pregnancy or paediatric checks).
- **Scores only from documented inputs.** The intake question bank does not collect vitals or mental status, so most risk scores will be `not_calculable` unless the documents print the inputs. This is intended (missing is never treated as normal).
- **Extraction coverage.** The offline path only recognises lab tests in the local synonym table and drugs in the regex dictionary; others are missed (see the eval report). Unit normalization covers a few common conversions; unknown units are left as printed and flagged.
- **Validator limits.** Number traceability checks that each number appears somewhere in the case evidence, not that it is used in the right context. Injection-marker and definitive-phrase lists are pattern-based and can be evaded by paraphrase; the doctor-gating step remains the final safeguard.
- **AI follow-up questions** are off by default (`AI_FOLLOWUPS_ENABLED=false`). When on, a question that passes the safety filter is shown to the patient without a clinician seeing it first.
