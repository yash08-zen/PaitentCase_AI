import { describe, it, expect, vi } from "vitest";
import React from "react";
import { renderToString } from "react-dom/server";
import { StoreProvider } from "../state/store";
import Documents from "./Documents";

describe("Frontend Milestone M6 Prescription Upload & OCR Tests", () => {
  it("verifies apiClient has all required M6 document and OCR endpoints", async () => {
    const { apiClient } = await import("../api/client");
    expect(typeof apiClient.uploadDocument).toBe("function");
    expect(typeof apiClient.listDocuments).toBe("function");
    expect(typeof apiClient.getDocumentExtraction).toBe("function");
    expect(typeof apiClient.getDocument).toBe("function");
    expect(typeof apiClient.getDocumentFileBlob).toBe("function");
  });

  it("renders Documents screen within StoreProvider without crashing", () => {
    const html = renderToString(
      <StoreProvider>
        <Documents go={() => {}} />
      </StoreProvider>
    );

    // Initial render shows header, upload card, and non-diagnostic boundary notice
    expect(html).toContain("Medical documents &amp; prescriptions");
    expect(html).toContain("Upload document");
    expect(html).toContain("NON-DIAGNOSTIC NOTICE");
    expect(html).toContain("document_extracted_unverified");
  });

  it("apiClient.uploadDocument sends multipart FormData to /api/documents/upload/{patientId}", async () => {
    const { ApiClient } = await import("../api/client");
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      headers: { get: () => "application/json" },
      json: async () => ({ id: 42, status: "pending", document_type: "prescription" }),
    });

    const client = new ApiClient({ baseUrl: "http://127.0.0.1:8000", fetchFn: mockFetch });
    const dummyBlob = new Blob(["fake-img-bytes"], { type: "image/png" });

    const result = await client.uploadDocument(12, dummyBlob, 5, "prescription");

    expect(result.id).toBe(42);
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/documents/upload/12",
      expect.objectContaining({
        method: "POST",
        body: expect.any(FormData),
      })
    );
  });

  it("apiClient.listDocuments formats query parameters correctly", async () => {
    const { ApiClient } = await import("../api/client");
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: { get: () => "application/json" },
      json: async () => [],
    });

    const client = new ApiClient({ baseUrl: "http://127.0.0.1:8000", fetchFn: mockFetch });
    await client.listDocuments({ patientId: 99, encounterId: 7 });

    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/documents?patient_id=99&encounter_id=7",
      expect.objectContaining({ method: "GET" })
    );
  });

  it("apiClient.getDocumentExtraction queries /api/documents/{id}/extraction", async () => {
    const { ApiClient } = await import("../api/client");
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: { get: () => "application/json" },
      json: async () => ({ id: 42, status: "completed", extracted_text: "Amoxicillin 500mg" }),
    });

    const client = new ApiClient({ baseUrl: "http://127.0.0.1:8000", fetchFn: mockFetch });
    const extraction = await client.getDocumentExtraction(42);

    expect(extraction.status).toBe("completed");
    expect(extraction.extracted_text).toBe("Amoxicillin 500mg");
    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/documents/42/extraction",
      expect.objectContaining({ method: "GET" })
    );
  });
});
