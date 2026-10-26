import { useState, useEffect, useCallback } from "react";
import { useStore } from "../state/store";
import apiClient from "../api/client";
import { Empty, Icon, Proto, Ring, Source, Tag, Spinner } from "../components/ui";
import { fmtT } from "../utils/i18n";

function ConflictCard({ f, onResolve }) {
  const { t } = useStore();
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
            {f.rule_id ? `[${f.rule_id}] ${f.field}` : `${t("discrepancy")}: ${f.field}`}
          </h2>
        </div>
        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          {f.rule_id && <Tag kind="warn">{f.rule_id}</Tag>}
          <Tag kind={isOpen ? "warn" : isResolved ? "ver" : "sys"}>
            {isOpen ? t("verificationRequired") : isResolved ? t("resolved") : t("dismissed")}
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
          <p className="small soft">{t("patientTestimony")}</p>
          <b>"{f.value_a || t("none")}"</b>
        </div>
        <span className="vsmark">vs</span>
        <div className="src doc">
          <Source s={f.source_b || "document_extracted_unverified"} />
          <p className="small soft">{t("documentExtraction")}</p>
          <b>"{f.value_b || t("none")}"</b>
        </div>
      </div>

      {f.resolution_note && (
        <div style={{ marginTop: 10, padding: "8px 12px", background: "#f0f7f0", borderRadius: 8 }}>
          <span className="small">
            <b>{t("clinicianResolution")}</b> {f.resolution_note}
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
              {busy ? t("resolving") : t("verifiedWithPatient")}
            </button>
            <button
              className="btn out sm"
              disabled={busy}
              onClick={() => handleAction("dismissed", "Discrepancy dismissed by clinician after inspection.")}
            >
              {t("dismissDiscrepancy")}
            </button>
          </>
        ) : (
          <button
            className="btn out sm"
            disabled={busy}
            onClick={() => handleAction("open", "Discrepancy reopened for clinical review.")}
          >
            {t("reopenDiscrepancy")}
          </button>
        )}
      </div>
    </div>
  );
}

