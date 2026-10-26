import { useState, useEffect, useCallback } from "react";
import { Icon, Spinner, EmptyState, ErrorBanner } from "../components/ui";
import apiClient from "../api/client";

export default function AuditLog() {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionFilter, setActionFilter] = useState("");

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const endpoint = actionFilter
        ? `/api/auth/audit?action=${encodeURIComponent(actionFilter)}&limit=100`
        : "/api/auth/audit?limit=100";
      const data = await apiClient.get(endpoint);
      setEvents(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err.message || "Failed to load audit logs");
    } finally {
      setLoading(false);
    }
  }, [actionFilter]);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  const getActionTagClass = (action) => {
    if (action.includes("FAILED") || action.includes("DENIED")) return "t-bad";
    if (action.includes("SUCCESS") || action.includes("CREATED")) return "t-patient";
    if (action.includes("LOGOUT")) return "t-sys";
    return "t-doc";
  };

  return (
    <div className="audit-log">
      <div className="head">
        <div>
          <span className="tag t-doc" style={{ marginBottom: "0.4rem" }}>
            <Icon n="shield" size={13} /> Admin Security
          </span>
          <h2>System Audit Trail</h2>
          <p className="soft small">
            Tamper-evident, backend-verified record of all authentication, role access, and clinical events.
          </p>
        </div>
        <div className="actions">
          <button className="btn out sm" onClick={fetchLogs} disabled={loading}>
            <Icon n="reset" size={14} /> Refresh
          </button>
        </div>
      </div>

      <div className="card" style={{ marginBottom: "1rem" }}>
        <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
          <span className="small soft" style={{ fontWeight: 600 }}>Filter by Action:</span>
          {["", "LOGIN_SUCCESS", "LOGIN_FAILED", "LOGOUT", "USER_REGISTERED", "PATIENT_CREATED", "ENCOUNTER_CREATED"].map((act) => (
            <button
              key={act}
              className={`chip ${actionFilter === act ? "on" : ""}`}
              onClick={() => setActionFilter(act)}
              style={{ fontSize: "0.78rem", padding: "0.25rem 0.75rem" }}
            >
              {act === "" ? "All Events" : act}
            </button>
          ))}
        </div>
      </div>

      {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

      <div className="card scroll">
        {loading ? (
          <div style={{ padding: "3rem", display: "flex", justifyContent: "center" }}>
            <Spinner text="Loading audit trail from backend..." />
          </div>
        ) : events.length === 0 ? (
          <EmptyState
            title="No audit events found"
            message={actionFilter ? `No events match action filter '${actionFilter}'.` : "The audit trail is currently empty."}
            icon="doc"
          />
        ) : (
          <table>
            <thead>
              <tr>
                <th style={{ width: "170px" }}>Timestamp (UTC)</th>
                <th style={{ width: "160px" }}>Action</th>
                <th style={{ width: "150px" }}>Actor</th>
                <th style={{ width: "120px" }}>Resource</th>
                <th>Summary / Details</th>
                <th style={{ width: "110px" }}>IP Address</th>
              </tr>
            </thead>
            <tbody>
              {events.map((ev) => (
                <tr key={ev.id}>
                  <td className="small soft">
                    {new Date(ev.timestamp).toLocaleString(undefined, {
                      year: "numeric",
                      month: "short",
                      day: "2-digit",
                      hour: "2-digit",
                      minute: "2-digit",
                      second: "2-digit",
                    })}
                  </td>
                  <td>
                    <span className={`tag ${getActionTagClass(ev.action)}`}>
                      {ev.action}
                    </span>
                  </td>
                  <td>
                    <b>{ev.actor_username || "anonymous"}</b>
                    {ev.actor_role && (
                      <span className="small soft" style={{ display: "block" }}>
                        Role: {ev.actor_role}
                      </span>
                    )}
                  </td>
                  <td>
                    {ev.resource_type ? (
                      <span className="small">
                        {ev.resource_type} {ev.resource_id ? `#${ev.resource_id}` : ""}
                      </span>
                    ) : (
                      <span className="soft small">-</span>
                    )}
                  </td>
                  <td className="small" style={{ lineHeight: 1.4 }}>
                    {ev.change_summary || "-"}
                  </td>
                  <td className="small soft">{ev.ip_address || "127.0.0.1"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

