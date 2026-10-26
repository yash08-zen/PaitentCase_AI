import { describe, it, expect, vi } from "vitest";
import { ApiClient, ApiError } from "../api/client";

describe("Frontend Milestone M9 Security, Validation & Resilience Tests", () => {
  it("formats HTTP 429 rate limit error with Retry-After header", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 429,
      headers: {
        get: (h) => (h.toLowerCase() === "retry-after" ? "45" : null),
      },
      text: async () => JSON.stringify({ detail: "Too many requests. Please wait 45 seconds before retrying." }),
    });

    const client = new ApiClient({ baseUrl: "http://127.0.0.1:8000", fetchFn: mockFetch });

    await expect(client.get("/api/auth/login")).rejects.toThrowError(
      /Too many requests|Rate limit exceeded/
    );
  });

  it("formats structured HTTP 422 validation errors with field names", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      headers: {
        get: (h) => (h.toLowerCase() === "content-type" ? "application/json" : null),
      },
      text: async () => JSON.stringify({
        detail: "Input validation failed. Please verify submitted fields.",
        errors: [
          { field: "date_of_birth", message: "Invalid date format" },
          { field: "gender", message: "Invalid gender choice" },
        ],
      }),
    });

    const client = new ApiClient({ baseUrl: "http://127.0.0.1:8000", fetchFn: mockFetch });

    try {
      await client.post("/api/patients", {});
      expect.fail("Should have thrown ApiError");
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError);
      expect(err.status).toBe(422);
      expect(err.message).toContain("date_of_birth: Invalid date format");
      expect(err.message).toContain("gender: Invalid gender choice");
    }
  });

  it("handles request timeout via AbortError with status 408", async () => {
    const mockFetch = vi.fn().mockRejectedValue({
      name: "AbortError",
      message: "The operation was aborted",
    });

    const client = new ApiClient({ baseUrl: "http://127.0.0.1:8000", fetchFn: mockFetch });

    try {
      await client.get("/api/health", { timeoutMs: 1 });
      expect.fail("Should have thrown ApiError on timeout");
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError);
      expect(err.status).toBe(408);
      expect(err.message).toContain("Request timed out");
    }
  });

  it("handles server 500 error without exposing stack traces", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      headers: {
        get: (h) => (h.toLowerCase() === "content-type" ? "application/json" : null),
      },
      text: async () => JSON.stringify({
        detail: "An internal server error occurred. Please contact system support.",
        error_code: "INTERNAL_SERVER_ERROR",
      }),
    });

    const client = new ApiClient({ baseUrl: "http://127.0.0.1:8000", fetchFn: mockFetch });

    try {
      await client.get("/api/some-endpoint");
      expect.fail("Should have thrown ApiError");
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError);
      expect(err.status).toBe(500);
      expect(err.message).toContain("An internal server error occurred");
      expect(err.message).not.toContain("Traceback");
      expect(err.message).not.toContain("File \"/");
    }
  });
});
