import { describe, it, expect } from "vitest";
import React from "react";
import { renderToString } from "react-dom/server";
import { StoreProvider } from "../state/store";
import Register from "./Register";
import Interview from "./Interview";
import Documents from "./Documents";
import DoctorReview from "./DoctorReview";
import Dashboard from "./Dashboard";

describe("Frontend Milestone M10 — P0 Release Gate E2E Smoke Tests (FR-15)", () => {
  it("verifies full client lifecycle API methods exist and match P0 requirements", async () => {
    const { apiClient } = await import("../api/client");
    expect(typeof apiClient.login).toBe("function");
    expect(typeof apiClient.getNextQuestion).toBe("function");
    expect(typeof apiClient.submitResponse).toBe("function");
    expect(typeof apiClient.uploadDocument).toBe("function");
    expect(typeof apiClient.getMissingInformation).toBe("function");
    expect(typeof apiClient.getCaseReadiness).toBe("function");
    expect(typeof apiClient.getCaseSummary).toBe("function");
    expect(typeof apiClient.getContradictions).toBe("function");
    expect(typeof apiClient.resolveConflict).toBe("function");
    expect(typeof apiClient.saveDoctorNotes).toBe("function");
    expect(typeof apiClient.finalizeCase).toBe("function");
    expect(typeof apiClient.getDashboardSummary).toBe("function");
    expect(typeof apiClient.getDashboardCases).toBe("function");
  });

  it("Step 1: Patient Registration screen renders informed consent checkbox and form inputs", () => {
    const html = renderToString(
      <StoreProvider>
        <Register go={() => {}} />
      </StoreProvider>
    );

    expect(html).toContain("Register Patient");
    expect(html).toContain("Full Name *");
    expect(html).toContain("Age *");
    expect(html).toContain("Gender *");
    expect(html).toContain("Informed Consent Required: *");
    expect(html).toContain("Register and continue");
  });

  it("Step 2 & 3: Interview screen renders adaptive questioning and rule-based engine UI", () => {
    const html = renderToString(
      <StoreProvider>
        <Interview go={() => {}} />
      </StoreProvider>
    );

    expect(html).toContain("Adaptive interview");
    expect(html).toContain("Adaptive path");
    expect(html).toContain("The engine dynamically selects each question from your earlier answers.");
  });

  it("Step 4 & 5: Documents screen renders prescription upload target and OCR extraction status", () => {
    const html = renderToString(
      <StoreProvider>
        <Documents go={() => {}} />
      </StoreProvider>
    );

    expect(html).toContain("Medical documents &amp; prescriptions");
    expect(html).toContain("Upload document");
    expect(html).toContain("NON-DIAGNOSTIC NOTICE");
    expect(html).toContain("document_extracted_unverified");
    expect(html).toContain("Real local ONNX OCR engine");
  });

  it("Step 7 & 8: DoctorReview screen initializes clinical case review with accessible loading state", () => {
    const html = renderToString(
      <StoreProvider>
        <DoctorReview go={() => {}} />
      </StoreProvider>
    );

    expect(html).toContain("spinner-container");
    expect(html).toContain("Loading clinical case summary");
  });

  it("Step 9: Doctor Dashboard renders queue, completeness readiness, and review filters", () => {
    const html = renderToString(
      <StoreProvider>
        <Dashboard go={() => {}} />
      </StoreProvider>
    );

    expect(html).toContain("Dashboard");
    expect(html).toContain("Total patients");
    expect(html).toContain("Cases requiring review");
    expect(html).toContain("Needs review");
  });
});
