import { useState } from "react";
import { useStore } from "../state/store";
import { completeness, statusOf, openFlags } from "../utils/engine";
import { Empty, StatusTag, Spinner, Icon } from "../components/ui";

const FILTERS = ["All", "Registered", "In interview", "Needs review", "Ready for review", "Finalized"];

export default function PatientList({ go }) {
  const { patients, cases, query, setQuery, setActiveId, loading, refreshPatients } = useStore();
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
          <h1>Patients</h1>
          <p className="soft">
            {patients.length} verified records. Search by name, ID, or chief complaint.
          </p>
        </div>
        <div className="actions">
          <button className="btn out sm" onClick={refreshPatients} disabled={loading} title="Refresh patients from backend">
            <Icon n="reset" size={14} /> Refresh
          </button>
          <input
            className="plain"
            placeholder="Search patients..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label="Search patients"
          />
          <button className="btn primary" onClick={() => go("register")}>
            <Icon n="plus" size={14} /> Register patient
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
            {f}
          </button>
        ))}
      </div>

      {loading && patients.length === 0 ? (
        <div style={{ padding: "3rem", display: "flex", justifyContent: "center" }}>
          <Spinner text="Loading patient records from backend..." />
        </div>
      ) : rows.length === 0 ? (
        <Empty
          title="No patients found"
          text="Try a different search term or filter, or register a new patient."
          action={
            <div className="actions">
              <button className="btn out" onClick={() => { setQuery(""); setFlt("All"); }}>
                Clear filters
              </button>
              <button className="btn primary" onClick={() => go("register")}>
                Register patient
              </button>
            </div>
          }
        />
      ) : (
        <div className="card scroll">
          <table>
            <thead>
              <tr>
                <th>Patient</th>
                <th>Chief Complaint</th>
                <th>Status</th>
                <th>Completeness</th>
                <th>Open flags</th>
                <th style={{ textAlign: "right" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.p.id}>
                  <td>
                    <b>{r.p.name}</b>
                    <p className="small soft">
                      {r.p.id} &bull; {r.p.age} yrs &bull; {r.p.gender} &bull; {r.p.language}
                    </p>
                  </td>
                  <td>
                    {r.c.answers?.complaint ? (
                      <span>{r.c.answers.complaint}</span>
                    ) : (
                      <span className="soft">Not yet recorded</span>
                    )}
                  </td>
                  <td>
                    <StatusTag s={r.s} />
                  </td>
                  <td>
                    {r.c.stage === "new" ? (
                      <span className="soft">Pending</span>
                    ) : (
                      `${completeness(r.c).total}%`
                    )}
                  </td>
                  <td>
                    {r.c.stage === "complete" ? openFlags(r.c).length : <span className="soft">None</span>}
                  </td>
                  <td className="end">
                    <button className="btn out sm" onClick={() => act(r)}>
                      {r.c.stage === "complete"
                        ? "Open review"
                        : r.c.stage === "new"
                        ? "Start interview"
                        : "Resume interview"}
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
