import { describe, it, expect, vi } from "vitest";
import React from "react";
import fs from "node:fs";
import path from "node:path";
import { renderToString } from "react-dom/server";
import { ApiClient } from "../api/client";
import { StoreProvider } from "../state/store";
import AIConclusionsPanel, { ConclusionCaseCard } from "../components/AIConclusionsPanel";
import AIClinicalInsights from "../components/AIClinicalInsights";
import PatientPortal from "./PatientPortal";
import { VISIT_TRANSLATIONS } from "../utils/i18n_visit";
import { UI_TRANSLATIONS, t as translate } from "../utils/i18n";

const en = (k) => translate(k, "en");

const CONCLUSION = {
  id: 9,
  type: "analyzed_conclusion",
  status: "pending",
  provenance: "ai_generated_unverified",
  model_name: "mock-clinical-v2",
  prompt_version: "v2",
  content: {
    conclusion: "The patient reports: chest pain on walking. Rule-based urgency is EMERGENCY.",
    possible_considerations: [{ name: "Consider ischaemic chest pain", likelihood: "possible" }],
    key_findings: [{ finding: "Reported finding", evidence_ref: "interview:chief_complaint", quote: "chest pain" }],
    recommended_next_steps: ["Examine the patient"],
    information_gaps: ["Not answered: has allergies"],
    urgency: "EMERGENCY",
  },
};

const ITEMS = [
  {
    encounter_id: 5, patient_id: 3, patient_name: "Rajesh Verma", reason_for_visit: "chest pain on walking",
    analysis_state: "ready", last_trigger: "interview_answer", analyzed_at: "2026-10-31T02:00:00Z",
    urgency: "EMERGENCY", red_flags: ["Possible ACS"], conclusion: CONCLUSION, overview: {},
  },
  {
    encounter_id: 6, patient_id: 4, patient_name: "Asha Kale", reason_for_visit: "rash",
    analysis_state: "ai_unavailable", last_trigger: "document_processed", analyzed_at: "2026-10-31T02:00:00Z",
    urgency: "ROUTINE", red_flags: [], conclusion: null,
    overview: { red_flags: [], abnormal_labs: ["Haemoglobin 9.1 g/dL (low)"] },
  },
  {
    encounter_id: 7, patient_id: 8, patient_name: "New Patient", reason_for_visit: null,
    analysis_state: "analyzing", last_trigger: null, analyzed_at: null, urgency: "ROUTINE", conclusion: null, overview: {},
  },
];

