import { describe, it, expect } from "vitest";
import React from "react";
import { renderToString } from "react-dom/server";
import { StoreProvider } from "../state/store";
import Login from "./Login";
import Shell from "../components/Shell";
import AuditLog from "./AuditLog";
import PatientPortal from "./PatientPortal";

describe("Frontend Role-Based Access and Auth Smoke Tests", () => {
  it("renders Login screen with all 4 synthetic demo roles", () => {
    const html = renderToString(<Login onLogin={() => {}} />);
    expect(html).toContain("Doctor");
    expect(html).toContain("Clinic Staff");
    expect(html).toContain("Patient");
    expect(html).toContain("Administrator");
    expect(html).toContain("Sign In");
    expect(html).toContain("Prototype supporting clinician review - not a diagnostic tool");
  });

  it("renders session expired message banner when sessionMessage is passed", () => {
    const html = renderToString(
      <Login onLogin={() => {}} sessionMessage="Your session has expired. Please log in again." />
    );
    expect(html).toContain("Your session has expired. Please log in again.");
  });

  it("renders Shell with doctor role navigation and role badge", () => {
    const doctorUser = { id: 2, username: "doctor", role: "doctor" };
    const html = renderToString(
      <StoreProvider>
        <Shell user={doctorUser} page="dashboard" go={() => {}} onLogout={() => {}}>
          <div>Doctor Content</div>
        </Shell>
      </StoreProvider>
    );

    expect(html).toContain("Doctor review");
    expect(html).toContain("Dashboard");
    expect(html).toContain("Active patient");
    expect(html).toContain("tag t-doc");
    expect(html).toContain("doctor");
    expect(html).not.toContain("Audit logs"); // Doctor cannot see audit logs
  });

  it("renders Shell with patient role restricted navigation", () => {
    const patientUser = { id: 4, username: "patient", role: "patient" };
    const html = renderToString(
      <StoreProvider>
        <Shell user={patientUser} page="interview" go={() => {}} onLogout={() => {}}>
          <div>Patient Content</div>
        </Shell>
      </StoreProvider>
    );

    expect(html).toContain("My Patient Portal");
    expect(html).toContain("Adaptive interview");
    expect(html).toContain("Documents");
    expect(html).toContain("Patient Portal Session");
    expect(html).toContain("Restricted to own medical record");
    // Patient should NOT see Doctor Review or Dashboard or Audit logs
    expect(html).not.toContain("Doctor review");
    expect(html).not.toContain("Dashboard");
    expect(html).not.toContain("Audit logs");
  });

  it("renders Shell with admin role navigation including audit logs", () => {
    const adminUser = { id: 1, username: "admin", role: "admin" };
    const html = renderToString(
      <StoreProvider>
        <Shell user={adminUser} page="audit" go={() => {}} onLogout={() => {}}>
          <div>Admin Content</div>
        </Shell>
      </StoreProvider>
    );

    expect(html).toContain("Audit logs");
    expect(html).toContain("Dashboard");
    expect(html).toContain("Doctor review");
  });

  it("renders AuditLog page structure with filter tags", () => {
    const html = renderToString(<AuditLog />);
    expect(html).toContain("System Audit Trail");
    expect(html).toContain("Filter by Action:");
    expect(html).toContain("LOGIN_SUCCESS");
    expect(html).toContain("LOGIN_FAILED");
    expect(html).toContain("LOGOUT");
  });

  it("renders Login screen with New Patient Sign Up tab", () => {
    const html = renderToString(<Login onLogin={() => {}} />);
    expect(html).toContain("New Patient Sign Up");
    expect(html).toContain("Sign In");
    expect(html).toContain("Create New Patient Account →");
  });

  it("renders PatientPortal with 3-step intake flow and trilingual options", () => {
    const patientUser = { id: 4, username: "patient", role: "patient" };
    const html = renderToString(
      <StoreProvider>
        <PatientPortal go={() => {}} user={patientUser} />
      </StoreProvider>
    );

    expect(html).toContain("Patient Portal");
    expect(html).toContain("Step 1: Registered");
    expect(html).toContain("Step 2: Documents");
    expect(html).toContain("Step 3: Interview");
    expect(html).toContain("Upload Prescriptions");
    expect(html).toContain("Adaptive Case-Taking");
    expect(html).toContain("हिन्दी");
    expect(html).toContain("मराठी");
  });
});

