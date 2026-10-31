# PatientCase AI — Project Status Report

**Project:** PatientCase AI (SIH26047)
**Feature:** AI Clinical Insights Layer
**Date:** 31 October 2026
**Branch:** `feature/ai-clinical-insights`
**Core design principle:** *The LLM proposes. Code verifies. The doctor decides.*

**Test suites (run on 31 Oct 2026):**
- Backend: **189 / 189 pytest passing** (98 original + 91 AI-layer, auto-analysis and questionnaire)
- Frontend: **95 / 95 vitest passing** (75 original + 20 AI tab, dashboard panel, reason card), production build OK
- Fresh `alembic upgrade head` / `downgrade -1` / re-upgrade verified on an empty database

---

## 1. What changed since the previous status report

The previous version of this file reported the AI layer as complete. An audit against the task (`CLAUDE_CODE_PROMPT_AI_Insights.md`) found that several items were missing or did not work, and that `docs/AI_EVAL_REPORT.md` contained numbers that were typed in rather than measured. The fixes are listed in `docs/AI_PLAN.md` ("Status after the gap audit") and the decisions in `docs/DECISIONS.md` (D-052 to D-066). Main points:

- **Eval report:** the old report's vision recall (94%), latency (38.5 ms) and token figures (1,620) were hard-coded, and red-team cases were counted as passed without any check. The harness now runs every case through the real pipeline and writes the report from measured values only.
- **Vision path:** never worked (wrong image keys); now fixed, and results are stored unverified with *read from handwriting, verify*.
- **Hosted provider:** now uses the official `anthropic` SDK with structured outputs (the old forced `tool_choice` request is rejected by Sonnet 5.5).
- **Safety:** an output validator now drops AI claims without resolvable evidence, definitive or instruction-like wording, and untraceable numbers. Missing score inputs are no longer silently defaulted to normal.
- **Background jobs, FTS5 guideline retrieval, medication reconciliation, regex cross-check, `RULE-LAB-ABNORMAL`, document quality checks, per-call audit and token logging, follow-up safety filter** were added.
- **Frontend AI tab** was rebuilt: the old one read fields the API never returned, so most panels were empty.
- **Docs** (README, LIMITATIONS, DECISIONS, API_MAP, RUNBOOK, `.env.example`) were updated; a duplicate Alembic head was fixed.

---

## 2. Definition of done (from the task, section 8)

| Requirement | Status |
|---|---|
| Existing 173 tests plus new tests all pass | Done: 284 / 284 |
| Doctor runs AI analysis on a case with a lab report and a prescription and sees entities with source highlights, abnormal labs, trends with rule-based interpretation, scores or `not_calculable`, urgency alerts, considerations with evidence, cited treatment reference, AI summary, and Accept / Edit / Reject that write audit events | Done; covered end-to-end by `test_full_case_with_lab_report_and_prescription` and the decision/audit tests. UI not yet checked by hand in a browser against a live backend. |
| Patients and staff never see AI insights (403 + test) | Done, tested on every AI endpoint |
| `LLM_PROVIDER=local` or LLM unreachable → app works and tab shows unavailable / reduced state | Done (`test_llm_down_degrades_gracefully`, frontend unavailable-state test). Not tested against a real Ollama install. |
| `docs/AI_EVAL_REPORT.md` has real measured results | Done for the mock provider and RapidOCR. Hosted-model and vision-path results not measured (no API key). |
| README, LIMITATIONS, DECISIONS, API_MAP, RUNBOOK updated and consistent | Done |

---

## 3. Measured results (mock provider; see `docs/AI_EVAL_REPORT.md`)

| Metric | Result |
|---|---|
| Risk scores vs hand-calculated cases | 16 / 16 |
| Fabricated entities caught by grounding | 15 / 15; 0 reached the engines |
| Red-team checks | 12 / 12 |
| Trend calculator (multi-document) | 3 / 3 |
| Conflict-rule detection recall | 12 / 12, no unexpected firings |
| Lab extraction (offline stand-in) | precision 100%, recall 80% (misses tests outside the synonym table) |
| RapidOCR medication recall | printed 75%, handwritten 0% |
| Vision path recall | **not measured** (needs hosted key) |

The mock provider is a regex/dictionary stand-in, not an LLM. These numbers do not describe real model accuracy.

---

## 3b. Added on 31 Oct 2026 (second request)

- **Automatic analysis:** runs on patient answers (debounced), interview completion and processed documents; no button needed. Produces a validated **Analyzed Conclusion** and a rule-based overview.
- **Doctor dashboard:** "AI Analyzed Conclusions" panel (doctor/admin only), sorted by urgency, live while analyses run, with a link into each case's AI tab.
- **Complaint-driven questionnaire:** free-text reason for visit (Patient Portal card, interview, self-registration) -> generic questions + symptom modules chosen from the patient's words in English/Hindi/Marathi. Fixed disease-choice list removed.

## 4. Remaining work

| Item | Priority | Notes |
|---|---|---|
| Run the eval with `--provider hosted` on synthetic data | High | Measures real extraction quality, vision recall on the handwriting images, latency and tokens. Needs an `ANTHROPIC_API_KEY`. |
| Handwriting detection beyond the confidence gate | High | Measured: two handwritten images scored OCR confidence ≥ 0.70 with 0% medication recall, so they are not routed to vision or review. Needs a better trigger (e.g. a handwriting classifier or "prescription with no recognised drug" rule). |
| Replace sample guideline passages with verified sources | High before any real use | `scripts/ingest_guidelines.py --replace` |
| Clinician review of trend rules, critical thresholds, red-flag rules, interaction table | High before any real use | Files listed in LIMITATIONS §6 |
| Test `local` mode on the target machine (Ollama, 3B model, 8 GB RAM / RTX 2050) | Medium | Not run during this work |
| Manual browser walkthrough of the AI tab against a live backend | Medium | Covered by render tests only |
| Expand drug/brand dictionary and lab synonym table | Low | Offline extraction misses tests like TSH, troponin, eGFR |

---

## 5. Architectural guarantees (as implemented and tested)

1. No clinical number comes from an LLM: lab flags, trends, scores and urgency are code; trend sentences are rejected if they contain a number code did not compute.
2. AI output is stored as `ai_generated_unverified`, visible to doctors/admins only, and becomes `doctor_verified` only on Accept or Edit; finalized cases lock re-runs and decisions.
3. Document and patient text never enters a system prompt; it is passed as delimited untrusted data.
4. Hosted mode de-identifies text before sending and audits every external call; local and mock modes make no external calls.
5. Missing information is never treated as negative.
