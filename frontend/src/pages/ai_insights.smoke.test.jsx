import { describe, it, expect, vi } from "vitest";
import React from "react";
import fs from "node:fs";
import path from "node:path";
import { renderToString } from "react-dom/server";
import { apiClient, ApiClient } from "../api/client";
import AIClinicalInsights, { highlightSpans, summaryToText } from "../components/AIClinicalInsights";
import { StoreProvider } from "../state/store";
import { AI_TRANSLATIONS } from "../utils/i18n_ai";
import { UI_TRANSLATIONS, t as translate } from "../utils/i18n";

const okJson = (body) =>
  vi.fn().mockResolvedValue({ ok: true, status: 200, headers: { get: () => "application/json" }, json: async () => body });

const pendingItem = (id, type, content, extra = {}) => ({
  id,
  type,
  content,
  evidence: {},
  status: "pending",
  provenance: "ai_generated_unverified",
  model_name: "mock-clinical-v2",
  prompt_version: "2026.10.clinical-insights-v2",
  ...extra,
});

const PAYLOAD = {
  encounter_id: 7,
  overall_urgency: "URGENT",
  red_flags: [{ id: 1, description: "[URGENT] Critical Laboratory Value: Potassium", status: "open" }],
  document_quality: [{ id: 2, description: "scan.png: no date found on document" }],
  documented_diagnoses: [{ id: 3, raw_text: "Type 2 Diabetes", source_span: "Type 2 Diabetes", grounded: true, document_id: 1 }],
  possible_diagnoses: [
    pendingItem(10, "disease_consideration", {
      name: "Consider reduced renal function",
      likelihood: "possible",
      supporting_findings: [{ finding: "creatinine above range", evidence_ref: "lab:4", quote: "Creatinine 1.8" }],
      findings_against: [],
      suggested_questions_or_tests: ["Consider repeat creatinine"],
    }),
  ],
  extracted_entities: [],
  extraction_disagreements: [],
  abnormal_labs: [
    { id: 4, test_name: "Serum Creatinine", value: 1.8, unit: "mg/dL", ref_low: 0.7, ref_high: 1.3, flag: "high", test_date: "2026-05-01" },
    { id: 5, test_name: "ALT", value: 40, unit: "U/L", ref_low: null, ref_high: null, flag: "range_not_available" },
  ],
  computed_trends: [
    { id: 6, test_name: "creatinine", previous_value: 1.0, current_value: 1.8, unit: "mg/dL", delta: 0.8, percent_change: 80,
      direction: "rising", time_span_days: 89, rule_matched: "CREATININE_PERCENT_RISE", clinical_label: "Creatinine rise >= 50%" },
  ],
  trend_interpretations: [pendingItem(11, "trend_interpretation", { interpretation: "Creatinine rose from 1.0 to 1.8 mg/dL." })],
  risk_scores: [
    { id: 20, score_name: "qSOFA", status: "not_calculable", score_value: null, missing_inputs: ["respiratory_rate", "altered_mental_status"],
      formula_version: "Singer et al. JAMA 2016 (qSOFA)", interpretation: "Cannot calculate" },
    { id: 21, score_name: "CHA2DS2-VASc", status: "calculated", score_value: 3, missing_inputs: [],
      formula_version: "Lip et al. Chest 2010 (CHA2DS2-VASc)", interpretation: "Moderate-high stroke risk" },
  ],
  rule_conflicts: [{ id: 30, rule_id: "RULE-ALLERGY-CONFLICT", description: "Amoxicillin vs penicillin allergy" }],
  medication_reconciliation: [{ drug: "amlodipine", status: "not_reported_by_patient", details: "Documented only.", sources: ["doc:3"] }],
  treatment_references: [
    pendingItem(12, "treatment_reference", {
      topic: "Type 2 Diabetes Mellitus",
      summary: "Metformin is the usual initial oral therapy.",
      dose_quotation: "Metformin 500 mg orally once or twice daily",
      patient_conflicts: [],
      citation: { source: "Sample Treatment Workflow (SAMPLE – replace with verified source)", section: "4.1", version_date: "2026-01-15", is_sample: true },
    }),
  ],
  case_summary: pendingItem(13, "case_summary", {
    sections: [{ section: "chief_complaint", text: "Chest pain on exertion", evidence_refs: ["interview:chief_complaint"] }],
  }),
  questions_to_ask: [pendingItem(14, "questions_to_ask", { question: "Can you clarify your allergy?", reason: "conflict", evidence_refs: ["conflict:0"] })],
  document_timeline: [],
  is_case_locked: false,
  job: { id: 1, status: "completed", progress: 1, finished_at: "2026-10-31T01:00:00Z", notes: { validation: ["x"] } },
  job_status: "completed",
  job_progress: 1,
  provider_mode: "mock",
  llm_status: { active_mode: "mock", available: true, state: "available", capability: "full", summary_languages: ["en"] },
};

const render = (props) =>
  renderToString(
    <StoreProvider>
      <AIClinicalInsights encounterId={7} isFinalized={false} {...props} />
    </StoreProvider>
  );

