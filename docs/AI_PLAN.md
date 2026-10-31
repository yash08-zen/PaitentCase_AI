# AI Clinical Insights Layer — Implementation Plan (SIH26047)

## Core Design Principle
> **The LLM proposes. Code verifies. The doctor decides.**
- Deterministic engines compute lab flags, trends, scores, urgency, interactions.
- Grounding validator verifies every claim against OCR spans / interview answers.
- Provenance `ai_generated_unverified` with doctor-only visibility until explicit `accept|edit|reject`.
- Strict prompt-injection defense: untrusted text isolated in user payload, never system instructions.
- "Missing ≠ Negative" preserved.

## Step-by-Step Implementation Roadmap

### Phase 1: LLM Service Layer & Foundations
- Create `backend/app/services/llm/`
  - `interface.py`: `generate(task, system_prompt, user_content, json_schema, *, images=None) -> validated dict`
  - `hosted_provider.py`: Anthropic Claude SDK with tool/schema-enforced JSON, timeouts, retries, exponential backoff.
  - `local_provider.py`: Ollama OpenAI-compatible client (`http://127.0.0.1:11434/v1`), `temperature=0`, `num_ctx<=4096`.
  - `mock_provider.py`: Deterministic test fixtures for offline reproducible testing.
  - `scrubber.py`: Patient de-identification scrubber (regex + entity masking for names, phones, ABHA/Aadhaar, IDs) with local re-attachment map.
  - `manager.py`: Provider selector (`LLM_PROVIDER`), fallback handling, structured call logging (latency, token usage, model, prompt_version, encounter_id — no raw clinical text or keys).
- Add database models & migrations:
  - `AI_INSIGHTS`, `LAB_RESULTS`, `DOCUMENT_ENTITIES`, `TREND_FLAGS`, `RISK_SCORES`, `GUIDELINE_PASSAGES`, `LLM_JOBS`.
  - Extend `CONFLICTS` table with `RULE-INTERACTION`, `RULE-LAB-ABNORMAL`, `RULE-DIAGNOSIS-DENIAL`, `RULE-WRONG-PATIENT`.
- Unit tests for scrubber, provider interface, and fallback degradation.

### Phase 2: Document Intelligence & Deterministic Engines
- Document classification & structured extraction (prescriptions, lab reports, discharge summaries, imaging reports).
- Grounding validator: verified normalized string span matching against OCR text.
- `backend/app/engines/`:
  - `lab_flagging.py`: Lab range comparison, synonym normalization (Hb/Haemoglobin), missing range handling.
  - `trend_calculator.py`: Test changes across dates, thresholds loaded from `config/trend_rules.yaml`.
  - `risk_scores.py`: qSOFA, CURB-65, NEWS2, CHA₂DS₂-VASc with `not_calculable` handling on missing inputs.
  - `red_flags.py`: Deterministic red-flag / priority urgency alerts.
  - `interactions.py`: Local drug-drug, drug-allergy interaction tables & discrepancy checks.
- Document chronological timeline generator.

### Phase 3: The 4 Clinical Features (LLM + Code Verification)
- 1. **Disease Considerations**: Top considerations (max 5) with qualitative likelihood, supporting evidence, counter-evidence, confirmatory questions. Segregated from documented diagnoses.
- 2. **Treatment & Dose Reference**: Guideline library with SQLite FTS5 (`GUIDELINE_PASSAGES`). Dose quotation strictly cited from retrieved passages; allergen & interaction cross-checks.
- 3. **Risk / Urgency Scores**: Display code-computed scores, inputs, missing inputs, and one-line plain language explanation.
- 4. **Clinical Trend Interpretation**: Rule-based trend interpretation sentences using only computed numbers. Validator rejects any unverified numbers.

### Phase 4: Summaries, Follow-ups, Vision Path & Quality Checks
- AI Case Summary in standard clinical structure with per-line source references (trilingual en/hi/mr in hosted mode).
- Doctor's "Questions to Ask" contradictory/gap resolution list.
- Feature-flagged AI follow-up questions (`AI_FOLLOWUPS_ENABLED`) with safety gating against leading/diagnostic queries.
- Vision path for low-confidence handwritten documents (< 0.70 confidence).
- Document quality checks: blurry/cropped detection, wrong patient detection (`RULE-WRONG-PATIENT`), medication reconciliation across records.

