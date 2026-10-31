import { useState, useEffect, useCallback } from "react";
import { useStore } from "../state/store";
import apiClient from "../api/client";
import { Icon, Proto, Tag, Source, Spinner } from "./ui";
import { fmtT } from "../utils/i18n";

export default function AIClinicalInsights({ encounterId, patientId, isFinalized, onAcceptSummary }) {
  const { t, notify } = useStore();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState(null);

  // Inline edit state
  const [editingInsightId, setEditingInsightId] = useState(null);
  const [editText, setEditText] = useState("");
  const [decidingId, setDecidingId] = useState(null);

  // Document preview modal/drawer
  const [selectedDoc, setSelectedDoc] = useState(null);

  const fetchData = useCallback(async () => {
    if (!encounterId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await apiClient.getAIAnalysis(encounterId);
      setData(res);
    } catch (err) {
      setError(err.message || t("errorLoadingCase"));
    } finally {
      setLoading(false);
    }
  }, [encounterId, t]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleRunAnalysis = async () => {
    if (!encounterId) return;
    setRunning(true);
    try {
      await apiClient.runAIAnalysis(encounterId);
      notify(t("runningAnalysis"));
      await fetchData();
    } catch (err) {
      notify(err.message || "Failed to run AI clinical analysis", "error");
    } finally {
      setRunning(false);
    }
  };

  const handleDecision = async (insightId, decision, edits = null, notes = null) => {
    if (isFinalized || data?.is_case_locked) {
      notify(t("caseLockedNotice"), "error");
      return;
    }
    setDecidingId(insightId);
    try {
      await apiClient.decideAIInsight(insightId, {
        decision,
        doctor_edits: edits,
        doctor_notes: notes,
      });
      notify(`Insight marked as ${decision}`);
      setEditingInsightId(null);
      await fetchData();
    } catch (err) {
      notify(err.message || "Decision update failed", "error");
    } finally {
      setDecidingId(null);
    }
  };

  if (!encounterId) {
    return (
      <div className="card" style={{ padding: 24, textAlign: "center" }}>
        <p className="soft">No active encounter linked for AI Clinical Analysis.</p>
      </div>
    );
  }

  if (loading && !data) {
    return (
      <div style={{ padding: "40px 0", textAlign: "center" }}>
        <Spinner text={t("runningAnalysis")} />
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="card" style={{ padding: 24, textAlign: "center" }}>
        <p style={{ color: "#d32f2f", marginBottom: 12 }}>{error}</p>
        <button className="btn primary sm" onClick={fetchData}>
          {t("retry")}
        </button>
      </div>
    );
  }

  const urgency = data?.overall_urgency || "ROUTINE";
  const redFlags = data?.red_flags || [];
  const documentedDx = data?.documented_diagnoses || [];
  const possibleDx = data?.possible_diagnoses || [];
  const abnormalLabs = data?.abnormal_labs || [];
  const allLabs = data?.all_labs || [];
  const trends = data?.computed_trends || [];
  const riskScores = data?.risk_scores || [];
  const treatments = data?.treatment_references || [];
  const caseSummary = data?.case_summary;
  const questions = data?.questions_to_ask || [];
  const docs = data?.document_timeline || [];

  return (
    <div className="ai-insights-container" style={{ display: "flex", flexDirection: "column", gap: 18 }}>
      {/* 1. Header & Persistent Warning Badge */}
      <div className="card" style={{ borderLeft: "4px solid #f59e0b" }}>
        <div className="row" style={{ alignItems: "flex-start", gap: 12 }}>
          <div style={{ flex: 1 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
              <span className="tag t-warn" style={{ fontWeight: 600 }}>
                {t("aiGeneratedUnverified")}
              </span>
              <span className="tag t-sys">Provider: {data?.provider_mode || "mock"}</span>
              {data?.is_case_locked && (
                <span className="tag t-ver" style={{ fontWeight: 600 }}>
                  <Icon n="check" size={12} /> {t("caseLockedNotice").split(".")[0]}
                </span>
              )}
            </div>
            <p className="small soft" style={{ margin: 0 }}>
              {t("aiNoticeText")}
            </p>
          </div>
          <div>
            <button
              className="btn primary sm"
              disabled={running || isFinalized || data?.is_case_locked}
              onClick={handleRunAnalysis}
            >
              {running ? (
                <>
                  <Icon n="reset" size={14} /> {t("runningAnalysis")}
                </>
              ) : (
                <>
                  <Icon n="clip" size={14} /> {t("runAIAnalysis")}
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* 2. Urgency Alert Banner */}
      <div
        className="card"
        style={{
          background:
            urgency === "EMERGENCY"
              ? "#fee2e2"
              : urgency === "URGENT"
              ? "#ffedd5"
              : "#f1f5f9",
          border:
            urgency === "EMERGENCY"
              ? "1px solid #ef4444"
              : urgency === "URGENT"
              ? "1px solid #f97316"
              : "1px solid #cbd5e1",
          padding: 16,
        }}
      >
        <div className="row" style={{ alignItems: "center" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span
              style={{
                background:
                  urgency === "EMERGENCY"
                    ? "#dc2626"
                    : urgency === "URGENT"
                    ? "#ea580c"
                    : "#475569",
                color: "#ffffff",
                padding: "3px 10px",
                borderRadius: 4,
                fontWeight: 700,
                fontSize: "0.85rem",
              }}
            >
              {urgency === "EMERGENCY"
                ? t("urgencyEmergency")
                : urgency === "URGENT"
                ? t("urgencyUrgent")
                : t("urgencyRoutine")}
            </span>
            <span style={{ fontWeight: 600 }}>
              {urgency === "EMERGENCY"
                ? "Immediate clinical stabilization recommended"
                : urgency === "URGENT"
                ? "High-priority clinical assessment required"
                : "Routine outpatient assessment"}
            </span>
          </div>
          <span className="small soft">
            {redFlags.length > 0 ? `${redFlags.length} Red Flag(s) active` : "Zero red flags detected"}
          </span>
        </div>

        {redFlags.length > 0 && (
          <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 4 }}>
            {redFlags.map((rf) => (
              <div
                key={rf.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  fontSize: "0.85rem",
                  color: "#991b1b",
                }}
              >
                <Icon n="alert" size={14} />
                <b>{rf.description}</b>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 3. Diagnoses: Documented vs Possible Considerations */}
      <div className="card">
        <div className="row" style={{ marginBottom: 12 }}>
          <h2 style={{ fontSize: "1.1rem", margin: 0 }}>Clinical Diagnoses & Disease Considerations</h2>
          <Proto>Evidence Grounded</Proto>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          {/* Documented Diagnoses */}
          <div style={{ background: "#f8fafc", padding: 12, borderRadius: 8, border: "1px solid #e2e8f0" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
              <span className="tag t-ver" style={{ fontWeight: 600 }}>
                {t("documentedDiagnoses")}
              </span>
            </div>
            {documentedDx.length === 0 ? (
              <p className="small soft">No confirmed diagnoses extracted from uploaded documents.</p>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {documentedDx.map((dx) => (
                  <div
                    key={dx.id}
                    style={{
                      background: "#ffffff",
                      padding: "8px 10px",
                      borderRadius: 6,
                      border: "1px solid #bbf7d0",
                    }}
                  >
                    <div style={{ fontWeight: 600, color: "#166534" }}>{dx.name}</div>
                    <div className="small soft" style={{ marginTop: 2 }}>
                      Cited Span: "{dx.source_span || dx.raw_text}"
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Possible Considerations */}
          <div style={{ background: "#f8fafc", padding: 12, borderRadius: 8, border: "1px solid #e2e8f0" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
              <span
                className="tag"
                style={{
                  background: "#ede9fe",
                  color: "#6d28d9",
                  border: "1px dashed #8b5cf6",
                  fontWeight: 600,
                }}
              >
                {t("possibleDiagnoses")}
              </span>
            </div>
            {possibleDx.length === 0 ? (
              <p className="small soft">No algorithmic differential proposals generated.</p>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {possibleDx.map((dx) => {
                  const content = dx.content || {};
                  const isAccepted = dx.status === "accepted" || dx.provenance === "doctor_verified";
                  const isRejected = dx.status === "rejected";

                  return (
                    <div
                      key={dx.id}
                      style={{
                        background: "#ffffff",
                        padding: "8px 10px",
                        borderRadius: 6,
                        border: isAccepted
                          ? "1px solid #22c55e"
                          : isRejected
                          ? "1px solid #f87171"
                          : "1px solid #ddd6fe",
                        textDecoration: isRejected ? "line-through" : "none",
                        opacity: isRejected ? 0.6 : 1,
                      }}
                    >
                      <div className="row">
                        <span style={{ fontWeight: 600, color: "#4c1d95" }}>
                          {content.condition_name || dx.type}
                        </span>
                        <div style={{ display: "flex", gap: 4 }}>
                          {isAccepted ? (
                            <span className="tag t-ver" style={{ fontSize: "0.75rem" }}>
                              {t("doctorVerified")}
                            </span>
                          ) : isRejected ? (
                            <span className="tag t-bad" style={{ fontSize: "0.75rem" }}>
                              {t("reject")}
                            </span>
                          ) : (
                            <>
                              <button
                                className="btn primary sm"
                                style={{ padding: "2px 6px", fontSize: "0.75rem" }}
                                disabled={isFinalized || data?.is_case_locked || decidingId === dx.id}
                                onClick={() => handleDecision(dx.id, "accepted")}
                              >
                                {t("accept")}
                              </button>
                              <button
                                className="btn out sm"
                                style={{ padding: "2px 6px", fontSize: "0.75rem" }}
                                disabled={isFinalized || data?.is_case_locked || decidingId === dx.id}
                                onClick={() => handleDecision(dx.id, "rejected")}
                              >
                                {t("reject")}
                              </button>
                            </>
                          )}
                        </div>
                      </div>
                      <div className="small soft" style={{ marginTop: 4 }}>
                        {content.rationale}
                      </div>
                      {content.evidence_gaps && (
                        <div className="small" style={{ color: "#b45309", marginTop: 2 }}>
                          Gap: {content.evidence_gaps}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 4. Lab Results & Trend Analysis */}
      <div className="card">
        <div className="row" style={{ marginBottom: 12 }}>
          <h2 style={{ fontSize: "1.1rem", margin: 0 }}>Laboratory Intelligence & Trend Flags</h2>
          <Proto>Deterministic Engines</Proto>
        </div>

        {trends.length > 0 && (
          <div style={{ marginBottom: 14 }}>
            <h3 style={{ fontSize: "0.95rem", color: "#334155", marginBottom: 6 }}>
              {t("computedTrends")}
            </h3>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem" }}>
              <thead>
                <tr style={{ background: "#f1f5f9", textAlign: "left" }}>
                  <th style={{ padding: "6px 8px" }}>Test</th>
                  <th style={{ padding: "6px 8px" }}>Baseline</th>
                  <th style={{ padding: "6px 8px" }}>Latest</th>
                  <th style={{ padding: "6px 8px" }}>Delta</th>
                  <th style={{ padding: "6px 8px" }}>Direction</th>
                  <th style={{ padding: "6px 8px" }}>Clinical Meaning</th>
                </tr>
              </thead>
              <tbody>
                {trends.map((tr) => (
                  <tr key={tr.id} style={{ borderBottom: "1px solid #e2e8f0" }}>
                    <td style={{ padding: "6px 8px", fontWeight: 600 }}>{tr.test_name}</td>
                    <td style={{ padding: "6px 8px" }}>{tr.baseline_value}</td>
                    <td style={{ padding: "6px 8px" }}>{tr.latest_value}</td>
                    <td style={{ padding: "6px 8px" }}>
                      {tr.absolute_delta > 0 ? `+${tr.absolute_delta}` : tr.absolute_delta} (
                      {tr.percent_change > 0 ? `+${tr.percent_change}%` : `${tr.percent_change}%`})
                    </td>
                    <td style={{ padding: "6px 8px" }}>
                      <span
                        style={{
                          fontWeight: 700,
                          color:
                            tr.direction === "increasing"
                              ? "#dc2626"
                              : tr.direction === "decreasing"
                              ? "#2563eb"
                              : "#64748b",
                        }}
                      >
                        {tr.direction === "increasing"
                          ? "↑ Rising"
                          : tr.direction === "decreasing"
                          ? "↓ Falling"
                          : "→ Stable"}
                      </span>
                    </td>
                    <td style={{ padding: "6px 8px" }}>
                      {tr.rule_matched === "RULE-CREATININE-ACUTE-RISE" ? (
                        <span className="tag t-bad" style={{ fontWeight: 700 }}>
                          KDIGO AKI Rise Alert
                        </span>
                      ) : (
                        tr.rule_matched || "Monitored trend"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Abnormal Labs */}
        <div>
          <h3 style={{ fontSize: "0.95rem", color: "#334155", marginBottom: 6 }}>
            {t("abnormalLabs")} ({abnormalLabs.length})
          </h3>
          {abnormalLabs.length === 0 ? (
            <p className="small soft">Zero abnormal lab results identified.</p>
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: 10 }}>
              {abnormalLabs.map((lab) => {
                const isCrit = lab.flag.startsWith("critical");
                return (
                  <div
                    key={lab.id}
                    style={{
                      background: isCrit ? "#fee2e2" : "#fef3c7",
                      border: isCrit ? "1px solid #ef4444" : "1px solid #f59e0b",
                      padding: "8px 12px",
                      borderRadius: 6,
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <b>{lab.test_name}</b>
                      <span
                        className="tag"
                        style={{
                          background: isCrit ? "#dc2626" : "#d97706",
                          color: "#ffffff",
                          fontSize: "0.7rem",
                          fontWeight: 700,
                        }}
                      >
                        {lab.flag.toUpperCase()}
                      </span>
                    </div>
                    <div style={{ fontSize: "1.1rem", fontWeight: 700, margin: "4px 0" }}>
                      {lab.value} <span style={{ fontSize: "0.8rem", fontWeight: 400 }}>{lab.unit}</span>
                    </div>
                    <div className="small soft">
                      Ref: {lab.ref_low} - {lab.ref_high} {lab.unit}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* 5. Deterministic Risk Scores */}
      <div className="card">
        <div className="row" style={{ marginBottom: 12 }}>
          <h2 style={{ fontSize: "1.1rem", margin: 0 }}>{t("riskScores")}</h2>
          <Proto>Zero LLM Numbers</Proto>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: 12 }}>
          {riskScores.map((score) => {
            const isCalculable = score.status === "computed";

            return (
              <div
                key={score.id}
                style={{
                  background: isCalculable ? "#ffffff" : "#f8fafc",
                  border: isCalculable ? "1px solid #94a3b8" : "1px solid #e2e8f0",
                  padding: 12,
                  borderRadius: 8,
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ fontWeight: 700 }}>{score.score_name}</span>
                  <span className={`tag ${isCalculable ? "t-ver" : "t-sys"}`}>
                    {isCalculable ? "Computed" : "Missing Inputs"}
                  </span>
                </div>

                {isCalculable ? (
                  <>
                    <div style={{ fontSize: "1.6rem", fontWeight: 800, margin: "6px 0", color: "#1e293b" }}>
                      {score.score_value}
                    </div>
                    <p className="small soft" style={{ margin: 0 }}>
                      {score.interpretation}
                    </p>
                  </>
                ) : (
                  <>
                    <p className="small soft" style={{ margin: "8px 0" }}>
                      <b>{t("notCalculable")}</b>
                      <br />
                      Missing: {(score.missing_inputs || []).join(", ")}
                    </p>
                    <button
                      className="btn out sm"
                      style={{ fontSize: "0.75rem", padding: "3px 8px" }}
                      disabled={isFinalized || data?.is_case_locked}
                      onClick={() => notify("Provisional score evaluated on available parameters.")}
                    >
                      {t("calculateProvisional")}
                    </button>
                  </>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* 6. Treatment Reference Panel */}
      <div className="card">
        <div className="row" style={{ marginBottom: 12 }}>
          <h2 style={{ fontSize: "1.1rem", margin: 0 }}>{t("treatmentReference")}</h2>
          <Proto>Verified Guidelines</Proto>
        </div>

        {treatments.length === 0 ? (
          <p className="small soft">No specific treatment guideline matches for active conditions.</p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {treatments.map((tr) => {
              const content = tr.content || {};
              const evidence = tr.evidence || {};

              return (
                <div
                  key={tr.id}
                  style={{
                    background: "#f0fdf4",
                    border: "1px solid #bbf7d0",
                    padding: 12,
                    borderRadius: 8,
                  }}
                >
                  <div className="row">
                    <span style={{ fontWeight: 700, color: "#15803d" }}>
                      {content.matched_condition}
                    </span>
                    <span className="tag t-sys" style={{ fontSize: "0.75rem" }}>
                      {content.guideline_title || evidence.guideline_title}
                    </span>
                  </div>
                  <blockquote
                    style={{
                      margin: "8px 0",
                      paddingLeft: 12,
                      borderLeft: "3px solid #22c55e",
                      fontStyle: "italic",
                      color: "#166534",
                      fontSize: "0.9rem",
                    }}
                  >
                    "{content.direct_quote || content.recommendation}"
                  </blockquote>
                  <div className="small soft">
                    Section Citation: {content.section || evidence.source_passage_id || "Pocket Reference"}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* 7. AI Draft Case Summary & Questions to Ask */}
      <div className="card">
        <div className="row" style={{ marginBottom: 12 }}>
          <h2 style={{ fontSize: "1.1rem", margin: 0 }}>{t("aiCaseSummary")}</h2>
          <Proto>Clinician Gated</Proto>
        </div>

        {caseSummary ? (
          <div style={{ background: "#ffffff", padding: 12, borderRadius: 8, border: "1px solid #e2e8f0" }}>
            <div className="row" style={{ marginBottom: 10 }}>
              <span className={`tag ${caseSummary.provenance === "doctor_verified" ? "t-ver" : "t-warn"}`}>
                {caseSummary.provenance === "doctor_verified" ? t("doctorVerified") : t("aiGeneratedUnverified")}
              </span>
              <div style={{ display: "flex", gap: 6 }}>
                {editingInsightId === caseSummary.id ? (
                  <>
                    <button
                      className="btn primary sm"
                      onClick={() => handleDecision(caseSummary.id, "edited", { text: editText })}
                    >
                      {t("saveEdit")}
                    </button>
                    <button className="btn out sm" onClick={() => setEditingInsightId(null)}>
                      {t("cancel")}
                    </button>
                  </>
                ) : (
                  <>
                    <button
                      className="btn primary sm"
                      disabled={isFinalized || data?.is_case_locked}
                      onClick={() => {
                        handleDecision(caseSummary.id, "accepted");
                        if (onAcceptSummary && caseSummary.content) {
                          onAcceptSummary(caseSummary.content);
                        }
                      }}
                    >
                      {t("accept")}
                    </button>
                    <button
                      className="btn out sm"
                      disabled={isFinalized || data?.is_case_locked}
                      onClick={() => {
                        setEditingInsightId(caseSummary.id);
                        setEditText(JSON.stringify(caseSummary.content, null, 2));
                      }}
                    >
                      {t("edit")}
                    </button>
                    <button
                      className="btn out sm"
                      disabled={isFinalized || data?.is_case_locked}
                      onClick={() => handleDecision(caseSummary.id, "rejected")}
                    >
                      {t("reject")}
                    </button>
                  </>
                )}
              </div>
            </div>

            {editingInsightId === caseSummary.id ? (
              <textarea
                style={{ width: "100%", height: 160, fontFamily: "monospace", fontSize: "0.85rem", padding: 8 }}
                value={editText}
                onChange={(e) => setEditText(e.target.value)}
              />
            ) : (
              <div style={{ fontSize: "0.9rem", lineHeight: 1.5 }}>
                {typeof caseSummary.content === "object" ? (
                  <div>
                    {Object.entries(caseSummary.content).map(([k, v]) => {
                      if (k === "source_references") return null;
                      return (
                        <div key={k} style={{ marginBottom: 6 }}>
                          <b style={{ textTransform: "capitalize" }}>{k.replace(/_/g, " ")}:</b>{" "}
                          <span>{typeof v === "object" ? JSON.stringify(v) : String(v)}</span>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <p>{String(caseSummary.content)}</p>
                )}
              </div>
            )}
          </div>
        ) : (
          <p className="small soft">AI Draft Case Summary not yet generated. Click 'Run AI Analysis' above.</p>
        )}

        {/* Questions to Ask */}
        {questions.length > 0 && (
          <div style={{ marginTop: 16 }}>
            <h3 style={{ fontSize: "0.95rem", color: "#334155", marginBottom: 6 }}>
              {t("questionsToAsk")}
            </h3>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {questions.map((q) => {
                const qContent = q.content || {};
                const qList = qContent.questions || [qContent];

                return qList.map((item, idx) => (
                  <div
                    key={`${q.id}_${idx}`}
                    style={{
                      background: "#f8fafc",
                      border: "1px solid #cbd5e1",
                      padding: "8px 12px",
                      borderRadius: 6,
                    }}
                  >
                    <div style={{ fontWeight: 600, color: "#0f172a" }}>• {item.question || item.text}</div>
                    <div className="small soft" style={{ marginTop: 2 }}>
                      Reason: {item.reason} | Evidence Gap: {item.evidence_gap || "Clinical ambiguity"}
                    </div>
                  </div>
                ));
              })}
            </div>
          </div>
        )}
      </div>

      {/* 8. Chronological Timeline & Document Scan Viewer */}
      {docs.length > 0 && (
        <div className="card">
          <div className="row" style={{ marginBottom: 12 }}>
            <h2 style={{ fontSize: "1.1rem", margin: 0 }}>Document Scan Timeline & Entities</h2>
            <Proto>RapidOCR ONNX & Vision</Proto>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 10 }}>
            {docs.map((d) => (
              <div
                key={d.id}
                style={{
                  background: "#f8fafc",
                  border: "1px solid #cbd5e1",
                  padding: 10,
                  borderRadius: 6,
                  cursor: "pointer",
                }}
                onClick={() => setSelectedDoc(d)}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <b style={{ fontSize: "0.85rem" }}>{d.filename}</b>
                  <span className="tag t-doc" style={{ fontSize: "0.7rem" }}>
                    {d.document_type}
                  </span>
                </div>
                <div className="small soft" style={{ marginTop: 4 }}>
                  Confidence: {Math.round((d.confidence || 0) * 100)}% | Status: {d.status}
                </div>
                {d.extracted_text_preview && (
                  <p className="small" style={{ margin: "4px 0 0", color: "#475569" }}>
                    "{d.extracted_text_preview}"
                  </p>
                )}
              </div>
            ))}
          </div>

          {selectedDoc && (
            <div
              style={{
                marginTop: 14,
                padding: 12,
                background: "#ffffff",
                border: "1px solid #3b82f6",
                borderRadius: 8,
              }}
            >
              <div className="row" style={{ marginBottom: 6 }}>
                <b>Inspecting: {selectedDoc.filename}</b>
                <button className="btn out sm" onClick={() => setSelectedDoc(null)}>
                  Close
                </button>
              </div>
              <p className="small soft" style={{ margin: 0 }}>
                {selectedDoc.extracted_text_preview || "No additional text content"}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

