import { describe, it, expect, vi } from "vitest";
import { ApiClient, ApiError } from "./client";

describe("ApiClient & Error Normalization", () => {
  it("handles successful JSON response", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => ({ status: "healthy", database: "connected" }),
    });

    const client = new ApiClient({ baseUrl: "http://test-server:8000", fetchFn: mockFetch });
    const res = await client.get("/health");

    expect(mockFetch).toHaveBeenCalledWith("http://test-server:8000/health", expect.objectContaining({
      method: "GET",
    }));
    expect(res).toEqual({ status: "healthy", database: "connected" });
  });

  it("handles network error when server cannot be reached", async () => {
    const mockFetch = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));

    const client = new ApiClient({ baseUrl: "http://test-server:8000", fetchFn: mockFetch });

    await expect(client.get("/health")).rejects.toThrow(ApiError);
    try {
      await client.get("/health");
    } catch (err) {
      expect(err.isNetworkError).toBe(true);
      expect(err.status).toBe(0);
      expect(err.code).toBe("NETWORK_ERROR");
      expect(err.message).toContain("Network error: Unable to reach the backend server");
    }
  });

  it("normalizes 400 and 422 validation errors with Pydantic details", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      statusText: "Unprocessable Entity",
      headers: new Headers({ "content-type": "application/json" }),
      text: async () => JSON.stringify({
        detail: [
          { loc: ["body", "full_name"], msg: "Field required" },
          { loc: ["body", "age"], msg: "Must be greater than 0" },
        ],
      }),
    });

    const client = new ApiClient({ baseUrl: "http://test-server:8000", fetchFn: mockFetch });

    try {
      await client.post("/api/patients", {});
      expect.unreachable();
    } catch (err) {
      expect(err instanceof ApiError).toBe(true);
      expect(err.status).toBe(422);
      expect(err.code).toBe("VALIDATION_ERROR");
      expect(err.message).toBe("full_name: Field required; age: Must be greater than 0");
    }
  });

  it("normalizes 401 Unauthorized errors", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      statusText: "Unauthorized",
      headers: new Headers({ "content-type": "application/json" }),
      text: async () => JSON.stringify({ detail: "Incorrect username or password" }),
    });

    const client = new ApiClient({ baseUrl: "http://test-server:8000", fetchFn: mockFetch });

    try {
      await client.post("/api/auth/login", { username: "wrong", password: "bad" });
      expect.unreachable();
    } catch (err) {
      expect(err.status).toBe(401);
      expect(err.code).toBe("UNAUTHORIZED");
      expect(err.message).toBe("Incorrect username or password");
    }
  });

  it("normalizes 403 Forbidden errors", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      statusText: "Forbidden",
      headers: new Headers({ "content-type": "application/json" }),
      text: async () => JSON.stringify({}),
    });

    const client = new ApiClient({ baseUrl: "http://test-server:8000", fetchFn: mockFetch });

    try {
      await client.get("/api/admin/metrics");
      expect.unreachable();
    } catch (err) {
      expect(err.status).toBe(403);
      expect(err.code).toBe("FORBIDDEN");
      expect(err.message).toBe("Access forbidden. You do not have permission to perform this action.");
    }
  });

  it("normalizes 404 Not Found errors", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      statusText: "Not Found",
      headers: new Headers({ "content-type": "application/json" }),
      text: async () => JSON.stringify({}),
    });

    const client = new ApiClient({ baseUrl: "http://test-server:8000", fetchFn: mockFetch });

    try {
      await client.get("/api/patients/9999");
      expect.unreachable();
    } catch (err) {
      expect(err.status).toBe(404);
      expect(err.code).toBe("NOT_FOUND");
      expect(err.message).toBe("The requested resource was not found.");
    }
  });

  it("normalizes 500 server errors", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      statusText: "Internal Server Error",
      headers: new Headers({ "content-type": "application/json" }),
      text: async () => JSON.stringify({}),
    });

    const client = new ApiClient({ baseUrl: "http://test-server:8000", fetchFn: mockFetch });

    try {
      await client.get("/api/crash");
      expect.unreachable();
    } catch (err) {
      expect(err.status).toBe(500);
      expect(err.code).toBe("SERVER_ERROR");
      expect(err.message).toContain("Server error (500)");
    }
  });

  it("attaches Authorization header when token is set", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => ({ id: 1, username: "doctor" }),
    });

    const client = new ApiClient({ baseUrl: "http://test-server:8000", fetchFn: mockFetch });
    client.setToken("sample-jwt-token");

    await client.get("/api/auth/me");

    const calledHeaders = mockFetch.mock.calls[0][1].headers;
    expect(calledHeaders.get("Authorization")).toBe("Bearer sample-jwt-token");
  });
  it("login() stores token and user profile", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => ({
        access_token: "jwt-token-12345",
        token_type: "bearer",
        user: { id: 2, username: "doctor", role: "doctor", is_active: true },
      }),
    });

    const client = new ApiClient({ baseUrl: "http://test-server:8000", fetchFn: mockFetch });
    const res = await client.login("doctor", "Doctor@1234");

    expect(res.access_token).toBe("jwt-token-12345");
    expect(client.getToken()).toBe("jwt-token-12345");
    expect(client.getUser()?.username).toBe("doctor");
  });

  it("logout() sends logout request and clears token and user profile", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => ({ message: "Logged out successfully" }),
    });

    const client = new ApiClient({ baseUrl: "http://test-server:8000", fetchFn: mockFetch });
    client.setToken("active-token");
    client.setUser({ username: "doctor" });

    await client.logout();

    expect(client.getToken()).toBeNull();
    expect(client.getUser()).toBeNull();
  });

  it("triggers onUnauthorized callback when a protected endpoint returns 401", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      statusText: "Unauthorized",
      headers: new Headers({ "content-type": "application/json" }),
      text: async () => JSON.stringify({ detail: "Invalid or expired token" }),
    });

    const onUnauthorized = vi.fn();
    const client = new ApiClient({ baseUrl: "http://test-server:8000", fetchFn: mockFetch });
    client.setOnUnauthorized(onUnauthorized);

    await expect(client.get("/api/dashboard/summary")).rejects.toThrow(ApiError);
    expect(onUnauthorized).toHaveBeenCalledWith("Your session has expired. Please log in again.");
  });

  it("does NOT trigger onUnauthorized callback when login endpoint returns 401", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      statusText: "Unauthorized",
      headers: new Headers({ "content-type": "application/json" }),
      text: async () => JSON.stringify({ detail: "Incorrect username or password" }),
    });

    const onUnauthorized = vi.fn();
    const client = new ApiClient({ baseUrl: "http://test-server:8000", fetchFn: mockFetch });
    client.setOnUnauthorized(onUnauthorized);

    await expect(client.post("/api/auth/login", { username: "doc", password: "bad" })).rejects.toThrow(ApiError);
    expect(onUnauthorized).not.toHaveBeenCalled();
  });
});

