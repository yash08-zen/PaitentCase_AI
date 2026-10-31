import { useState, useEffect, useCallback, useRef } from "react";
import { useStore } from "../state/store";
import apiClient from "../api/client";
import { Icon, Proto, Spinner } from "./ui";
import { fmtT } from "../utils/i18n";

/**
 * Doctor-only AI Insights tab.
 * "The LLM proposes. Code verifies. The doctor decides."
 * Every AI item carries an "AI-generated, unverified" badge, its citations and
 * Accept / Edit / Reject controls. Rule-based outputs (labs, trends, scores,
 * red flags, reconciliation) are labelled as code-computed.
 */

const ACTIVE_JOB = ["pending", "running"];
const POLL_MS = 1500;

export function summaryToText(content, t) {
  const sections = (content && content.sections) || [];
  return sections.map((s) => `${t(`summary_${s.section}`).toUpperCase()}:\n${s.text}`).join("\n\n");
}

function editableText(item, t) {
  const c = item.content || {};
  switch (item.type) {
    case "case_summary":
      return summaryToText(c, t);
    case "disease_consideration":
      return c.name || "";
    case "treatment_reference":
      return c.summary || "";
    case "trend_interpretation":
      return c.interpretation || "";
    case "questions_to_ask":
      return c.question || "";
    default:
      return JSON.stringify(c, null, 2);
  }
}

/** Render text with cited spans highlighted (case-insensitive, non-overlapping). */
export function highlightSpans(text, spans) {
  if (!text) return [];
  const ranges = [];
  const lower = text.toLowerCase();
  for (const s of spans) {
    if (!s || s.length < 2) continue;
    const i = lower.indexOf(s.toLowerCase());
    if (i >= 0 && !ranges.some(([a, b]) => i < b && i + s.length > a)) ranges.push([i, i + s.length]);
  }
  ranges.sort((x, y) => x[0] - y[0]);
  const parts = [];
  let pos = 0;
  ranges.forEach(([a, b], k) => {
    if (a > pos) parts.push(<span key={`t${k}`}>{text.slice(pos, a)}</span>);
    parts.push(
      <mark key={`m${k}`} style={{ background: "#fde68a", padding: "0 1px" }}>
        {text.slice(a, b)}
      </mark>
    );
    pos = b;
  });
  if (pos < text.length) parts.push(<span key="end">{text.slice(pos)}</span>);
  return parts;
}

function StatusBadge({ item, t }) {
  if (item.status === "accepted") return <span className="tag t-ver">{t("statusAccepted")}</span>;
  if (item.status === "edited") return <span className="tag t-ver">{t("statusEdited")}</span>;
  if (item.status === "rejected") return <span className="tag t-bad">{t("statusRejected")}</span>;
  return (
    <span className="tag t-warn" style={{ fontWeight: 600 }}>
      {t("aiGeneratedUnverified")}
    </span>
  );
}

