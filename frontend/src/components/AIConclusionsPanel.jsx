import { useState, useEffect, useCallback, useRef } from "react";
import { useStore } from "../state/store";
import apiClient from "../api/client";
import { Spinner } from "./ui";
import { ConclusionBody } from "./AIClinicalInsights";
import { fmtT } from "../utils/i18n";

/**
 * Doctor dashboard: the latest automatic AI analysis for each open case.
 * The analysis runs on its own when the patient answers or a document is
 * processed; this panel only displays it. Doctor/admin only (the API returns
 * 403 for other roles and the panel then renders nothing).
 */

const POLL_ANALYZING_MS = 5000;
const POLL_IDLE_MS = 30000;
export const REVIEW_TAB_KEY = "pc_review_tab";

const URGENCY_STYLE = {
  EMERGENCY: { bg: "#fee2e2", border: "#ef4444", tag: "#dc2626" },
  URGENT: { bg: "#ffedd5", border: "#f97316", tag: "#ea580c" },
  ROUTINE: { bg: "#ffffff", border: "#e2e8f0", tag: "#475569" },
};

export function ConclusionCaseCard({ item, t, onOpen, lang = "en" }) {
  const u = URGENCY_STYLE[item.urgency] || URGENCY_STYLE.ROUTINE;
  const ov = item.overview || {};
  const when = item.analyzed_at
    ? new Date(item.analyzed_at).toLocaleString(lang === "en" ? "en-IN" : `${lang}-IN`)
    : null;
  return (
    <div
      data-testid={`conclusion-case-${item.encounter_id}`}
      style={{ background: u.bg, border: `1px solid ${u.border}`, borderRadius: 8, padding: "10px 12px" }}
    >
      <div className="row" style={{ alignItems: "center", gap: 8, flexWrap: "wrap" }}>
        <b>{item.patient_name}</b>
        <span className="tag" style={{ background: u.tag, color: "#fff", fontWeight: 700, fontSize: "0.7rem" }}>
          {item.urgency === "EMERGENCY" ? t("urgencyEmergency") : item.urgency === "URGENT" ? t("urgencyUrgent") : t("urgencyRoutine")}
        </span>
        <span className="tag t-sys" style={{ fontSize: "0.7rem" }}>
          {item.analysis_state === "analyzing" && <Spinner size={10} />} {t(`state_${item.analysis_state}`)}
        </span>
        <button className="btn out sm" style={{ marginLeft: "auto" }} onClick={() => onOpen(item)}>
          {t("openAIInsights")} →
        </button>
      </div>
      <div className="small" style={{ marginTop: 4 }}>
        <b>{t("reasonForVisit")}:</b> {item.reason_for_visit || "—"}
      </div>
      {when && (
        <div className="small soft">
          {fmtT(t("lastUpdate"), { when, trigger: t(`trigger_${item.last_trigger || "manual"}`) })}
        </div>
      )}

      {item.conclusion ? (
        <div style={{ marginTop: 8, background: "#fff", border: "1px dashed #c4b5fd", borderRadius: 6, padding: 8 }}>
          <span className="tag t-warn" style={{ fontWeight: 600, fontSize: "0.7rem" }}>
            {item.conclusion.status === "pending" ? t("aiGeneratedUnverified")
              : item.conclusion.status === "edited" ? t("statusEdited") : t("statusAccepted")}
          </span>
          <div style={{ marginTop: 6 }}>
            {item.conclusion.doctor_edits?.text
              ? <p style={{ margin: 0, whiteSpace: "pre-wrap" }}>{item.conclusion.doctor_edits.text}</p>
              : <ConclusionBody content={item.conclusion.content} t={t} />}
          </div>
        </div>
      ) : (
        <div className="small" style={{ marginTop: 8 }}>
          <div className="soft">
            {item.analysis_state === "analyzing" ? t("state_analyzing")
              : item.analysis_state === "ready" ? t("conclusionMissingRerun") : t("conclusionPending")}
          </div>
          {(ov.red_flags || []).length > 0 || (ov.abnormal_labs || []).length > 0 ? (
            <div style={{ marginTop: 4 }}>
              <b>{t("ruleOverview")}:</b>{" "}
              {(ov.red_flags || []).length > 0 && <span>{t("redFlagsShort")}: {ov.red_flags.join("; ")}. </span>}
              {(ov.abnormal_labs || []).length > 0 && <span>{t("abnormalLabsShort")}: {ov.abnormal_labs.join("; ")}.</span>}
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}

export default function AIConclusionsPanel({ go, initialData = null }) {
  const { patients, setActiveId, t, language } = useStore();
  const [data, setData] = useState(initialData);
  const [forbidden, setForbidden] = useState(false);
  const timer = useRef(null);

  const load = useCallback(async () => {
    try {
      setData(await apiClient.getAIOverview());
    } catch (err) {
      if (err?.status === 403 || /403|forbidden/i.test(err?.message || "")) setForbidden(true);
    }
  }, []);

  useEffect(() => {
    if (!initialData) load();
  }, [load, initialData]);

  useEffect(() => {
    clearTimeout(timer.current);
    if (forbidden || initialData) return undefined;
    const analyzing = (data?.items || []).some((i) => i.analysis_state === "analyzing");
    timer.current = setTimeout(load, analyzing ? POLL_ANALYZING_MS : POLL_IDLE_MS);
    return () => clearTimeout(timer.current);
  }, [data, forbidden, load, initialData]);

  if (forbidden) return null;

  const openCase = (item) => {
    // Never open an unrelated record: only a patient that matches this case
    const local = patients.find((p) => p.backendId === item.patient_id);
    if (!local) return;
    try {
      sessionStorage.setItem(REVIEW_TAB_KEY, "ai_insights");
    } catch {
      // the review page then opens on its default tab
    }
    setActiveId(local.id);
    go("review");
  };

  const items = data?.items || [];
  return (
    <div className="card" style={{ marginBottom: "1rem", borderLeft: "4px solid #8b5cf6" }}>
      <div className="row" style={{ marginBottom: 6 }}>
        <h2 style={{ margin: 0 }}>{t("dashAIConclusions")}</h2>
        <span className="tag t-warn" style={{ fontWeight: 600 }}>{t("aiGeneratedUnverified")}</span>
      </div>
      <p className="small soft" style={{ margin: "0 0 10px" }}>
        {t("dashAIConclusionsHint")} {t("aiNoticeText")}
      </p>
      {!data ? (
        <Spinner text={t("loading")} />
      ) : items.length === 0 ? (
        <p className="small soft">{t("noOpenCases")}</p>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {items.map((item) => (
            <ConclusionCaseCard key={item.encounter_id} item={item} t={t} onOpen={openCase} lang={language} />
          ))}
        </div>
      )}
    </div>
  );
}
