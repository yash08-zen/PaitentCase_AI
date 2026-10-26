import { describe, it, expect, vi } from "vitest";
import React from "react";
import { renderToString } from "react-dom/server";
import { StoreProvider } from "../state/store";
import Dashboard from "./Dashboard";

describe("Frontend Milestone M8 Doctor Dashboard & Review Tests", () => {
  it("verifies apiClient has all required M8 review and dashboard endpoints", async () => {
    const { apiClient } = await import("../api/client");
    expect(typeof apiClient.saveDoctorNotes).toBe("function");
    expect(typeof apiClient.getDoctorNotes).toBe("function");
    expect(typeof apiClient.finalizeCase).toBe("function");
    expect(typeof apiClient.getDashboardSummary).toBe("function");
    expect(typeof apiClient.getDashboardCases).toBe("function");
  });

  it("renders Dashboard within StoreProvider without crashing", () => {
    const html = renderToString(
      <StoreProvider>
        <Dashboard go={() => {}} />
      </StoreProvider>
    );

    expect(html).toContain("Dashboard");
    expect(html).toContain("Total patients");
    expect(html).toContain("Interviews complete");
    expect(html).toContain("Needs review");
    expect(html).toContain("Cases requiring review");
  });

  it("apiClient.saveDoctorNotes sends PUT to /api/encounters/{id}/notes", async () => {
    const { ApiClient } = await import("../api/client");
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: { get: () => "application/json" },
      json: async () => ({ id: 10, doctor_notes: "Patient reviewed and stable." }),
    });

    const client = new ApiClient({ baseUrl: "http://127.0.0.1:8000", fetchFn: mockFetch });
    const result = await client.saveDoctorNotes(10, "Patient reviewed and stable.");

    expect(result.doctor_notes).toBe("Patient reviewed and stable.");
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/encounters/10/notes",
      expect.objectContaining({
        method: "PUT",
        body: JSON.stringify({ doctor_notes: "Patient reviewed and stable." }),
      })
    );
  });

  it("apiClient.finalizeCase sends POST to /api/encounters/{id}/finalize", async () => {
    const { ApiClient } = await import("../api/client");
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: { get: () => "application/json" },
      json: async () => ({
        encounter_id: 15,
        status: "reviewed",
        review_status: "reviewed",
        doctor_notes: "Review finalized.",
        reviewed_at: "2026-10-24T00:00:00Z",
      }),
    });

    const client = new ApiClient({ baseUrl: "http://127.0.0.1:8000", fetchFn: mockFetch });
    const result = await client.finalizeCase(15, "Review finalized.");

    expect(result.status).toBe("reviewed");
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/encounters/15/finalize",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ doctor_notes: "Review finalized." }),
      })
    );
  });

  it("apiClient.getDashboardCases queries /api/dashboard/cases with query parameters", async () => {
    const { ApiClient } = await import("../api/client");
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: { get: () => "application/json" },
      json: async () => ([{ encounter_id: 1, patient_name: "John Doe", open_flags: 1 }]),
    });

    const client = new ApiClient({ baseUrl: "http://127.0.0.1:8000", fetchFn: mockFetch });
    const result = await client.getDashboardCases({ status: "needs_review", search: "John" });

    expect(result).toHaveLength(1);
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/dashboard/cases?status=needs_review&search=John",
      expect.objectContaining({
        method: "GET",
      })
    );
  });
});
