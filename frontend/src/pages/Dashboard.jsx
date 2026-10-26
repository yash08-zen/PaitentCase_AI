import { useState, useEffect, useCallback } from "react";
import { useStore } from "../state/store";
import { completeness, openFlags, statusOf } from "../utils/engine";
import { Icon, Ring, StatusTag, Proto, Tag } from "../components/ui";
import apiClient from "../api/client";

const WEEK = [["S", 2], ["M", 7], ["T", 5], ["W", 9], ["T", 6], ["F", 3], ["S", 1]];

export default function Dashboard({ go }) {
  const { patients, cases, setActiveId } = useStore();
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
    const localMatch = patients.find((p) => p.backendId === backendEnc.patient_id || p.name === backendEnc.patient_name);
    if (localMatch) {
      setActiveId(localMatch.id);
    } else if (patients.length > 0) {
      setActiveId(patients[0].id);
    }
    go("review");
  };

  const totalPatientsCount = liveSummary?.total_patients ?? patients.length;
  const completedCount = liveSummary?.completed_cases ?? done.length;
  const reviewCount = liveSummary?.cases_needing_review ?? reviewLocal.length;
  const activeCount = liveSummary?.active_encounters ?? rows.filter((r) => ["interview", "new"].includes(r.c?.stage)).length;

  const stats = [
    ["Total patients", totalPatientsCount, "Registered in system"],
    ["Interviews complete", completedCount, "Ready for clinician review"],
    ["Needs review", reviewCount, "Open flags / conflicts"],
    ["In progress", activeCount, "Intake currently active"],
  ];

  return (
    <>
      <div className="head">
        <div>
          <h1>Dashboard</h1>
          <p className="soft">Intake activity and cases waiting for clinician review.</p>
        </div>
        <div className="actions">
          <button className="btn primary" onClick={() => go("register")}>
            <Icon n="plus" />
            Register patient
          </button>
          <button className="btn out" onClick={() => go("patients")}>
            View patients
          </button>
        </div>
      </div>

      <div className="stats">
        {stats.map(([l, v, s], i) => (
          <div key={l} className={`card stat ${i === 0 ? "hero" : ""}`}>
            <div className="row">
              <span>{l}</span>
              <span className="arrow">
                <Icon n="arrow" size={14} />
              </span>
            </div>
            <b>{v}</b>
            <p className="small">{s}</p>
          </div>
        ))}
      </div>

      <div className="cols">
        <div className="card">
          <h2>Weekly intake</h2>
          <p className="small soft">Patients registered per day (sample distribution)</p>
          <div className="bars">
            {WEEK.map(([d, n], i) => (
              <div key={i} className="barcol">
                <div
                  className={`pillbar ${n >= 5 ? "on" : "hatch"}`}
                  style={{ height: 24 + n * 14 }}
                  title={`${n} patients`}
                />
                <span className="small soft">{d}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="card center">
          <h2>Average case completeness</h2>
          <p className="small soft">Across completed interviews</p>
          <div style={{ margin: "1rem auto" }}>
            <Ring value={avg} label="Average completeness" />
          </div>
          <p className="small soft">Measures completeness of information, not health or diagnostic accuracy.</p>
        </div>
      </div>

      <div className="cols">
        {/* Clinician Review Queue */}
        <div className="card">
          <div className="row">
            <h2>Cases requiring review</h2>
            <Proto>Clinician review queue</Proto>
          </div>

          {liveCases && liveCases.length > 0 ? (
            liveCases.map((enc) => (
              <div className="li" key={enc.encounter_id}>
                <div>
                  <b>{enc.patient_name}</b>
                  <p className="small soft">
                    {enc.chief_complaint || "General intake"} • {enc.open_flags} flag(s), {enc.open_conflicts} discrepancy(ies)
                  </p>
                </div>
                <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                  <Tag kind={enc.status === "reviewed" ? "ver" : "warn"}>
                    {enc.status === "reviewed" ? "Reviewed" : "Needs Review"}
                  </Tag>
                  <button className="btn out sm" onClick={() => openBackendCase(enc)}>
                    Open review
                  </button>
                </div>
              </div>
            ))
          ) : reviewLocal.length === 0 ? (
            <p className="soft mt">No open flags. All reviewed cases are up to date.</p>
          ) : (
            reviewLocal.map(({ p, c }) => (
              <div className="li" key={p.id}>
                <div>
                  <b>{p.name}</b>
                  <p className="small soft">
                    {c.answers.complaint || "Intake"} · {openFlags(c).length} open flag(s)
                  </p>
                </div>
                <button className="btn out sm" onClick={() => openLocal(p.id, "review")}>
                  Open review
                </button>
              </div>
            ))
          )}
        </div>

        <div className="card">
          <h2>Recent cases</h2>
          {rows.slice(0, 5).map(({ p, c }) => (
            <div className="li" key={p.id}>
              <div>
                <b>{p.name}</b>
                <p className="small soft">
                  {p.id} · {p.age ? `${p.age} yrs` : "Age not specified"}
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
