import { useState } from "react";
import { useStore } from "../state/store";
import { completeness, statusOf, openFlags } from "../utils/engine";
import { Empty, StatusTag, Spinner, Icon, STATUS_KEYS } from "../components/ui";
import { fmtT } from "../utils/i18n";

const FILTERS = ["All", "Registered", "In interview", "Needs review", "Ready for review", "Finalized"];

export default function PatientList({ go }) {
  const { patients, cases, query, setQuery, setActiveId, loading, refreshPatients, t } = useStore();
  const [flt, setFlt] = useState("All");

  const q = (query || "").trim().toLowerCase();

  const rows = patients
    .map((p) => {
      const c = cases[p.id] || { stage: "new", answers: {}, stack: [], skipped: [], flags: {}, docs: [] };
      const s = statusOf(c);
      return { p, c, s };
    })
    .filter((r) => {
      const matchFilter = flt === "All" || r.s === flt;
      const complaintText = r.c.answers?.complaint || "";
      const matchQuery =
        !q ||
        `${r.p.name} ${r.p.id} ${complaintText}`.toLowerCase().includes(q);
      return matchFilter && matchQuery;
    });

  const act = (r) => {
    setActiveId(r.p.id);
    go(r.c.stage === "complete" ? "review" : "interview");
  };

  return (
    <>
      <div className="head">
        <div>
          <h1>{t("patients")}</h1>
          <p className="soft">
            {fmtT(t("patientsSubtitle"), { n: patients.length })}
          </p>
        </div>
        <div className="actions">
          <button className="btn out sm" onClick={refreshPatients} disabled={loading} title={t("refreshPatientsTitle")}>
            <Icon n="reset" size={14} /> {t("refresh")}
          </button>
          <input
            className="plain"
            placeholder={t("searchShort")}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label={t("searchPatients")}
          />
          <button className="btn primary" onClick={() => go("register")}>
            <Icon n="plus" size={14} /> {t("register")}
          </button>
        </div>
      </div>

      <div className="chips">
        {FILTERS.map((f) => (
          <button
            key={f}
            className={`chip ${flt === f ? "on" : ""}`}
            onClick={() => setFlt(f)}
          >
            {t(STATUS_KEYS[f])}
          </button>
        ))}
      </div>

      {loading && patients.length === 0 ? (
        <div style={{ padding: "3rem", display: "flex", justifyContent: "center" }}>
          <Spinner text={t("loadingPatients")} />
        </div>
      ) : rows.length === 0 ? (
        <Empty
          title={t("noPatientsFound")}
          text={t("noPatientsText")}
          action={
            <div className="actions">
              <button className="btn out" onClick={() => { setQuery(""); setFlt("All"); }}>
                {t("clearFilters")}
              </button>
              <button className="btn primary" onClick={() => go("register")}>
                {t("register")}
              </button>
            </div>
          }
        />
      ) : (
        <div className="card scroll">
          <table>
            <thead>
              <tr>
                <th>{t("colPatient")}</th>
                <th>{t("colComplaint")}</th>
                <th>{t("colStatus")}</th>
                <th>{t("colCompleteness")}</th>
                <th>{t("colOpenFlags")}</th>
                <th style={{ textAlign: "right" }}>{t("colActions")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.p.id}>
                  <td>
                    <b>{r.p.name}</b>
                    <p className="small soft">
                      {r.p.id} &bull; {r.p.age ? `${r.p.age} ${t("yrs")}` : t("ageNotSpecified")} &bull; {r.p.gender} &bull; {r.p.language}
                    </p>
                  </td>
                  <td>
                    {r.c.answers?.complaint ? (
                      <span>{r.c.answers.complaint}</span>
                    ) : (
                      <span className="soft">{t("notYetRecorded")}</span>
                    )}
                  </td>
                  <td>
                    <StatusTag s={r.s} />
                  </td>
                  <td>
                    {r.c.stage === "new" ? (
                      <span className="soft">{t("pending")}</span>
                    ) : (
                      `${completeness(r.c).total}%`
                    )}
                  </td>
                  <td>
                    {r.c.stage === "complete" ? openFlags(r.c).length : <span className="soft">{t("none")}</span>}
                  </td>
                  <td className="end">
                    <button className="btn out sm" onClick={() => act(r)}>
                      {r.c.stage === "complete"
                        ? t("openReview")
                        : r.c.stage === "new"
                        ? t("startInterviewShort")
                        : t("resumeInterviewShort")}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