describe("AI Clinical Insights tab", () => {
  it("exposes all AI client methods", () => {
    for (const m of ["runAIAnalysis", "getAIAnalysis", "decideAIInsight", "getAIGuidelines", "getAITrendRules", "getLLMStatus"]) {
      expect(typeof apiClient[m]).toBe("function");
    }
  });

  it("runAIAnalysis queues the job with the summary language", async () => {
    const fetchFn = okJson({ status: "queued", job_id: 3 });
    const client = new ApiClient({ baseUrl: "http://127.0.0.1:8000", fetchFn });
    const res = await client.runAIAnalysis(42, { summaryLanguage: "hi" });
    expect(res.status).toBe("queued");
    expect(fetchFn).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/analysis/42/run?summary_language=hi",
      expect.objectContaining({ method: "POST" })
    );
  });

  it("decideAIInsight sends PUT with the decision", async () => {
    const fetchFn = okJson({ id: 5, status: "accepted", provenance: "doctor_verified" });
    const client = new ApiClient({ baseUrl: "http://127.0.0.1:8000", fetchFn });
    await client.decideAIInsight(5, { decision: "edited", doctor_edits: { text: "x" } });
    expect(fetchFn).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/insights/5/decision",
      expect.objectContaining({ method: "PUT", body: JSON.stringify({ decision: "edited", doctor_edits: { text: "x" } }) })
    );
  });

  it("renders the empty and loading states", () => {
    expect(render({ encounterId: null })).toContain("No active encounter linked for AI analysis.");
    expect(render({})).toContain("Loading...");
  });

  it("shows the badge and Accept / Edit / Reject on every AI item", () => {
    const html = render({ initialData: PAYLOAD });
    const aiItems = [10, 11, 12, 13, 14];
    for (const id of aiItems) expect(html).toContain(`data-testid="ai-item-${id}"`);
    const badges = html.match(/AI-generated, unverified/g) || [];
    expect(badges.length).toBeGreaterThanOrEqual(aiItems.length + 1); // + header badge
    expect((html.match(/>Accept</g) || []).length).toBe(aiItems.length);
    expect((html.match(/>Edit</g) || []).length).toBe(aiItems.length);
    expect((html.match(/>Reject</g) || []).length).toBe(aiItems.length);
    expect(html).toContain("lab:4");
    expect(html).toContain("mock-clinical-v2");
  });

  it("renders not_calculable scores with missing inputs and calculated ones with formula", () => {
    const html = render({ initialData: PAYLOAD });
    expect(html).toContain("Not calculable");
    expect(html).toContain("Missing: respiratory_rate, altered_mental_status");
    expect(html).toContain("Formula: Lip et al. Chest 2010 (CHA2DS2-VASc)");
    expect(html).toContain("Range not printed");
  });

  it("labels the treatment panel and sample sources", () => {
    const html = render({ initialData: PAYLOAD });
    expect(html).toContain("Reference information for the prescriber. Not a prescription.");
    expect(html).toContain("SAMPLE – replace with verified source");
    expect(html).toContain("Metformin 500 mg orally once or twice daily");
  });

  it("shows the processing indicator, urgency and reconciliation", () => {
    const html = render({ initialData: PAYLOAD });
    expect(html).toContain("AI processing: offline test mode");
    expect(html).toContain("Urgent red flags: prioritise review");
    expect(html).toContain("Not reported by patient");
    expect(html).toContain("RULE-ALLERGY-CONFLICT");
    expect(html).toContain("1 AI item(s) were removed by the validator");
  });

  it("shows a clear unavailable state and locks controls on finalized cases", () => {
    const down = { ...PAYLOAD, job_status: "unavailable", llm_status: { ...PAYLOAD.llm_status, available: false, state: "llm_unavailable" } };
    const html = render({ initialData: down });
    expect(html).toContain("AI service unavailable.");
    expect(html).toContain("Last run finished without AI suggestions");
    const locked = render({ initialData: { ...PAYLOAD, is_case_locked: true } });
    expect((locked.match(/disabled=""/g) || []).length).toBeGreaterThanOrEqual(15);
  });

  it("helpers: highlights cited spans and serializes the summary", () => {
    const html = renderToString(<pre>{highlightSpans("Serum Creatinine 1.8 mg/dL", ["creatinine 1.8"])}</pre>);
    expect(html).toContain("<mark");
    expect(html).toContain(">Creatinine 1.8</mark>");
    expect(summaryToText(PAYLOAD.case_summary.content, (k) => translate(k, "en"))).toBe("CHIEF COMPLAINT:\nChest pain on exertion");
  });

  it("has every AI string in English, Hindi and Marathi", () => {
    const en = Object.keys(AI_TRANSLATIONS.en).sort();
    expect(Object.keys(AI_TRANSLATIONS.hi).sort()).toEqual(en);
    expect(Object.keys(AI_TRANSLATIONS.mr).sort()).toEqual(en);
    for (const lang of ["hi", "mr"]) {
      for (const k of en) expect(AI_TRANSLATIONS[lang][k].trim().length).toBeGreaterThan(0);
    }
  });

  it("every t() key used by the AI tab exists in all three languages", () => {
    const src = fs.readFileSync(path.resolve(__dirname, "../components/AIClinicalInsights.jsx"), "utf8");
    const keys = new Set([...src.matchAll(/\bt\("([A-Za-z_]+)"\)/g)].map((m) => m[1]));
    // dynamic keys built from template strings
    for (const s of ["chief_complaint", "hpi", "pmh_psh", "drug_allergy", "family", "personal", "ros", "prior_investigations"]) keys.add(`summary_${s}`);
    for (const s of ["more_likely", "possible", "less_likely"]) keys.add(`likelihood_${s}`);
    for (const s of ["added", "stopped", "changed_dose", "duplicate_brand_generic", "not_reported_by_patient", "patient_reported_only"]) keys.add(`recon_${s}`);
    expect(keys.size).toBeGreaterThan(40);
    for (const lang of ["en", "hi", "mr"]) {
      const missing = [...keys].filter((k) => !UI_TRANSLATIONS[lang][k]);
      expect(missing, `${lang} missing`).toEqual([]);
    }
  });
});