### Phase 5: Doctor-Gated Review API & Frontend AI Insights Tab
- Backend API endpoints (Doctor-only RBAC):
  - `POST /api/analysis/{encounter_id}/run`: Launch async background LLM job.
  - `GET /api/analysis/{encounter_id}`: Comprehensive insights payload.
  - `PUT /api/insights/{id}/decision`: Accept, edit, reject with audit trail.
  - `GET /api/system/llm-status`: Provider status & active mode.
- Frontend UI:
  - "AI Insights" tab on Doctor Case page.
  - Side-by-side original scan and extracted spans.
  - Urgency banner, documented vs possible diagnoses, abnormal labs, trend chart/table, risk scores with not_calculable states.
  - AI-generated unverified badges and Accept / Edit / Reject buttons.
  - Full Trilingual UI localization (en, hi, mr) in `i18n.js`.

### Phase 6: Eval Harness, Red-Team Security Tests, Benchmarking & Docs
- Evaluation harness in `backend/eval/` with 25-30 synthetic test cases.
- Measure precision, recall, hallucination/grounding-failure rate, score accuracy, vision vs RapidOCR handwriting recall.
- Red-team prompt-injection, definitive diagnosis bait, invented dose bait test cases.
- Output metrics to `docs/AI_EVAL_REPORT.md`.
- Update README.md, LIMITATIONS.md, DECISIONS.md, API_MAP.md, RUNBOOK.md, `.env.example`.


---

## Status after the gap audit (2026-10-31)

An audit of the first implementation against the task found these gaps; all were fixed on branch `feature/ai-clinical-insights` (see `docs/DECISIONS.md` D-052 to D-066):

| Gap found | Fix |
|---|---|
| `AI_EVAL_REPORT.md` contained hard-coded numbers (vision recall, latency, tokens) and red-team cases counted as passed without checks | Harness rewritten; every case runs through the real pipeline and the report is generated from measured values only |
| Analysis ran synchronously inside the request | Background job (202 + polling, 409 on concurrent runs), idempotent re-runs |
| No output validator: considerations stored without evidence checks; mock evidence pointed at data not in the case | Evidence catalogue + `output_validator.py` (resolvable refs, quotes, traceable numbers, definitive/injected wording) |
| Hosted provider used raw HTTP with forced `tool_choice` (rejected by Sonnet 5.5) | Official `anthropic` SDK with structured outputs |
| Vision path passed the wrong image keys and always failed; results were marked grounded | Fixed keys; results stored unverified with *read from handwriting, verify* |
| NEWS2 defaulted missing oxygen/consciousness to normal; CHA₂DS₂-VASc treated "not mentioned" as "no" | Missing inputs stay missing → `not_calculable` |
| Trend rules matched with unknown dates; series not date-sorted | Windowed rules need a known span; date-sorted series incl. earlier encounters |
| No FTS5, no ingestion script | FTS5 index, JSON sample library, `scripts/ingest_guidelines.py` |
| No medication reconciliation, regex cross-check, `RULE-LAB-ABNORMAL`, quality checks | Implemented as deterministic code |
| No audit event per external call, no token logging | Per-call metadata on the job + `LLM_EXTERNAL_CALL` audit events |
| AI follow-ups had no safety filter and leaked into other encounters | Safety filter + bank mapping + per-encounter scoping |
| Frontend tab read fields the API never returned | Tab rebuilt against the real payload; en/hi/mr strings with a parity test |
| Duplicate Alembic head | Chain repaired; new migration `8c9d0e1f2a3b` |
| README / LIMITATIONS / DECISIONS / API_MAP / RUNBOOK / `.env.example` not updated | Updated |

Still open: hosted-model and vision-path accuracy are not measured (needs an API key and synthetic data); the 0.70 OCR confidence gate misses confident-but-wrong handwriting (measured, documented in LIMITATIONS).
