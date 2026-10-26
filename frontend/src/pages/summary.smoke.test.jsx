import { describe, it, expect, vi } from "vitest";
import React from "react";
import { renderToString } from "react-dom/server";
import { StoreProvider } from "../state/store";
import DoctorReview from "./DoctorReview";
import { Source, Tag } from "../components/ui";

describe("Frontend Milestone M5 Summary, Missing Info, and Completeness Tests", () => {
  it("verifies apiClient has all required M5 analysis endpoints", async () => {
    const { apiClient } = await import("../api/client");
    expect(typeof apiClient.getCaseSummary).toBe("function");
    expect(typeof apiClient.getMissingInformation).toBe("function");
    expect(typeof apiClient.getCaseReadiness).toBe("function");
  });

  it("renders DoctorReview screen within StoreProvider without crashing", () => {
    const html = renderToString(
      <StoreProvider>
        <DoctorReview go={() => {}} />
      </StoreProvider>
    );

    // Initial render shows spinner loading clinical case summary
    expect(html).toContain("Loading clinical case summary");
  });

  it("renders Source tags with extended M5 provenance mappings", () => {
    const patHtml = renderToString(<Source s="patient_reported" />);
    expect(patHtml).toContain("Patient-reported");
    expect(patHtml).toContain("t-patient");

    const docHtml = renderToString(<Source s="document_extracted_unverified" />);
    expect(docHtml).toContain("Document-extracted (unverified)");
    expect(docHtml).toContain("t-doc");

    const verHtml = renderToString(<Source s="doctor_verified" />);
    expect(verHtml).toContain("Doctor-verified");
    expect(verHtml).toContain("t-ver");

    const unkHtml = renderToString(<Source s="missing_unknown" />);
    expect(unkHtml).toContain("Not provided / unknown");
    expect(unkHtml).toContain("t-warn");
  });

  it("apiClient methods dispatch to correct backend endpoint paths", async () => {
    const { ApiClient } = await import("../api/client");
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: { get: () => "application/json" },
      json: async () => ({ success: true }),
    });

    const client = new ApiClient({ baseUrl: "http://127.0.0.1:8000", fetchFn: mockFetch });

    await client.getCaseSummary(101);
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/encounters/101/summary",
      expect.objectContaining({ method: "GET" })
    );

    await client.getMissingInformation(101);
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/encounters/101/missing",
      expect.objectContaining({ method: "GET" })
    );

    await client.getCaseReadiness(101);
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/encounters/101/readiness",
      expect.objectContaining({ method: "GET" })
    );
  });
});