/** One AI item with badge, model line and Accept / Edit / Reject. */
function AIItem({ item, t, locked, busy, onDecide, onAccepted, children }) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState("");
  const decided = item.status !== "pending";
  const shown = item.doctor_edits && item.doctor_edits.text;

  return (
    <div
      className="ai-item"
      data-testid={`ai-item-${item.id}`}
      style={{
        background: "#ffffff",
        border: `1px solid ${item.status === "rejected" ? "#fca5a5" : decided ? "#86efac" : "#ddd6fe"}`,
        borderRadius: 8,
        padding: "10px 12px",
        opacity: item.status === "rejected" ? 0.65 : 1,
      }}
    >
      <div className="row" style={{ alignItems: "center", gap: 8, flexWrap: "wrap" }}>
        <StatusBadge item={item} t={t} />
        {item.model_name && (
          <span className="small soft">
            {fmtT(t("modelLine"), { model: item.model_name, version: item.prompt_version || "-" })}
          </span>
        )}
        <div style={{ display: "flex", gap: 6, marginLeft: "auto" }}>
          {editing ? (
            <>
              <button
                className="btn primary sm"
                disabled={busy || !text.trim()}
                onClick={async () => {
                  await onDecide(item.id, "edited", { text });
                  setEditing(false);
                }}
              >
                {t("saveEdit")}
              </button>
              <button className="btn out sm" onClick={() => setEditing(false)}>
                {t("cancel")}
              </button>
            </>
          ) : (
            <>
              <button
                className="btn primary sm"
                disabled={locked || busy}
                aria-label={`${t("accept")} ${item.id}`}
                onClick={async () => {
                  await onDecide(item.id, "accepted");
                  if (onAccepted) onAccepted(item);
                }}
              >
                {t("accept")}
              </button>
              <button
                className="btn out sm"
                disabled={locked || busy}
                onClick={() => {
                  setText(shown || editableText(item, t));
                  setEditing(true);
                }}
              >
                {t("edit")}
              </button>
              <button className="btn out sm" disabled={locked || busy} onClick={() => onDecide(item.id, "rejected")}>
                {t("reject")}
              </button>
            </>
          )}
        </div>
      </div>
      {editing ? (
        <div style={{ marginTop: 8 }}>
          <p className="small soft" style={{ margin: "0 0 4px" }}>
            {t("editHint")}
          </p>
          <textarea
            aria-label={t("edit")}
            style={{ width: "100%", minHeight: 110, fontSize: "0.9rem", padding: 8 }}
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
        </div>
      ) : (
        <div style={{ marginTop: 8 }}>
          {shown ? <p style={{ whiteSpace: "pre-wrap", margin: 0 }}>{shown}</p> : children}
        </div>
      )}
    </div>
  );
}

