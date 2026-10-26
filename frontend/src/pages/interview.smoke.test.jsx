import { describe, it, expect, vi } from "vitest";
import React from "react";
import { renderToString } from "react-dom/server";
import { StoreProvider } from "../state/store";
import Interview from "./Interview";

describe("Frontend Milestone M4 Adaptive Interview Smoke Tests", () => {
  it("renders Interview screen within StoreProvider without crashing", () => {
    const html = renderToString(
      <StoreProvider>
        <Interview go={() => {}} />
      </StoreProvider>
    );

    // Initial render displays either loading spinner or question header
    expect(html).toContain("Adaptive interview");
    expect(html).toContain("Loading adaptive interview");
  });

  it("verifies apiClient has all required M4 interview methods", async () => {
    const { apiClient } = await import("../api/client");
    expect(typeof apiClient.getNextQuestion).toBe("function");
    expect(typeof apiClient.submitResponse).toBe("function");
    expect(typeof apiClient.backQuestion).toBe("function");
    expect(typeof apiClient.getInterviewProgress).toBe("function");
    expect(typeof apiClient.resumeInterview).toBe("function");
    expect(typeof apiClient.getInterviewAnswers).toBe("function");
    expect(typeof apiClient.completeInterview).toBe("function");
  });
});
