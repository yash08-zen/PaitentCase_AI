import { useState, useEffect, useCallback } from "react";
import { useStore } from "../state/store";
import apiClient from "../api/client";
import { Empty, Icon, Proto, Ring, Source, StatusTag, Tag, Spinner } from "../components/ui";

const ST = { open: ["warn", "Open"], reviewed: ["doc", "Reviewed"], verified: ["ver", "Verified"] };

function ConflictCard({ f, onResolve }) {
  const [busy, setBusy] = useState(false);
  const isOpen = f.status === "open";
  const isResolved = f.status === "resolved";

  const handleAction = async (status, note) => {
    setBusy(true);
    try {
      await onResolve(status, note);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className={`card conflict ${isOpen ? "open" : "reviewed"}`} style={{ marginBottom: 14 }}>
      <div className="row">
        <div className="chead">
          <Icon n="alert" />
          <h2 style={{ fontSize: "1.1rem", margin: 0 }}>
            {f.rule_id ? `[${f.rule_id}] ${f.field}` : `Discrepancy: ${f.field}`}
          </h2>
        </div>
        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          {f.rule_id && <Tag kind="warn">{f.rule_id}</Tag>}
          <Tag kind={isOpen ? "warn" : isResolved ? "ver" : "sys"}>
            {isOpen ? "Verification Required" : isResolved ? "Resolved" : "Dismissed"}
          </Tag>
        </div>
      </div>

      {f.description && (
        <p className="small soft" style={{ margin: "6px 0 10px" }}>
          {f.description}
        </p>
      )}

      <div className="vs">
        <div className="src pat">
          <Source s={f.source_a || "patient_reported"} />
          <p className="small soft">Patient testimony</p>
          <b>"{f.value_a || 'None'}"</b>
        </div>
        <span className="vsmark">vs</span>
        <div className="src doc">
          <Source s={f.source_b || "document_extracted_unverified"} />
          <p className="small soft">Document extraction</p>
          <b>"{f.value_b || 'None'}"</b>
        </div>
      </div>

      {f.resolution_note && (
        <div style={{ marginTop: 10, padding: "8px 12px", background: "#f0f7f0", borderRadius: 8 }}>
          <span className="small">
            <b>Clinician resolution:</b> {f.resolution_note}
          </span>
        </div>
      )}

      <div className="actions" style={{ marginTop: 12 }}>
        {isOpen ? (
          <>
            <button
              className="btn primary sm"
              disabled={busy}
              onClick={() => handleAction("resolved", "Verified with patient. Clinical record reconciled.")}
            >
              {busy ? "Resolving..." : "Verified with patient"}
            </button>
            <button
              className="btn out sm"
              disabled={busy}
              onClick={() => handleAction("dismissed", "Discrepancy dismissed by clinician after inspection.")}
            >
              Dismiss discrepancy
            </button>
          </>
        ) : (
          <button
            className="btn out sm"
            disabled={busy}
            onClick={() => handleAction("open", "Discrepancy reopened for clinical review.")}
          >
            Reopen discrepancy
          </button>
        )}
      </div>
    </div>
  );
}

export default function DoctorReview({ go }) {
  const { patients, cases, activeId, setNotes, finalize, notify } = useStore();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [encounterId, setEncounterId] = useState(null);
  const [summaryData, setSummaryData] = useState(null);
  const [missingData, setMissingData] = useState(null);
  const [readinessData, setReadinessData] = useState(null);
  const [conflictsData, setConflictsData] = useState([]);
  const [notesText, setNotesText] = useState("");
  const [savingNotes, setSavingNotes] = useState(false);
  const [finalizing, setFinalizing] = useState(false);
  const [isFinalized, setIsFinalized] = useState(false);
  const [finalizedInfo, setFinalizedInfo] = useState(null);

  const p = patients.find((x) => x.id === activeId);
  const c = cases[activeId];

  const loadCaseData = useCallback(async () => {
    if (!p) return;
    setLoading(true);
    setError(null);
    try {
      let resolvedEncId = c?.encounterId;
      if (!resolvedEncId && p.backendId) {
        const encList = await apiClient.get("/api/encounters");
        const match = Array.isArray(encList)
          ? encList.find((e) => e.patient_id === p.backendId)
          : null;
        resolvedEncId = match ? match.id : null;
      }

      setEncounterId(resolvedEncId);

      if (resolvedEncId) {
        const [sumRes, misRes, readRes, confRes] = await Promise.all([
          apiClient.getCaseSummary(resolvedEncId),
          apiClient.getMissingInformation(resolvedEncId),
          apiClient.getCaseReadiness(resolvedEncId),
          apiClient.listConflicts(resolvedEncId, { refresh: true }).catch(() => []),
        ]);
        setSummaryData(sumRes);
        setMissingData(misRes);
        setReadinessData(readRes);
        setConflictsData(Array.isArray(confRes) ? confRes : []);

        if (sumRes) {
          if (sumRes.doctor_notes) {
            setNotesText(sumRes.doctor_notes);
          } else if (c?.notes) {
            setNotesText(c.notes);
          }
          if (sumRes.review_status === "reviewed" || c?.finalized) {
            setIsFinalized(true);
            setFinalizedInfo({
              reviewed_at: sumRes.reviewed_at,
              reviewed_by: sumRes.reviewed_by,
            });
          }
        }
      } else if (c) {
        setNotesText(c.notes || "");
        if (c.finalized) setIsFinalized(true);
      }
    } catch (err) {
      setError(err.message || "Failed to load case review data from backend");
    } finally {
      setLoading(false);
    }
  }, [p, c?.encounterId, c?.notes, c?.finalized]);

  useEffect(() => {
    loadCaseData();
  }, [loadCaseData]);

  const handleResolveConflict = async (conflictId, status, note) => {
    try {
      await apiClient.resolveConflict(conflictId, { status, resolutionNote: note });
      notify(status === "resolved" ? "Discrepancy reconciled and verified" : "Discrepancy status updated");
      await loadCaseData();
    } catch (err) {
      notify(err.message || "Failed to update discrepancy", true);
    }
  };

  const handleSaveNotes = async () => {
    if (!encounterId) {
      setNotes(p.id, notesText);
      notify("Notes saved locally");
      return;
    }
    setSavingNotes(true);
    try {
      await apiClient.saveDoctorNotes(encounterId, notesText);
      setNotes(p.id, notesText);
      notify("Clinician review notes saved successfully");
    } catch (err) {
      notify(err.message || "Failed to save clinician notes", true);
    } finally {
      setSavingNotes(false);
    }
  };

  const handleFinalize = async () => {
    if (!encounterId) {
      finalize(p.id);
      setIsFinalized(true);
      notify("Case finalized locally");
      return;
    }
    setFinalizing(true);
    try {
      const res = await apiClient.finalizeCase(encounterId, notesText);
      finalize(p.id);
      setIsFinalized(true);
      setFinalizedInfo({
        reviewed_at: res.reviewed_at,
        reviewed_by: res.reviewed_by,
      });
      notify("Case finalized & review completed. Interview is locked.");
      await loadCaseData();
    } catch (err) {
      notify(err.message || "Failed to finalize case", true);
    } finally {
      setFinalizing(false);
    }
  };

  if (!p) {
    return (
      <Empty
        title="No patient selected"
        text="Choose a patient to review."
        action={
          <button className="btn primary" onClick={() => go("patients")}>
            Open patient list
          </button>
        }
      />
    );
  }

  if (loading) {
    return (
      <div style={{ padding: "60px 0", textAlign: "center" }}>
        <Spinner text={`Loading clinical case summary for ${p.name}...`} />
      </div>
    );
  }

  if (error) {
    return (
      <Empty
        title="Error loading case data"
        text={error}
        action={
          <button className="btn primary" onClick={loadCaseData}>
            Retry
          </button>
        }
      />
    );
  }

  const scoreValue = readinessData?.score != null ? Math.round(readinessData.score * 100) : 0;
  const factors = readinessData?.factors || {};
  const missingFields = missingData?.missing_fields || [];
  const findingsList = summaryData?.structured_findings || [];
  const summaryText = summaryData?.summary_text || "No summary text generated yet.";

  return (
    <>
      <div className="head">
        <div>
          <h1>{p.name}</h1>
          <p className="soft">
            {p.age ? `${p.age} yrs` : "Age not provided"} • {p.gender || "Gender not provided"} •{" "}
            {p.language || "English"} • Encounter #{encounterId || p.id} • Registered {p.registered}
          </p>
        </div>
        <div className="actions">
          <Tag kind={readinessData?.label === "Ready for Review" ? "ok" : "warn"}>
            {readinessData?.label || "Awaiting Review"}
          </Tag>
          {missingFields.length > 0 && (
            <Tag kind="bad">
              {missingFields.length} missing field{missingFields.length > 1 ? "s" : ""}
            </Tag>
          )}
        </div>
      </div>

      <div className="rv">
        <div className="rvmain">
          {/* Clinical Discrepancies & Contradictions (from M7 engine) */}
          {conflictsData.length > 0 && (
            <div className="rvsec">
              <div className="row">
                <h2>Cross-source discrepancies ({conflictsData.filter((x) => x.status === "open").length} open)</h2>
                <Proto>Clinical discrepancy rules</Proto>
              </div>
              <p className="small soft" style={{ margin: "-6px 0 12px" }}>
                Patient statements compared with prescription documents. Discrepancies require doctor verification.
              </p>
              {conflictsData.map((f) => (
                <ConflictCard
                  key={f.id}
                  f={f}
                  onResolve={(status, note) => handleResolveConflict(f.id, status, note)}
                />
              ))}
            </div>
          )}

          {/* Backend Generated Case Summary */}
          <div className="card">
            <div className="row">
              <h2>Case summary</h2>
              <div className="actions">
                <Source s="system" />
                <Proto>Rule-based text, not a diagnosis</Proto>
              </div>
            </div>
            <pre
              className="sumtext"
              style={{
                whiteSpace: "pre-wrap",
                fontFamily: "inherit",
                fontSize: "0.95rem",
                lineHeight: "1.5",
                background: "#f9fafb",
                padding: "1rem",
                borderRadius: "8px",
                border: "1px solid #e5e7eb",
              }}
            >
              {summaryText}
            </pre>
          </div>

          {/* Structured Findings Table with Source Provenance */}
          <div className="card">
            <div className="row">
              <h2>Structured findings</h2>
              <Proto>Explicit Provenance</Proto>
            </div>
            <p className="small soft">
              Every value is traced to its origin (patient reported, document extracted, or missing).
            </p>
            <div className="scroll">
              <table className="mt" style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ textAlign: "left", borderBottom: "2px solid #e5e7eb" }}>
                    <th style={{ padding: "8px 12px" }}>Item</th>
                    <th style={{ padding: "8px 12px" }}>Value</th>
                    <th style={{ padding: "8px 12px" }}>Source Provenance</th>
                  </tr>
                </thead>
                <tbody>
                  {findingsList.map((r) => (
                    <tr
                      key={r.key}
                      className={r.is_missing ? "missrow" : ""}
                      style={{ borderBottom: "1px solid #f3f4f6" }}
                    >
                      <td style={{ padding: "8px 12px" }}>
                        <b>{r.label}</b>
                      </td>
                      <td style={{ padding: "8px 12px" }}>
                        {r.is_missing ? (
                          <Tag kind="warn">Not provided / unknown</Tag>
                        ) : (
                          <b>{r.value}</b>
                        )}
                      </td>
                      <td style={{ padding: "8px 12px" }}>
                        <Source s={r.source} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Missing-Information Checklist (from backend detect_missing) */}
          <div className="card">
            <div className="row">
              <h2>Missing-information checklist</h2>
              <span className="small soft">
                {factors.required_fields_answered || `${6 - missingFields.length}/6 complete`}
              </span>
            </div>
            <p className="small soft">
              Missing information ≠ negative answer. Blanks are treated as unknown, never assumed negative.
            </p>
            <div className="check" style={{ margin: "1rem 0" }}>
              {missingFields.map((f) => (
                <div
                  key={f.field}
                  style={{
                    display: "flex",
                    alignItems: "flex-start",
                    gap: "8px",
                    padding: "8px 12px",
                    background: "#fef3c7",
                    borderRadius: "6px",
                    marginBottom: "6px",
                  }}
                >
                  <Icon n="alert" size={16} />
                  <div>
                    <span style={{ fontWeight: "600", color: "#92400e" }}>
                      {f.label || f.field}: {f.status || "Not provided / unknown"}
                    </span>
                    <p className="small soft" style={{ margin: "2px 0 0 0", color: "#b45309" }}>
                      {f.reason}
                    </p>
                  </div>
                </div>
              ))}
              {missingFields.length === 0 && (
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    padding: "10px 14px",
                    background: "#ecfdf5",
                    borderRadius: "6px",
                    color: "#065f46",
                  }}
                >
                  <Icon n="check" size={16} />
                  <span>All required clinical intake fields have been recorded.</span>
                </div>
              )}
            </div>
          </div>

          {/* Uploaded Documents */}
          <div className="card">
            <h2>Uploaded documents</h2>
            {!c?.docs || c.docs.length === 0 ? (
              <p className="soft mt">No documents were uploaded for this case.</p>
            ) : (
              c.docs.map((d) => (
                <div className="li" key={d.id}>
                  <div>
                    <b>{d.type || "Prescription"}</b>
                    <p className="small soft">{d.file} • Unverified extraction</p>
                  </div>
                  <Source s="document_extracted_unverified" />
                </div>
              ))
            )}
            <button className="btn out sm mt" onClick={() => go("documents")}>
              Manage documents
            </button>
          </div>
        </div>

        {/* Sidebar: Deterministic Completeness & Notes */}
        <div className="rvside">
          <div className="card center">
            <h2>Case completeness</h2>
            <div style={{ margin: "1rem auto" }}>
              <Ring value={scoreValue} size={140} label="Completeness" />
            </div>
            <Tag kind={scoreValue >= 80 ? "ok" : scoreValue >= 50 ? "warn" : "bad"}>
              {readinessData?.label || "Awaiting Review"}
            </Tag>
            <p className="small soft" style={{ marginTop: "0.75rem" }}>
              {readinessData?.disclaimer ||
                "This score reflects case data completeness only. It is NOT a measure of diagnostic accuracy or patient health."}
            </p>
          </div>

          <div className="card">
            <h3>Completeness factors</h3>
            <table className="mt calc" style={{ width: "100%" }}>
              <tbody>
                <tr>
                  <td>
                    <b>Required fields</b>
                    <p className="small soft">Core clinical checklist</p>
                  </td>
                  <td className="end small">
                    <b>{factors.required_fields_answered || "0/6"}</b>
                  </td>
                </tr>
                <tr>
                  <td>
                    <b>Critical missing</b>
                    <p className="small soft">Allergies, meds, acuity</p>
                  </td>
                  <td className="end small">
                    <b>{Math.round((factors.critical_missing_score ?? 1) * 100)}%</b>
                  </td>
                </tr>
                <tr>
                  <td>
                    <b>Information discrepancies</b>
                    <p className="small soft">Patient vs document conflicts</p>
                  </td>
                  <td className="end small">
                    <b>{factors.open_conflicts ?? 0} open</b>
                  </td>
                </tr>
                <tr>
                  <td>
                    <b>Review flags</b>
                    <p className="small soft">Awaiting clinician decision</p>
                  </td>
                  <td className="end small">
                    <b>{factors.open_flags ?? 0} open</b>
                  </td>
                </tr>
                <tr style={{ borderTop: "2px solid #e5e7eb" }}>
                  <td>
                    <b>Overall score</b>
                  </td>
                  <td className="end">
                    <b>{scoreValue} / 100</b>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <div className="card">
            <div className="row">
              <h3>Clinician review notes</h3>
              {isFinalized && <Tag kind="ver">Review finalized</Tag>}
            </div>
            <label className="small soft" htmlFor="notes">
              Add observations, instructions, or corrections
            </label>
            <textarea
              id="notes"
              rows="4"
              value={notesText}
              onChange={(e) => setNotesText(e.target.value)}
              disabled={isFinalized}
              placeholder="Add clinician notes for this case"
            />
            {!isFinalized ? (
              <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 8 }}>
                <button
                  className="btn out wide sm"
                  disabled={savingNotes}
                  onClick={handleSaveNotes}
                >
                  {savingNotes ? "Saving notes..." : "Save notes"}
                </button>
                <button
                  className="btn primary wide"
                  disabled={missingFields.length > 0 || finalizing}
                  onClick={handleFinalize}
                >
                  {finalizing ? "Finalizing review..." : "Finalize case"}
                </button>
              </div>
            ) : (
              <div style={{ marginTop: 10, padding: "8px 12px", background: "#f0fdf4", borderRadius: 8, border: "1px solid #bbf7d0" }}>
                <span className="small" style={{ color: "#166534" }}>
                  <b>Case finalized & locked.</b>
                  {finalizedInfo?.reviewed_at && (
                    <span className="soft"> Reviewed {new Date(finalizedInfo.reviewed_at).toLocaleDateString()}</span>
                  )}
                </span>
              </div>
            )}
            {missingFields.length > 0 && !isFinalized && (
              <p className="small soft center" style={{ color: "#b45309", marginTop: 8 }}>
                Complete or verify missing intake fields before final handoff.
              </p>
            )}
            <p className="small soft center" style={{ marginTop: "8px" }}>
              The doctor remains responsible for all clinical decisions.
            </p>
          </div>
        </div>
      </div>
    </>
  );
}
