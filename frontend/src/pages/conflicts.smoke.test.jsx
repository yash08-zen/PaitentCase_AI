import { describe, it, expect, vi } from "vitest";
import React from "react";
import { renderToString } from "react-dom/server";
import { StoreProvider } from "../state/store";
import DoctorReview from "./DoctorReview";

describe("Frontend Milestone M7 Medication Discrepancy & Conflict Tests", () => {
  it("verifies apiClient has all required M7 conflict endpoints", async () => {
    const { apiClient } = await import("../api/client");
    expect(typeof apiClient.listConflicts).toBe("function");
    expect(typeof apiClient.getContradictions).toBe("function");
    expect(typeof apiClient.resolveConflict).toBe("function");
  });

  it("apiClient.listConflicts formats encounter_id and refresh query params", async () => {
    const { ApiClient } = await import("../api/client");
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: { get: () => "application/json" },
      json: async () => [{ id: 1, rule_id: "RULE-MED-DENIAL", status: "open" }],
    });

    const client = new ApiClient({ baseUrl: "http://127.0.0.1:8000", fetchFn: mockFetch });
    const result = await client.listConflicts(15, { refresh: true });

    expect(result.length).toBe(1);
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/conflicts?encounter_id=15&refresh=true",
      expect.objectContaining({ method: "GET" })
    );
  });

  it("apiClient.resolveConflict sends PUT request with status and resolution_note", async () => {
    const { ApiClient } = await import("../api/client");
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: { get: () => "application/json" },
      json: async () => ({ id: 7, status: "resolved", resolution_note: "Patient discontinued drug" }),
    });

    const client = new ApiClient({ baseUrl: "http://127.0.0.1:8000", fetchFn: mockFetch });
    const result = await client.resolveConflict(7, {
      status: "resolved",
      resolutionNote: "Patient discontinued drug",
    });

    expect(result.status).toBe("resolved");
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/conflicts/7/resolve",
      expect.objectContaining({
        method: "PUT",
        body: JSON.stringify({
          status: "resolved",
          resolution_note: "Patient discontinued drug",
        }),
      })
    );
  });

  it("renders DoctorReview screen with StoreProvider without crashing", () => {
    const html = renderToString(
      <StoreProvider>
        <DoctorReview go={() => {}} />
      </StoreProvider>
    );

    // Initial render shows spinner loading clinical case summary
    expect(html).toContain("Loading clinical case summary");
  });
});