describe("Automatic analysis on the doctor dashboard", () => {
  it("client fetches the doctor-only overview feed", async () => {
    const fetchFn = vi.fn().mockResolvedValue({
      ok: true, status: 200, headers: { get: () => "application/json" }, json: async () => ({ items: [] }),
    });
    const client = new ApiClient({ baseUrl: "http://127.0.0.1:8000", fetchFn });
    await client.getAIOverview(10);
    expect(fetchFn).toHaveBeenCalledWith("http://127.0.0.1:8000/api/analysis/overview?limit=10", expect.anything());
  });

  it("shows each case's conclusion, urgency, state and an unverified badge", () => {
    const html = renderToString(
      <StoreProvider>
        <AIConclusionsPanel go={() => {}} initialData={{ items: ITEMS }} />
      </StoreProvider>
    );
    expect(html).toContain("AI Analyzed Conclusions");
    expect(html).toContain("Rule-based urgency is EMERGENCY");
    expect(html).toContain("Consider ischaemic chest pain");
    expect(html).toContain("AI-generated, unverified");
    expect(html).toContain("Analyzed");
    expect(html).toContain("Analyzing…");
    expect(html).toContain("AI unavailable: rule-based overview only");
    expect(html).toContain("Haemoglobin 9.1 g/dL (low)");
    expect(html).toContain("patient answer");
    expect((html.match(/Open AI insights/g) || []).length).toBe(3);
  });

  it("shows a doctor's edited conclusion instead of the AI text", () => {
    const edited = { ...ITEMS[0], conclusion: { ...CONCLUSION, status: "edited", doctor_edits: { text: "My own conclusion" } } };
    const html = renderToString(<ConclusionCaseCard item={edited} t={en} onOpen={() => {}} />);
    expect(html).toContain("My own conclusion");
    expect(html).not.toContain("Rule-based urgency is EMERGENCY");
    expect(html).toContain("Edited by doctor");
  });

  it("AI tab puts the Analyzed Conclusion first with Accept / Edit / Reject", () => {
    const data = {
      encounter_id: 5, overall_urgency: "EMERGENCY", red_flags: [], document_quality: [], documented_diagnoses: [],
      possible_diagnoses: [], extracted_entities: [], extraction_disagreements: [], abnormal_labs: [], computed_trends: [],
      trend_interpretations: [], risk_scores: [], rule_conflicts: [], medication_reconciliation: [], treatment_references: [],
      case_summary: null, questions_to_ask: [], document_timeline: [], is_case_locked: false, job_status: "completed",
      analysis_state: "ready", analyzed_conclusion: CONCLUSION,
      llm_status: { active_mode: "mock", available: true, capability: "full", summary_languages: ["en"] },
    };
    const html = renderToString(
      <StoreProvider>
        <AIClinicalInsights encounterId={5} isFinalized={false} initialData={data} />
      </StoreProvider>
    );
    expect(html.indexOf("Analyzed Conclusion")).toBeLessThan(html.indexOf("Rule-based alerts (not AI)"));
    expect(html.indexOf("Rule-based alerts (not AI)")).toBeGreaterThan(0);
    expect(html).toContain('data-testid="ai-item-9"');
    expect(html).toContain("Re-run analysis");
    expect(html).toContain("The analysis runs automatically");
    expect(html).toContain("Not answered: has allergies");
  });

  it("dashboard renders the panel only for doctors and admins", () => {
    const src = fs.readFileSync(path.resolve(__dirname, "./Dashboard.jsx"), "utf8");
    expect(src).toMatch(/role === "doctor" \|\| role === "admin"/);
    expect(src).toContain("{showAIConclusions && <AIConclusionsPanel");
  });
});

describe("Reason for visit in the patient portal", () => {
  it("renders the free-text reason box", () => {
    const html = renderToString(
      <StoreProvider>
        <PatientPortal go={() => {}} user={{ username: "patient", role: "patient" }} />
      </StoreProvider>
    );
    expect(html).toContain("Why are you visiting today?");
    expect(html).toContain("<textarea");
    expect(html).toContain("Save and continue to my questions");
  });

  it("has every visit string in English, Hindi and Marathi", () => {
    const keys = Object.keys(VISIT_TRANSLATIONS.en).sort();
    expect(Object.keys(VISIT_TRANSLATIONS.hi).sort()).toEqual(keys);
    expect(Object.keys(VISIT_TRANSLATIONS.mr).sort()).toEqual(keys);
  });

  it("every t() key used by the dashboard panel exists in all three languages", () => {
    const src = fs.readFileSync(path.resolve(__dirname, "../components/AIConclusionsPanel.jsx"), "utf8");
    const keys = new Set([...src.matchAll(/\bt\("([A-Za-z_]+)"\)/g)].map((m) => m[1]));
    for (const s of ["analyzing", "ready", "ai_unavailable", "failed", "not_analyzed"]) keys.add(`state_${s}`);
    for (const s of ["interview_answer", "interview_completed", "document_processed", "reason_for_visit", "manual", "backfill"]) keys.add(`trigger_${s}`);
    for (const lang of ["en", "hi", "mr"]) {
      expect([...keys].filter((k) => !UI_TRANSLATIONS[lang][k]), lang).toEqual([]);
    }
  });
});
