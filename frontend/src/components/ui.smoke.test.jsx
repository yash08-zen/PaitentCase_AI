import { describe, it, expect } from "vitest";
import React from "react";
import { renderToString } from "react-dom/server";
import {
  Spinner,
  EmptyState,
  ErrorBanner,
  Toast,
  ClinicalNotice,
  HealthIndicator,
  Icon,
  Logo,
} from "./ui";
import App from "../App";

describe("Frontend Shared Primitives Smoke Tests", () => {
  it("renders ClinicalNotice with required boundary text", () => {
    const html = renderToString(<ClinicalNotice />);
    expect(html).toContain("Prototype supporting clinician review — not a diagnostic tool");
    expect(html).toContain("CLINICAL NOTICE");
    expect(html).toContain("role=\"note\"");
  });

  it("renders Spinner with role status", () => {
    const html = renderToString(<Spinner text="Processing request..." />);
    expect(html).toContain("role=\"status\"");
    expect(html).toContain("Processing request...");
    expect(html).toContain("spinner-svg");
  });

  it("renders EmptyState with custom title, text, and action", () => {
    const html = renderToString(
      <EmptyState
        title="No cases found"
        text="No pending patient encounters."
        action={<button className="btn sm">New Intake</button>}
      />
    );
    expect(html).toContain("No cases found");
    expect(html).toContain("No pending patient encounters.");
    expect(html).toContain("New Intake");
  });

  it("renders ErrorBanner with error message and retry button", () => {
    const html = renderToString(
      <ErrorBanner
        title="Failed to load patient"
        message="Backend returned 500 error."
        onRetry={() => {}}
      />
    );
    expect(html).toContain("Failed to load patient");
    expect(html).toContain("Backend returned 500 error.");
    expect(html).toContain("Retry");
    expect(html).toContain("role=\"alert\"");
  });

  it("renders Toast with success and error styling", () => {
    const successHtml = renderToString(<Toast toast="Patient registered successfully" />);
    expect(successHtml).toContain("toast-success");
    expect(successHtml).toContain("Patient registered successfully");

    const errorHtml = renderToString(
      <Toast toast={{ message: "Validation failed", type: "error" }} onDismiss={() => {}} />
    );
    expect(errorHtml).toContain("toast-error");
    expect(errorHtml).toContain("Validation failed");
    expect(errorHtml).toContain("Dismiss notification");
  });

  it("renders HealthIndicator initially in checking state", () => {
    const html = renderToString(<HealthIndicator />);
    expect(html).toContain("health-indicator");
    expect(html).toContain("role=\"status\"");
  });

  it("renders Logo and Icon correctly", () => {
    const logoHtml = renderToString(<Logo />);
    expect(logoHtml).toContain("PatientCase AI");

    const iconHtml = renderToString(<Icon n="check" size={24} />);
    expect(iconHtml).toContain("svg");
    expect(iconHtml).toContain("width=\"24\"");
  });

  it("renders main App component without crashing", () => {
    const html = renderToString(<App />);
    expect(html).toContain("PatientCase AI");
    expect(html).toContain("Welcome to PatientCase AI");
    expect(html).toContain("Prototype supporting clinician review — not a diagnostic tool");
  });
});

