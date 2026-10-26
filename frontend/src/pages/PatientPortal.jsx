import { useState, useEffect } from "react";
import { useStore } from "../state/store";
import apiClient from "../api/client";
import { Icon, Bar, Tag, Spinner } from "../components/ui";

const LANGUAGES = [
  { code: "en", label: "English", native: "English" },
  { code: "hi", label: "Hindi", native: "हिन्दी" },
  { code: "mr", label: "Marathi", native: "मराठी" },
];

export default function PatientPortal({ go, user }) {
  const { patients, cases, activeId, notify, language, setLanguage, t, LANGUAGES } = useStore();
  const [loading, setLoading] = useState(false);
  const [progressData, setProgressData] = useState(null);
  const [updatingLang, setUpdatingLang] = useState(false);

  const p = patients.find((x) => x.id === activeId) || patients[0];
  const c = cases[p?.id];
  const encounterId = c?.encounterId;

  // Sync language with patient record on initial mount
  useEffect(() => {
    if (p?.language) {
      const match = LANGUAGES.find(
        (l) => (l.name || l.label || "").toLowerCase() === p.language.toLowerCase() || l.code === p.language.toLowerCase()
      );
      if (match && match.code !== language) setLanguage(match.code);
    }
  }, [p?.language, language, setLanguage, LANGUAGES]);

  // Load interview progress
  useEffect(() => {
    if (!encounterId) return;
    let isMounted = true;
    apiClient
      .getInterviewProgress(encounterId)
      .then((prog) => {
        if (isMounted) setProgressData(prog);
      })
      .catch(() => {});
    return () => {
      isMounted = false;
    };
  }, [encounterId]);

  const handleLanguageChange = async (langCode) => {
    setLanguage(langCode);
    const langObj = LANGUAGES.find((l) => l.code === langCode);
    if (!langObj) return;

    if (encounterId) {
      setUpdatingLang(true);
      try {
        await apiClient.setEncounterLanguage(encounterId, langObj.name || langObj.label || langObj.native);
        notify(`${t("prefLang")}: ${langObj.native} (${langObj.name || langObj.code})`);
      } catch {
        // Fallback gracefully
      } finally {
        setUpdatingLang(false);
      }
    }
  };

  const answeredCount = progressData?.answered_questions || 0;
  const totalCount = progressData?.total_questions || 16;
  const progressPercent = Math.round(
    progressData?.progress_percent ?? (totalCount > 0 ? (answeredCount / totalCount) * 100 : 0)
  );

  const docCount = (c?.docs || []).length;

  return (
    <div className="portal animate-fade" role="region" aria-label="Patient Portal">
      {/* Header welcome banner */}
      <div className="head" style={{ marginBottom: "1.2rem" }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
            <span className="tag t-patient" style={{ fontSize: "0.8rem", padding: "0.2rem 0.6rem" }}>
              {t("portal")}
            </span>
            <span className="small soft">Unique ID: <b>{p?.id || "P-New"}</b></span>
            {encounterId && <span className="small soft">&bull; Encounter <b>#{encounterId}</b></span>}
          </div>
          <h1 style={{ margin: "0.4rem 0 0.2rem", fontSize: "1.8rem" }}>
            {p?.name || user?.username || t("patient")}
          </h1>
          <p className="soft" style={{ margin: 0 }}>
            {t("portalSubheading")}
          </p>
        </div>

        {/* Trilingual Switcher */}
        <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: "0.3rem" }}>
          <span className="small soft" style={{ fontWeight: 600 }}>{t("selectLanguage")}:</span>
          <div style={{ display: "flex", gap: "0.3rem" }}>
            {LANGUAGES.map((l) => (
              <button
                key={l.code}
                type="button"
                className={`btn sm ${language === l.code ? "primary" : "out"}`}
                onClick={() => handleLanguageChange(l.code)}
                disabled={updatingLang}
                style={{ padding: "0.25rem 0.55rem", fontSize: "0.78rem" }}
              >
                {l.native}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* 3-Step Guided Journey Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "1rem", marginBottom: "1.5rem" }}>
        {/* Step 1: Registration & Consent */}
        <div className="card" style={{ padding: "1.2rem", borderTop: "4px solid var(--accent)", position: "relative" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.6rem" }}>
            <span className="tag t-ver">
              <Icon n="check" size={12} /> {t("step1Title")}
            </span>
            <span className="small soft">{t("step1Badge")}</span>
          </div>
          <h3 style={{ margin: "0.2rem 0 0.4rem", fontSize: "1.1rem" }}>{t("step1Heading")}</h3>
          <p className="small soft" style={{ marginBottom: "0.8rem" }}>
            {t("step1Desc")}
          </p>
          <div className="small" style={{ background: "#f8faf8", padding: "0.6rem 0.8rem", borderRadius: "8px" }}>
            <div><b>{t("age")}:</b> {p?.age || "—"} &bull; <b>{t("gender")}:</b> {p?.gender || "—"}</div>
            <div><b>{t("chiefComplaint")}:</b> {p?.complaint || c?.answers?.complaint || "Routine case review"}</div>
          </div>
        </div>

        {/* Step 2: Upload Documents */}
        <div className="card" style={{ padding: "1.2rem", borderTop: "4px solid var(--navy)", position: "relative" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.6rem" }}>
            <span className="tag t-doc">
              <Icon n="doc" size={12} /> {t("step2Title")}
            </span>
            <span className="small soft">{docCount} {t("docCountLabel")}</span>
          </div>
          <h3 style={{ margin: "0.2rem 0 0.4rem", fontSize: "1.1rem" }}>{t("step2Heading")}</h3>
          <p className="small soft" style={{ marginBottom: "0.8rem" }}>
            {t("step2Desc")}
          </p>
          <button
            className="btn out wide"
            type="button"
            onClick={() => go("documents")}
            style={{ display: "flex", justifyContent: "center", alignItems: "center", gap: "0.4rem" }}
          >
            <Icon n="doc" size={16} />
            {t("step2Button")} →
          </button>
        </div>

        {/* Step 3: Adaptive Interview */}
        <div className="card" style={{ padding: "1.2rem", borderTop: "4px solid var(--primary, #0c8a5a)", position: "relative" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.6rem" }}>
            <span className="tag t-patient">
              <Icon n="chat" size={12} /> {t("step3Title")}
            </span>
            <span className="small soft">{progressPercent}% complete</span>
          </div>
          <h3 style={{ margin: "0.2rem 0 0.4rem", fontSize: "1.1rem" }}>{t("step3Heading")}</h3>
          <p className="small soft" style={{ marginBottom: "0.6rem" }}>
            {t("step3Desc")}
          </p>
          <div style={{ marginBottom: "0.8rem" }}>
            <Bar value={progressPercent} />
          </div>
          <button
            className="btn primary wide"
            type="button"
            onClick={() => go("interview")}
            style={{ display: "flex", justifyContent: "center", alignItems: "center", gap: "0.4rem" }}
          >
            <Icon n="chat" size={16} />
            {progressPercent >= 100 ? `${t("reviewCase")} →` : progressPercent > 0 ? `${t("resumeInterview")} →` : `${t("startInterview")} →`}
          </button>
        </div>
      </div>

      {/* Handoff Preparation Card */}
      <div className="card" style={{ padding: "1.2rem", background: "#f9fbfa", border: "1px solid var(--line)" }}>
        <div style={{ display: "flex", alignItems: "flex-start", gap: "0.8rem" }}>
          <div style={{ fontSize: "1.8rem" }}>📋</div>
          <div>
            <h4 style={{ margin: "0 0 0.2rem", fontSize: "1rem" }}>What happens next?</h4>
            <p className="small soft" style={{ margin: 0, lineHeight: 1.5 }}>
              Once you finish answering the questions and uploading any documents, PatientCase AI compiles your answers into a structured clinical summary with verified medication provenance. Your consulting physician will review this entire case file during your visit.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