export default function DoctorReview({ go }) {
  const { patients, cases, activeId, setNotes, finalize, notify, t } = useStore();
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
  const patientId = p?.id;
  const patientBackendId = p?.backendId;

  const loadCaseData = useCallback(async () => {
    if (!patientId) return;
    setLoading(true);
    setError(null);
    setIsFinalized(false);
    setFinalizedInfo(null);
    setNotesText("");
    setSummaryData(null);
    setMissingData(null);
    setReadinessData(null);
    setConflictsData([]);
    try {
      let resolvedEncId = c?.encounterId;
      if (!resolvedEncId && patientBackendId) {
        const encList = await apiClient.get("/api/encounters");
        const match = Array.isArray(encList)
          ? encList.find((e) => e.patient_id === patientBackendId)
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
      setError(err.message || t("loadCaseFailed"));
    } finally {
      setLoading(false);
    }
  }, [patientId, patientBackendId, c?.encounterId, c?.notes, c?.finalized, t]);

  useEffect(() => {
    loadCaseData();
  }, [loadCaseData]);

  const handleResolveConflict = async (conflictId, status, note) => {
    try {
      await apiClient.resolveConflict(conflictId, { status, resolutionNote: note });
      notify(status === "resolved" ? t("discrepancyReconciled") : t("discrepancyUpdated"));
      await loadCaseData();
    } catch (err) {
      notify(err.message || t("discrepancyUpdateFailed"), "error");
    }
  };

  const handleSaveNotes = async () => {
    if (!encounterId) {
      setNotes(p.id, notesText);
      notify(t("notesSavedLocally"));
      return;
    }
    setSavingNotes(true);
    try {
      await apiClient.saveDoctorNotes(encounterId, notesText);
      setNotes(p.id, notesText);
      notify(t("notesSaved"));
    } catch (err) {
      notify(err.message || t("notesSaveFailed"), "error");
    } finally {
      setSavingNotes(false);
    }
  };

  const handleFinalize = async () => {
    if (!encounterId) {
      finalize(p.id);
      setIsFinalized(true);
      notify(t("finalizedLocally"));
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
      notify(t("finalizedOk"));
      await loadCaseData();
    } catch (err) {
      notify(err.message || t("finalizeFailed"), "error");
    } finally {
      setFinalizing(false);
    }
  };

  if (!p) {
    return (
      <Empty
        title={t("noPatientSelected")}
        text={t("choosePatient")}
        action={
          <button className="btn primary" onClick={() => go("patients")}>
            {t("openPatientList")}
          </button>
        }
      />
    );
  }

  if (loading) {
    return (
      <div style={{ padding: "60px 0", textAlign: "center" }}>
        <Spinner text={fmtT(t("loadingCaseFor"), { name: p.name })} />
      </div>
    );
  }

  if (error) {
    return (
      <Empty
        title={t("errorLoadingCase")}
        text={error}
        action={
          <button className="btn primary" onClick={loadCaseData}>
            {t("retry")}
          </button>
        }
      />
    );
  }

  const scoreValue = readinessData?.score != null ? Math.round(readinessData.score * 100) : 0;
  const factors = readinessData?.factors || {};
  const missingFields = missingData?.missing_fields || [];
  const findingsList = summaryData?.structured_findings || [];
  const summaryText = summaryData?.summary_text || t("noSummaryYet");

  return (
    <>
      <div className="head">
        <div>
          <h1>{p.name}</h1>
          <p className="soft">
            {p.age ? `${p.age} ${t("yrs")}` : t("ageNotProvided")} • {p.gender || t("genderNotProvided")} •{" "}
            {p.language || "English"} • {t("encounter")} #{encounterId || p.id} • {t("registeredOn")} {p.registered}
          </p>
        </div>
        <div className="actions">
          <Tag kind={readinessData?.label === "Ready for Review" ? "ok" : "warn"}>
            {readinessData?.label || t("awaitingReview")}
          </Tag>
          {missingFields.length > 0 && (
            <Tag kind="bad">
              {fmtT(t("nMissingFields"), { n: missingFields.length })}
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
                <h2>{fmtT(t("crossSourceDiscrepancies"), { n: conflictsData.filter((x) => x.status === "open").length })}</h2>
                <Proto>{t("discrepancyRules")}</Proto>
              </div>
              <p className="small soft" style={{ margin: "-6px 0 12px" }}>
                {t("discrepancyDesc")}
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
              <h2>{t("caseSummary")}</h2>
              <div className="actions">
                <Source s="system" />
                <Proto>{t("notADiagnosis")}</Proto>
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
              <h2>{t("structuredFindings")}</h2>
              <Proto>{t("explicitProvenance")}</Proto>
            </div>
            <p className="small soft">
              {t("findingsDesc")}
            </p>
            <div className="scroll">
              <table className="mt" style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ textAlign: "left", borderBottom: "2px solid #e5e7eb" }}>
                    <th style={{ padding: "8px 12px" }}>{t("colItem")}</th>
                    <th style={{ padding: "8px 12px" }}>{t("colValue")}</th>
                    <th style={{ padding: "8px 12px" }}>{t("colProvenance")}</th>
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
                          <Tag kind="warn">{t("srcMissing")}</Tag>
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
              <h2>{t("missingChecklist")}</h2>
              <span className="small soft">
                {factors.required_fields_answered || fmtT(t("nOfSixComplete"), { n: Math.max(0, 6 - missingFields.length) })}
              </span>
            </div>
            <p className="small soft">
              {t("missingNotNegative")}
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
                      {f.label || f.field}: {f.status || t("srcMissing")}
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
                  <span>{t("allRequiredRecorded")}</span>
                </div>
              )}
            </div>
          </div>

          {/* Uploaded Documents */}
          <div className="card">
            <h2>{t("uploadedDocuments")}</h2>
            {!c?.docs || c.docs.length === 0 ? (
              <p className="soft mt">{t("noDocsForCase")}</p>
            ) : (
              c.docs.map((d) => (
                <div className="li" key={d.id}>
                  <div>
                    <b>{d.type || t("prescription")}</b>
                    <p className="small soft">{d.file} • {t("unverifiedExtraction")}</p>
                  </div>
                  <Source s="document_extracted_unverified" />
                </div>
              ))
            )}
            <button className="btn out sm mt" onClick={() => go("documents")}>
              {t("manageDocuments")}
            </button>
          </div>
        </div>

        {/* Sidebar: Deterministic Completeness & Notes */}
        <div className="rvside">
          <div className="card center">
            <h2>{t("caseCompleteness")}</h2>
            <div style={{ margin: "1rem auto" }}>
              <Ring value={scoreValue} size={140} label={t("completenessLabel")} />
            </div>
            <Tag kind={scoreValue >= 80 ? "ok" : scoreValue >= 50 ? "warn" : "bad"}>
              {readinessData?.label || t("awaitingReview")}
            </Tag>
            <p className="small soft" style={{ marginTop: "0.75rem" }}>
              {readinessData?.disclaimer || t("scoreDisclaimer")}
            </p>
          </div>

          <div className="card">
            <h3>{t("completenessFactors")}</h3>
            <table className="mt calc" style={{ width: "100%" }}>
              <tbody>
                <tr>
                  <td>
                    <b>{t("requiredFields")}</b>
                    <p className="small soft">{t("coreChecklist")}</p>
                  </td>
                  <td className="end small">
                    <b>{factors.required_fields_answered || "0/6"}</b>
                  </td>
                </tr>
                <tr>
                  <td>
                    <b>{t("criticalMissing")}</b>
                    <p className="small soft">{t("criticalMissingSub")}</p>
                  </td>
                  <td className="end small">
                    <b>{Math.round((factors.critical_missing_score ?? 1) * 100)}%</b>
                  </td>
                </tr>
                <tr>
                  <td>
                    <b>{t("infoDiscrepancies")}</b>
                    <p className="small soft">{t("infoDiscrepanciesSub")}</p>
                  </td>
                  <td className="end small">
                    <b>{factors.open_conflicts ?? 0} {t("open")}</b>
                  </td>
                </tr>
                <tr>
                  <td>
                    <b>{t("reviewFlags")}</b>
                    <p className="small soft">{t("reviewFlagsSub")}</p>
                  </td>
                  <td className="end small">
                    <b>{factors.open_flags ?? 0} {t("open")}</b>
                  </td>
                </tr>
                <tr style={{ borderTop: "2px solid #e5e7eb" }}>
                  <td>
                    <b>{t("overallScore")}</b>
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
              <h3>{t("clinicianNotes")}</h3>
              {isFinalized && <Tag kind="ver">{t("reviewFinalized")}</Tag>}
            </div>
            <label className="small soft" htmlFor="notes">
              {t("notesLabel")}
            </label>
            <textarea
              id="notes"
              rows="4"
              value={notesText}
              onChange={(e) => setNotesText(e.target.value)}
              disabled={isFinalized}
              placeholder={t("notesPlaceholder")}
            />
            {!isFinalized ? (
              <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 8 }}>
                <button
                  className="btn out wide sm"
                  disabled={savingNotes}
                  onClick={handleSaveNotes}
                >
                  {savingNotes ? t("savingNotes") : t("saveNotes")}
                </button>
                <button
                  className="btn primary wide"
                  disabled={missingFields.length > 0 || finalizing}
                  onClick={handleFinalize}
                >
                  {finalizing ? t("finalizing") : t("finalizeCase")}
                </button>
              </div>
            ) : (
              <div style={{ marginTop: 10, padding: "8px 12px", background: "#f0fdf4", borderRadius: 8, border: "1px solid #bbf7d0" }}>
                <span className="small" style={{ color: "#166534" }}>
                  <b>{t("caseLocked")}</b>
                  {finalizedInfo?.reviewed_at && (
                    <span className="soft"> {t("reviewedOn")} {new Date(finalizedInfo.reviewed_at).toLocaleDateString()}</span>
                  )}
                </span>
              </div>
            )}
            {missingFields.length > 0 && !isFinalized && (
              <p className="small soft center" style={{ color: "#b45309", marginTop: 8 }}>
                {t("completeMissingFirst")}
              </p>
            )}
            <p className="small soft center" style={{ marginTop: "8px" }}>
              {t("doctorResponsible")}
            </p>
          </div>
        </div>
      </div>
    </>
  );
}
