import { describe, it, expect, vi } from "vitest";
import React from "react";
import { renderToString } from "react-dom/server";
import { apiClient, ApiClient } from "../api/client";
import AIClinicalInsights from "../components/AIClinicalInsights";
import { StoreProvider } from "../state/store";

describe("Frontend AI Clinical Insights Layer Smoke Tests", () => {
  it("verifies apiClient exposes all AI Clinical Insights methods", () => {
    expect(typeof apiClient.runAIAnalysis).toBe("function");
    expect(typeof apiClient.getAIAnalysis).toBe("function");
    expect(typeof apiClient.decideAIInsight).toBe("function");
    expect(typeof apiClient.getAIGuidelines).toBe("function");
    expect(typeof apiClient.getAITrendRules).toBe("function");
    expect(typeof apiClient.getLLMStatus).toBe("function");
  });

  it("apiClient.runAIAnalysis sends POST to /api/analysis/{id}/run", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: { get: () => "application/json" },
      json: async () => ({ status: "completed", encounter_id: 42, overall_urgency: "ROUTINE" }),
    });

    const client = new ApiClient({ baseUrl: "http://127.0.0.1:8000", fetchFn: mockFetch });
    const result = await client.runAIAnalysis(42);

    expect(result.status).toBe("completed");
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/analysis/42/run",
      expect.objectContaining({ method: "POST" })
    );
  });

  it("apiClient.decideAIInsight sends PUT to /api/insights/{id}/decision", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: { get: () => "application/json" },
      json: async () => ({ id: 5, status: "accepted", provenance: "doctor_verified" }),
    });

    const client = new ApiClient({ baseUrl: "http://127.0.0.1:8000", fetchFn: mockFetch });
    const result = await client.decideAIInsight(5, { decision: "accepted" });

    expect(result.status).toBe("accepted");
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/insights/5/decision",
      expect.objectContaining({
        method: "PUT",
        body: JSON.stringify({ decision: "accepted" }),
      })
    );
  });

  it("verifies AIClinicalInsights renders with no encounter state cleanly", () => {
    const html = renderToString(
      <StoreProvider>
        <AIClinicalInsights encounterId={null} patientId={null} isFinalized={false} />
      </StoreProvider>
    );

    expect(html).toContain("No active encounter linked for AI Clinical Analysis.");
  });

  it("verifies AIClinicalInsights renders initial loading/pipeline state", () => {
    const html = renderToString(
      <StoreProvider>
        <AIClinicalInsights encounterId={1} patientId={1} isFinalized={false} />
      </StoreProvider>
    );

    expect(html).toContain("Running AI Pipeline...");
  });
});
