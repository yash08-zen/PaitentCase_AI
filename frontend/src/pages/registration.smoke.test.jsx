import { describe, it, expect } from "vitest";
import React from "react";
import { renderToString } from "react-dom/server";
import { StoreProvider } from "../state/store";
import Register from "./Register";
import PatientList from "./PatientList";

describe("Frontend Milestone M3 Registration & Patient List Smoke Tests", () => {
  it("renders Register screen with all input fields and informed consent checkbox", () => {
    const html = renderToString(
      <StoreProvider>
        <Register go={() => {}} />
      </StoreProvider>
    );

    expect(html).toContain("Register Patient");
    expect(html).toContain("Full Name *");
    expect(html).toContain("Age *");
    expect(html).toContain("Gender *");
    expect(html).toContain("Contact Number");
    expect(html).toContain("Preferred Language");
    expect(html).toContain("Informed Consent Required: *");
    expect(html).toContain("Register and continue");
  });

  it("renders PatientList screen with search input, filter chips, and register button", () => {
    const html = renderToString(
      <StoreProvider>
        <PatientList go={() => {}} />
      </StoreProvider>
    );

    expect(html).toContain("Patients");
    expect(html).toContain("Search patients");
    expect(html).toContain("Register patient");
    expect(html).toContain("Registered");
    expect(html).toContain("In interview");
    expect(html).toContain("Needs review");
    expect(html).toContain("Ready for review");
    expect(html).toContain("Finalized");
  });
});