function Evidence({ items, title, t }) {
  if (!items || items.length === 0) return null;
  return (
    <div style={{ marginTop: 6 }}>
      <div className="small" style={{ fontWeight: 600 }}>
        {title}
      </div>
      <ul style={{ margin: "2px 0 0 18px", padding: 0 }}>
        {items.map((f, i) => (
          <li key={i} className="small">
            {f.finding}{" "}
            <span className="soft">
              — {t("evidenceSource")}: <code>{f.evidence_ref}</code>
              {f.quote ? <> “{f.quote}”</> : null}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Section({ title, badge, children }) {
  return (
    <div className="card">
      <div className="row" style={{ marginBottom: 12 }}>
        <h2 style={{ fontSize: "1.1rem", margin: 0 }}>{title}</h2>
        {badge && <Proto>{badge}</Proto>}
      </div>
      {children}
    </div>
  );
}

const fmtNum = (v) => (v === null || v === undefined ? "–" : Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 }));

export default function AIClinicalInsights({ encounterId, isFinalized, onAcceptSummary, initialData = null }) {
  const { t, notify, language: lang = "en" } = useStore();
  const [data, setData] = useState(initialData);
  const [loading, setLoading] = useState(!initialData);
  const [error, setError] = useState(null);
  const [busyId, setBusyId] = useState(null);
  const [starting, setStarting] = useState(false);
  const [summaryLang, setSummaryLang] = useState("en");
  const [selectedDocId, setSelectedDocId] = useState(null);
  const [scanUrl, setScanUrl] = useState(null);
  const pollRef = useRef(null);

  const fetchData = useCallback(async () => {
    if (!encounterId) return null;
    setError(null);
    try {
      const res = await apiClient.getAIAnalysis(encounterId);
      setData(res);
      return res;
    } catch (err) {
      setError(err.message || t("errorLoadingCase"));
      return null;
    } finally {
      setLoading(false);
    }
  }, [encounterId, t]);

  useEffect(() => {
    if (!initialData) fetchData();
    return () => clearTimeout(pollRef.current);
  }, [fetchData, initialData]);

  // Poll while the background job is pending/running
  useEffect(() => {
    clearTimeout(pollRef.current);
    if (data && ACTIVE_JOB.includes(data.job_status)) {
      pollRef.current = setTimeout(fetchData, POLL_MS);
    }
    return () => clearTimeout(pollRef.current);
  }, [data, fetchData]);

  // Load the scan for the selected document (authenticated blob)
  useEffect(() => {
    let url = null;
    let cancelled = false;
    setScanUrl(null);
    const doc = (data?.document_timeline || []).find((d) => d.id === selectedDocId);
    if (doc && (doc.mime_type || "").startsWith("image/")) {
      apiClient
        .getDocumentFileBlob(doc.id)
        .then((blob) => {
          if (cancelled) return;
          url = URL.createObjectURL(blob);
          setScanUrl(url);
        })
        .catch(() => setScanUrl(null));
    }
    return () => {
      cancelled = true;
      if (url) URL.revokeObjectURL(url);
    };
  }, [selectedDocId, data?.document_timeline]);

  const locked = Boolean(isFinalized || data?.is_case_locked);
  const llm = data?.llm_status || {};
  const jobStatus = data?.job_status || "none";
  const running = starting || ACTIVE_JOB.includes(jobStatus);

  const handleRun = async () => {
    setStarting(true);
    try {
      await apiClient.runAIAnalysis(encounterId, { summaryLanguage: summaryLang });
      notify(t("analysisStarted"));
      await fetchData();
    } catch (err) {
      notify(err.message || t("errorOccurred"), "error");
    } finally {
      setStarting(false);
    }
  };

  const handleDecision = async (insightId, decision, edits = null) => {
    if (locked) {
      notify(t("caseLockedNotice"), "error");
      return;
    }
    setBusyId(insightId);
    try {
      await apiClient.decideAIInsight(insightId, { decision, doctor_edits: edits });
      notify(t("decisionSaved"));
      await fetchData();
    } catch (err) {
      notify(err.message || t("errorOccurred"), "error");
    } finally {
      setBusyId(null);
    }
  };

  if (!encounterId) {
    return (
      <div className="card" style={{ padding: 24, textAlign: "center" }}>
        <p className="soft">{t("encounterMissing")}</p>
      </div>
    );
  }
  if (loading && !data) {
    return (
      <div style={{ padding: "40px 0", textAlign: "center" }}>
        <Spinner text={t("loading")} />
      </div>
    );
  }
  if (error && !data) {
    return (
      <div className="card" style={{ padding: 24, textAlign: "center" }}>
        <p style={{ color: "#b91c1c", marginBottom: 12 }}>{error}</p>
        <button className="btn primary sm" onClick={fetchData}>
          {t("retry")}
        </button>
      </div>
    );
  }

  const itemProps = { t, locked, onDecide: handleDecision };
  const urgency = data?.overall_urgency || "ROUTINE";
  const docs = data?.document_timeline || [];
  const selectedDoc = docs.find((d) => d.id === selectedDocId);
  const entitiesFor = (docId) => (data?.extracted_entities || []).filter((e) => e.document_id === docId);
  const modeLabel = { hosted: t("aiModeHosted"), local: t("aiModeLocal"), mock: t("aiModeMock") }[llm.active_mode || data?.provider_mode] || "-";
  const removedCount = (data?.job?.notes?.validation || []).length;
  const summary = data?.case_summary;
  const summaryLangs = llm.summary_languages || ["en"];

  let jobLine = t("jobNone");
  if (jobStatus === "pending") jobLine = t("jobQueued");
  else if (jobStatus === "running") jobLine = fmtT(t("jobRunning"), { pct: Math.round((data?.job_progress || 0) * 100) });
  else if (jobStatus === "failed") jobLine = fmtT(t("jobFailed"), { error: data?.job?.error || "" });
  else if (jobStatus === "unavailable") jobLine = t("jobUnavailable");
  else if (jobStatus === "completed")
    jobLine = fmtT(t("jobCompleted"), {
      time: data?.job?.finished_at ? new Date(data.job.finished_at).toLocaleString(lang === "en" ? "en-IN" : `${lang}-IN`) : "",
    });

  return (
    <div className="ai-insights-container" style={{ display: "flex", flexDirection: "column", gap: 18 }}>
      {/* Header: notice, provider indicator, run controls, job state */}
      <div className="card" style={{ borderLeft: "4px solid #f59e0b" }}>
        <div className="row" style={{ alignItems: "flex-start", gap: 12, flexWrap: "wrap" }}>
          <div style={{ flex: 1, minWidth: 260 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6, flexWrap: "wrap" }}>
              <span className="tag t-warn" style={{ fontWeight: 600 }}>
                {t("aiGeneratedUnverified")}
              </span>
              <span className="tag t-sys" data-testid="ai-processing-indicator">
                {fmtT(t("aiProcessing"), { mode: modeLabel })}
              </span>
              {locked && (
                <span className="tag t-ver" style={{ fontWeight: 600 }}>
                  <Icon n="check" size={12} /> {t("caseLockedNotice").split(".")[0]}
                </span>
              )}
            </div>
            <p className="small soft" style={{ margin: 0 }}>
              {t("aiNoticeText")}
            </p>
            {llm.consent_statement && llm.active_mode === "hosted" && (
              <p className="small" style={{ margin: "4px 0 0", color: "#92400e" }}>
                {llm.consent_statement}
              </p>
            )}
            <p className="small" style={{ margin: "6px 0 0" }} aria-live="polite">
              {running && <Spinner size={12} />} {jobLine}
            </p>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <label className="small" htmlFor="ai-summary-lang">
              {t("summaryLanguage")}
            </label>
            <select
              id="ai-summary-lang"
              value={summaryLang}
              disabled={running || locked}
              onChange={(e) => setSummaryLang(e.target.value)}
            >
              {["en", "hi", "mr"].map((code) => (
                <option key={code} value={code} disabled={!summaryLangs.includes(code)}>
                  {{ en: "English", hi: "हिन्दी", mr: "मराठी" }[code]}
                </option>
              ))}
            </select>
            <button className="btn primary sm" disabled={running || locked} onClick={handleRun}>
              <Icon n={running ? "reset" : "clip"} size={14} /> {running ? t("runningAnalysis") : t("runAIAnalysis")}
            </button>
          </div>
        </div>
        {llm.available === false && (
          <div className="small" role="status" style={{ marginTop: 10, padding: 8, background: "#fef2f2", color: "#991b1b", borderRadius: 6 }}>
            {t("aiUnavailable")}
          </div>
        )}
        {llm.available !== false && llm.capability === "reduced" && (
          <div className="small" role="status" style={{ marginTop: 10, padding: 8, background: "#fffbeb", color: "#92400e", borderRadius: 6 }}>
            {t("aiReduced")}
          </div>
        )}
        {removedCount > 0 && (
          <p className="small soft" style={{ margin: "8px 0 0" }}>
            {fmtT(t("validatorRemoved"), { n: removedCount })}
          </p>
        )}
      </div>

      {/* Urgency banner (rule-based) */}
      <div
        className="card"
        role={urgency === "ROUTINE" ? undefined : "alert"}
        style={{
          background: urgency === "EMERGENCY" ? "#fee2e2" : urgency === "URGENT" ? "#ffedd5" : "#f1f5f9",
          border: `1px solid ${urgency === "EMERGENCY" ? "#ef4444" : urgency === "URGENT" ? "#f97316" : "#cbd5e1"}`,
        }}
      >
        <div className="row" style={{ alignItems: "center" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span
              style={{
                background: urgency === "EMERGENCY" ? "#dc2626" : urgency === "URGENT" ? "#ea580c" : "#475569",
                color: "#ffffff",
                padding: "3px 10px",
                borderRadius: 4,
                fontWeight: 700,
                fontSize: "0.85rem",
              }}
            >
              {urgency === "EMERGENCY" ? t("urgencyEmergency") : urgency === "URGENT" ? t("urgencyUrgent") : t("urgencyRoutine")}
            </span>
            <span style={{ fontWeight: 600 }}>
              {urgency === "EMERGENCY" ? t("urgencyBannerEmergency") : urgency === "URGENT" ? t("urgencyBannerUrgent") : t("urgencyBannerRoutine")}
            </span>
          </div>
          <span className="small soft">{t("redFlagsRuleBased")}</span>
        </div>
        {(data?.red_flags || []).map((rf) => (
          <div key={rf.id} className="small" style={{ display: "flex", gap: 8, marginTop: 6, color: "#991b1b" }}>
            <Icon n="alert" size={14} /> <b>{rf.description}</b>
          </div>
        ))}
        {(data?.document_quality || []).length > 0 && (
          <div style={{ marginTop: 10 }}>
            <div className="small" style={{ fontWeight: 600 }}>
              {t("docQualityTitle")}
            </div>
            {data.document_quality.map((q) => (
              <div key={q.id} className="small soft">
                • {q.description}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Timeline + original scan beside extracted fields */}
      <Section title={t("scanAndFields")} badge={t("timeline")}>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
          {docs.map((d) => (
            <button
              key={d.id}
              className={`btn sm ${selectedDocId === d.id ? "primary" : "out"}`}
              onClick={() => setSelectedDocId(d.id)}
            >
              {d.document_date || t("undated")} · {d.document_type} · {d.filename}
            </button>
          ))}
        </div>
        {!selectedDoc ? (
          <p className="small soft">{t("selectDocument")}</p>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 14 }}>
            <div style={{ border: "1px solid #e2e8f0", borderRadius: 8, padding: 8, minHeight: 160 }}>
              {scanUrl ? (
                <img src={scanUrl} alt={selectedDoc.filename} style={{ maxWidth: "100%" }} />
              ) : (
                <p className="small soft">{t("noScanPreview")}</p>
              )}
            </div>
            <div>
              {selectedDoc.read_from_handwriting && (
                <div className="tag t-warn" style={{ marginBottom: 6 }}>
                  {t("readFromHandwriting")}
                </div>
              )}
              <div className="small" style={{ fontWeight: 600 }}>
                {t("extractedTextHighlighted")}
              </div>
              <pre style={{ whiteSpace: "pre-wrap", fontSize: "0.85rem", background: "#f8fafc", padding: 8, borderRadius: 6 }}>
                {highlightSpans(
                  selectedDoc.extracted_text,
                  entitiesFor(selectedDoc.id).filter((e) => e.grounded).map((e) => e.source_span)
                )}
              </pre>
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                {entitiesFor(selectedDoc.id).map((e) => (
                  <div key={e.id} className="small">
                    <b>{e.type}</b>: {e.raw_text}{" "}
                    <span className={`tag ${e.grounded ? "t-ver" : "t-bad"}`} style={{ fontSize: "0.7rem" }}>
                      {e.review_status === "read_from_handwriting_verify"
                        ? t("readFromHandwriting")
                        : e.grounded
                        ? t("grounded")
                        : t("notGrounded")}
                    </span>
                  </div>
                ))}
                {(data?.extraction_disagreements || [])
                  .filter((e) => e.document_id === selectedDoc.id)
                  .map((e) => (
                    <div key={e.id} className="small" style={{ color: "#b45309" }}>
                      ⚠ {t("regexDisagreement")}: {e.raw_text} ({e.value?.found_by})
                    </div>
                  ))}
              </div>
            </div>
          </div>
        )}
      </Section>

      {/* Documented vs possible diagnoses */}
      <Section title={t("possibleDiagnoses")}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 16 }}>
          <div>
            <div className="tag t-ver" style={{ fontWeight: 600 }}>
              {t("documentedDiagnoses")}
            </div>
            <p className="small soft" style={{ margin: "4px 0 8px" }}>
              {t("documentedDiagnosesHint")}
            </p>
            {(data?.documented_diagnoses || []).filter((d) => d.grounded).length === 0 ? (
              <p className="small soft">{t("noDocumentedDx")}</p>
            ) : (
              data.documented_diagnoses
                .filter((d) => d.grounded)
                .map((d) => (
                  <div key={d.id} className="small" style={{ padding: "6px 8px", border: "1px solid #bbf7d0", borderRadius: 6, marginBottom: 6 }}>
                    <b>{d.raw_text}</b> <span className="soft">— “{d.source_span}” (doc {d.document_id})</span>
                  </div>
                ))
            )}
          </div>
          <div>
            <div className="tag" style={{ background: "#ede9fe", color: "#6d28d9", border: "1px dashed #8b5cf6", fontWeight: 600 }}>
              {t("possibleDiagnoses")}
            </div>
            <p className="small soft" style={{ margin: "4px 0 8px" }}>
              {t("possibleDiagnosesHint")}
            </p>
            {(data?.possible_diagnoses || []).length === 0 ? (
              <p className="small soft">{t("noPossibleDx")}</p>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {data.possible_diagnoses.map((dx) => {
                  const c = dx.content || {};
                  return (
                    <AIItem key={dx.id} item={dx} busy={busyId === dx.id} {...itemProps}>
                      <div style={{ fontWeight: 600, color: "#4c1d95" }}>
                        {c.name}{" "}
                        <span className="tag t-sys" style={{ fontSize: "0.7rem" }}>
                          {t(`likelihood_${(c.likelihood || "possible").replace(/ /g, "_")}`)}
                        </span>
                      </div>
                      <Evidence items={c.supporting_findings} title={t("supportingFindings")} t={t} />
                      <Evidence items={c.findings_against} title={t("findingsAgainst")} t={t} />
                      {(c.suggested_questions_or_tests || []).length > 0 && (
                        <div className="small" style={{ marginTop: 6 }}>
                          <b>{t("suggestedChecks")}:</b> {c.suggested_questions_or_tests.join("; ")}
                        </div>
                      )}
                    </AIItem>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </Section>

      {/* Labs and trends (code-computed) */}
      <Section title={t("abnormalLabs")}>
        {(data?.abnormal_labs || []).length === 0 ? (
          <p className="small soft">{t("noAbnormalLabs")}</p>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: 10 }}>
            {data.abnormal_labs.map((lab) => {
              const crit = (lab.flag || "").startsWith("critical");
              const noRange = lab.flag === "range_not_available";
              return (
                <div
                  key={lab.id}
                  style={{
                    background: crit ? "#fee2e2" : noRange ? "#f8fafc" : "#fef3c7",
                    border: `1px solid ${crit ? "#ef4444" : noRange ? "#cbd5e1" : "#f59e0b"}`,
                    padding: "8px 12px",
                    borderRadius: 6,
                  }}
                >
                  <div className="row">
                    <b>{lab.test_name}</b>
                    <span className="tag t-sys" style={{ fontSize: "0.7rem" }}>
                      {noRange ? t("rangeNotAvailable") : lab.flag.replace("_", " ").toUpperCase()}
                    </span>
                  </div>
                  <div style={{ fontSize: "1.1rem", fontWeight: 700, margin: "4px 0" }}>
                    {fmtNum(lab.value)} <span style={{ fontSize: "0.8rem", fontWeight: 400 }}>{lab.unit}</span>
                  </div>
                  <div className="small soft">
                    {noRange ? t("rangeNotAvailable") : `${t("printedRange")}: ${fmtNum(lab.ref_low)} – ${fmtNum(lab.ref_high)}`}
                    {lab.test_date ? ` · ${lab.test_date}` : ""}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        <h3 style={{ fontSize: "0.95rem", margin: "16px 0 6px" }}>{t("computedTrends")}</h3>
        {(data?.computed_trends || []).length === 0 ? (
          <p className="small soft">{t("noTrends")}</p>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem" }}>
              <thead>
                <tr style={{ background: "#f1f5f9", textAlign: "left" }}>
                  {["colTest", "colPrevious", "colLatest", "colChange", "colSpan", "colRule"].map((k) => (
                    <th key={k} style={{ padding: "6px 8px" }}>
                      {t(k)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.computed_trends.map((tr) => (
                  <tr key={tr.id} style={{ borderBottom: "1px solid #e2e8f0" }}>
                    <td style={{ padding: "6px 8px", fontWeight: 600 }}>{tr.test_name}</td>
                    <td style={{ padding: "6px 8px" }}>{fmtNum(tr.previous_value)} {tr.unit}</td>
                    <td style={{ padding: "6px 8px" }}>{fmtNum(tr.current_value)} {tr.unit}</td>
                    <td style={{ padding: "6px 8px" }}>
                      {tr.delta > 0 ? "+" : ""}
                      {fmtNum(tr.delta)} ({tr.percent_change > 0 ? "+" : ""}
                      {fmtNum(tr.percent_change)}%){" "}
                      {tr.direction === "rising" ? t("dirRising") : tr.direction === "falling" ? t("dirFalling") : t("dirStable")}
                    </td>
                    <td style={{ padding: "6px 8px" }}>
                      {tr.time_span_days == null ? t("spanUnknown") : fmtT(t("daysN"), { n: tr.time_span_days })}
                    </td>
                    <td style={{ padding: "6px 8px" }}>
                      {tr.rule_matched ? <span className="tag t-bad">{tr.clinical_label}</span> : <span className="soft">{t("trendNoRule")}</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {(data?.trend_interpretations || []).length > 0 && (
          <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 8 }}>
            <div className="small" style={{ fontWeight: 600 }}>
              {t("trendInterpretation")}
            </div>
            {data.trend_interpretations.map((it) => (
              <AIItem key={it.id} item={it} busy={busyId === it.id} {...itemProps}>
                <p style={{ margin: 0 }}>{it.content?.interpretation}</p>
                <p className="small soft" style={{ margin: "4px 0 0" }}>
                  {t("colRule")}: {it.evidence?.rule_label}
                </p>
              </AIItem>
            ))}
          </div>
        )}
      </Section>

      {/* Risk scores (code-computed) */}
      <Section title={t("riskScores")}>
        <p className="small soft" style={{ marginTop: -6 }}>
          {t("riskScoresHint")}
        </p>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: 12 }}>
          {(data?.risk_scores || []).map((s) => {
            const ok = s.status === "calculated";
            return (
              <div
                key={s.id}
                data-testid={`risk-score-${s.score_name}`}
                style={{ border: `1px solid ${ok ? "#94a3b8" : "#e2e8f0"}`, background: ok ? "#fff" : "#f8fafc", padding: 12, borderRadius: 8 }}
              >
                <div className="row">
                  <b>{s.score_name}</b>
                  <span className={`tag ${ok ? "t-ver" : "t-sys"}`}>{ok ? t("calculated") : t("notCalculable")}</span>
                </div>
                {ok ? (
                  <>
                    <div style={{ fontSize: "1.6rem", fontWeight: 800, margin: "6px 0" }}>{fmtNum(s.score_value)}</div>
                    <p className="small soft" style={{ margin: 0 }}>
                      {s.interpretation}
                    </p>
                  </>
                ) : (
                  <p className="small soft" style={{ margin: "8px 0 0" }}>
                    {fmtT(t("missingInputs"), { list: (s.missing_inputs || []).join(", ") })}
                  </p>
                )}
                <p className="small soft" style={{ margin: "6px 0 0" }}>
                  {fmtT(t("formulaVersion"), { v: s.formula_version })}
                </p>
              </div>
            );
          })}
        </div>
      </Section>

      {/* Rule conflicts + medication reconciliation (code-computed) */}
      <Section title={t("ruleConflicts")}>
        {(data?.rule_conflicts || []).length === 0 ? (
          <p className="small soft">{t("noRuleConflicts")}</p>
        ) : (
          data.rule_conflicts.map((c) => (
            <div key={c.id} className="small" style={{ marginBottom: 6 }}>
              <span className="tag t-bad" style={{ fontSize: "0.7rem" }}>
                {c.rule_id}
              </span>{" "}
              {c.description}
            </div>
          ))
        )}
        <h3 style={{ fontSize: "0.95rem", margin: "14px 0 6px" }}>{t("medRecon")}</h3>
        {(data?.medication_reconciliation || []).length === 0 ? (
          <p className="small soft">{t("noMedRecon")}</p>
        ) : (
          data.medication_reconciliation.map((r, i) => (
            <div key={i} className="small" style={{ marginBottom: 4 }}>
              <b>{r.drug}</b> — <span className="tag t-warn" style={{ fontSize: "0.7rem" }}>{t(`recon_${r.status}`)}</span>{" "}
              <span className="soft">
                {r.details} ({(r.sources || []).join(", ")})
              </span>
            </div>
          ))
        )}
      </Section>

      {/* Treatment reference */}
      <Section title={t("treatmentReference")}>
        <div className="small" role="note" style={{ padding: 8, background: "#fff7ed", border: "1px solid #fdba74", borderRadius: 6, marginBottom: 10, fontWeight: 600 }}>
          {t("treatmentLabel")}
        </div>
        {(data?.treatment_references || []).length === 0 ? (
          <p className="small soft">{data?.treatment_reference_status || t("treatmentNone")}</p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {data.treatment_references.map((tr) => {
              const c = tr.content || {};
              const cit = c.citation || {};
              return (
                <AIItem key={tr.id} item={tr} busy={busyId === tr.id} {...itemProps}>
                  <div style={{ fontWeight: 700, color: "#15803d" }}>{c.topic}</div>
                  <p style={{ margin: "4px 0" }}>{c.summary}</p>
                  <div className="small">
                    <b>{t("quotedDose")}:</b>{" "}
                    {c.dose_quotation ? <q style={{ fontStyle: "italic" }}>{c.dose_quotation}</q> : <span className="soft">{t("noQuotedDose")}</span>}
                  </div>
                  {(c.patient_conflicts || []).length > 0 && (
                    <div className="small" role="alert" style={{ marginTop: 6, color: "#991b1b", fontWeight: 600 }}>
                      ⚠ {t("patientConflicts")}: {c.patient_conflicts.join(" | ")}
                    </div>
                  )}
                  <div className="small soft" style={{ marginTop: 6 }}>
                    {t("citation")}: {cit.source} · {cit.section} · {cit.version_date}
                    {cit.is_sample && (
                      <span className="tag t-warn" style={{ marginLeft: 6, fontSize: "0.7rem" }}>
                        {t("sampleSourceWarning")}
                      </span>
                    )}
                  </div>
                </AIItem>
              );
            })}
          </div>
        )}
      </Section>

      {/* AI summary + questions to ask */}
      <Section title={t("aiCaseSummary")}>
        {!summary ? (
          <p className="small soft">{t("noSummary")}</p>
        ) : (
          <AIItem
            item={summary}
            busy={busyId === summary.id}
            {...itemProps}
            onAccepted={(it) => onAcceptSummary && onAcceptSummary(summaryToText(it.content, t))}
          >
            {(summary.content?.sections || []).map((s) => (
              <div key={s.section} style={{ marginBottom: 6 }}>
                <b>{t(`summary_${s.section}`)}:</b> {s.text}{" "}
                <span className="small soft">[{(s.evidence_refs || []).join(", ")}]</span>
              </div>
            ))}
          </AIItem>
        )}
        <h3 style={{ fontSize: "0.95rem", margin: "16px 0 6px" }}>{t("questionsToAsk")}</h3>
        {(data?.questions_to_ask || []).length === 0 ? (
          <p className="small soft">{t("noQuestions")}</p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {data.questions_to_ask.map((q) => (
              <AIItem key={q.id} item={q} busy={busyId === q.id} {...itemProps}>
                <div style={{ fontWeight: 600 }}>{q.content?.question}</div>
                <div className="small soft">
                  {q.content?.reason} [{(q.content?.evidence_refs || []).join(", ")}]
                </div>
              </AIItem>
            ))}
          </div>
        )}
      </Section>
    </div>
  );
}
