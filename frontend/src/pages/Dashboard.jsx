import { useState, useEffect, useCallback } from "react";
import { useStore } from "../state/store";
import { completeness, openFlags, statusOf } from "../utils/engine";
import { Icon, Ring, StatusTag, Proto, Tag } from "../components/ui";
import apiClient from "../api/client";
import { fmtT } from "../utils/i18n";
import AIConclusionsPanel from "../components/AIConclusionsPanel";

const WEEK = [2, 7, 5, 9, 6, 3, 1];

export default function Dashboard({ go, user }) {
  const role = (user?.role || "doctor").toLowerCase();
  const showAIConclusions = role === "doctor" || role === "admin";
  const { patients, cases, setActiveId, t } = useStore();
  const days = t("weekDays").split(",");
  const [liveSummary, setLiveSummary] = useState(null);
  const [liveCases, setLiveCases] = useState(null);
  const [loading, setLoading] = useState(false);

  const fetchDashboardData = useCallback(async () => {
    setLoading(true);
    try {
      const [sum, queue] = await Promise.all([
        apiClient.getDashboardSummary().catch(() => null),
        apiClient.getDashboardCases().catch(() => null),
      ]);
      if (sum) setLiveSummary(sum);
      if (Array.isArray(queue)) setLiveCases(queue);
    } catch {
      // Fallback to store
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDashboardData();
  }, [fetchDashboardData]);

  const rows = patients.map((p) => ({ p, c: cases[p.id] }));
  const done = rows.filter((r) => r.c?.stage === "complete");
  const reviewLocal = rows.filter((r) => r.c?.stage === "complete" && !r.c?.finalized && openFlags(r.c).length);
  const avg = done.length ? Math.round(done.reduce((s, r) => s + completeness(r.c).total, 0) / done.length) : 0;

  const openLocal = (id, page) => {
    setActiveId(id);
    go(page);
  };

  const openBackendCase = (backendEnc) => {
    // Match local patient by backendId or patient_id
    // Never fall back to an unrelated patient: opening the wrong record is worse than not opening one.
    const localMatch = patients.find((p) => p.backendId === backendEnc.patient_id);
    if (!localMatch) return;
    setActiveId(localMatch.id);
    go("review");
  };

  const totalPatientsCount = liveSummary?.total_patients ?? patients.length;
  const completedCount = liveSummary?.completed_cases ?? done.length;
  const reviewCount = liveSummary?.cases_needing_review ?? reviewLocal.length;
  const activeCount = liveSummary?.active_encounters ?? rows.filter((r) => ["interview", "new"].includes(r.c?.stage)).length;

  const stats = [
    [t("statTotal"), totalPatientsCount, t("statTotalSub"), "patients"],
    [t("statComplete"), completedCount, t("statCompleteSub"), "patients"],
    [t("statReview"), reviewCount, t("statReviewSub"), "patients"],
    [t("statProgress"), activeCount, t("statProgressSub"), "patients"],
  ];

  return (
    <>
      <div className="head">
        <div>
          <h1>{t("dashboard")}</h1>
          <p className="soft">{t("dashSubtitle")}</p>
        </div>
        <div className="actions">
          <button className="btn primary" onClick={() => go("register")}>
            <Icon n="plus" />
            {t("register")}
          </button>
          <button className="btn out" onClick={() => go("patients")}>
            {t("viewPatients")}
          </button>
        </div>
      </div>

      <div className="stats">
        {stats.map(([l, v, s, target], i) => (
          <div key={i} className={`card stat ${i === 0 ? "hero" : ""}`}>
            <div className="row">
              <span>{l}</span>
              <button type="button" className="arrow" onClick={() => go(target)} aria-label={l}>
                <Icon n="arrow" size={14} />
              </button>
            </div>
            <b>{v}</b>
            <p className="small">{s}</p>
          </div>
        ))}
      </div>

      {showAIConclusions && <AIConclusionsPanel go={go} />}

      <div className="cols">
        <div className="card">
          <h2>{t("weeklyIntake")}</h2>
          <p className="small soft">{t("weeklyIntakeSub")}</p>
          <div className="bars">
            {WEEK.map((n, i) => (
              <div key={i} className="barcol">
                <div
                  className={`pillbar ${n >= 5 ? "on" : "hatch"}`}
                  style={{ height: 24 + n * 14 }}
                  title={fmtT(t("nPatients"), { n })}
                />
                <span className="small soft">{days[i]}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="card center">
          <h2>{t("avgCompleteness")}</h2>
          <p className="small soft">{t("avgCompletenessSub")}</p>
          <div style={{ margin: "1rem auto" }}>
            <Ring value={avg} label={t("avgCompleteness")} />
          </div>
          <p className="small soft">{t("completenessDisclaimer")}</p>
        </div>
      </div>

      <div className="cols">
        {/* Clinician Review Queue */}
        <div className="card">
          <div className="row">
            <h2>{t("casesRequiringReview")}</h2>
            <Proto>{t("reviewQueue")}</Proto>
          </div>

          {liveCases && liveCases.length > 0 ? (
            liveCases.map((enc) => (
              <div className="li" key={enc.encounter_id}>
                <div>
                  <b>{enc.patient_name}</b>
                  <p className="small soft">
                    {enc.chief_complaint || t("generalIntake")} • {fmtT(t("flagsAndDiscrepancies"), { flags: enc.open_flags, conflicts: enc.open_conflicts })}
                  </p>
                </div>
                <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                  {enc.urgency && (
                    <span title={(enc.priority_alerts || []).join("\n")}>
                      <Tag kind="bad">
                        {enc.urgency === "EMERGENCY" ? t("urgencyEmergency") : t("urgencyUrgent")}
                      </Tag>
                    </span>
                  )}
                  <Tag kind={enc.status === "reviewed" ? "ver" : "warn"}>
                    {enc.status === "reviewed" ? t("reviewed") : t("stNeedsReview")}
                  </Tag>
                  <button className="btn out sm" onClick={() => openBackendCase(enc)}>
                    {t("openReview")}
                  </button>
                </div>
              </div>
            ))
          ) : reviewLocal.length === 0 ? (
            <p className="soft mt">{t("noOpenFlags")}</p>
          ) : (
            reviewLocal.map(({ p, c }) => (
              <div className="li" key={p.id}>
                <div>
                  <b>{p.name}</b>
                  <p className="small soft">
                    {c.answers.complaint || t("generalIntake")} · {fmtT(t("nOpenFlags"), { n: openFlags(c).length })}
                  </p>
                </div>
                <button className="btn out sm" onClick={() => openLocal(p.id, "review")}>
                  {t("openReview")}
                </button>
              </div>
            ))
          )}
        </div>

        <div className="card">
          <h2>{t("recentCases")}</h2>
          {rows.slice(0, 5).map(({ p, c }) => (
            <div className="li" key={p.id}>
              <div>
                <b>{p.name}</b>
                <p className="small soft">
                  {p.id} · {p.age ? `${p.age} ${t("yrs")}` : t("ageNotSpecified")}
                </p>
              </div>
              <StatusTag s={statusOf(c)} />
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
