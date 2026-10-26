import { useState, useEffect } from 'react';
import { dashboardApi } from '../services/api';

function StatCard({ icon, value, label, color }) {
  return (
    <div className="stat-card animate-fade">
      <div className="stat-icon" style={{ color }}>{icon}</div>
      <div className="stat-value">{value ?? <span className="loader" />}</div>
      <div className="stat-label">{label}</div>
    </div>
  );
}

export default function DashboardPage({ onNavigate }) {
  const [summary, setSummary] = useState(null);
  const [cases, setCases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    async function load() {
      try {
        const [s, c] = await Promise.all([dashboardApi.summary(), dashboardApi.cases()]);
        setSummary(s);
        setCases(c);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const statusBadge = (status) => {
    const map = {
      pending:     ['badge-muted',   '⏳ Pending'],
      in_progress: ['badge-warning', '▶ In Progress'],
      completed:   ['badge-success', '✓ Completed'],
      reviewed:    ['badge-info',    '👁 Reviewed'],
    };
    const [cls, label] = map[status] || ['badge-muted', status];
    return <span className={`badge ${cls}`}>{label}</span>;
  };

  return (
    <div className="page-content animate-fade">
      <div className="page-header">
        <div className="page-header-left">
          <h1>Dashboard</h1>
          <p className="page-subtitle">Overview of patients, encounters and cases needing review</p>
        </div>
        <div className="flex gap-sm">
          <button className="btn btn-primary" onClick={() => onNavigate('register')}>
            + Register Patient
          </button>
        </div>
      </div>

      {error && <div className="alert alert-danger mb-md">⚠ {error}</div>}

      <div className="notice-banner mb-md">
        ℹ️ PatientCase AI assists with information collection only. Final clinical decisions rest with the clinician.
      </div>

      {/* Stats */}
      <div className="grid-4" style={{ marginBottom: 'var(--sp-xl)' }}>
        <StatCard icon="👥" value={summary?.total_patients}      label="Total Patients"       color="var(--c-primary)" />
        <StatCard icon="▶"  value={summary?.active_encounters}   label="Active Encounters"    color="var(--c-warning)" />
        <StatCard icon="✓"  value={summary?.completed_cases}     label="Completed Cases"      color="var(--c-success)" />
        <StatCard icon="🔔" value={summary?.cases_needing_review} label="Needing Review"      color="var(--c-danger)"  />
      </div>

      {/* Cases needing review */}
      <div className="section-title">Cases Needing Review</div>
      {loading ? (
        <div className="loading-center"><div className="loader loader-lg" /><p>Loading cases…</p></div>
      ) : cases.length === 0 ? (
        <div className="empty-state card">
          <div className="empty-state-icon">✅</div>
          <h3>No cases need review</h3>
          <p>All cases are up to date. Register a new patient or start an encounter to begin.</p>
          <button className="btn btn-primary mt-md" onClick={() => onNavigate('register')}>
            Register New Patient
          </button>
        </div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Patient</th>
                <th>Chief Complaint</th>
                <th>Status</th>
                <th>Started</th>
                <th>Flags</th>
                <th>Conflicts</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {cases.map(c => (
                <tr key={c.encounter_id}>
                  <td style={{ fontWeight: 600 }}>{c.patient_name}</td>
                  <td className="text-muted">{c.chief_complaint || '—'}</td>
                  <td>{statusBadge(c.status)}</td>
                  <td className="text-sm text-muted">{new Date(c.started_at).toLocaleDateString()}</td>
                  <td>
                    {c.open_flags > 0
                      ? <span className="badge badge-warning">⚠ {c.open_flags}</span>
                      : <span className="text-dim">—</span>}
                  </td>
                  <td>
                    {c.open_conflicts > 0
                      ? <span className="badge badge-danger">⚡ {c.open_conflicts}</span>
                      : <span className="text-dim">—</span>}
                  </td>
                  <td>
                    <button
                      className="btn btn-secondary btn-sm"
                      onClick={() => onNavigate('case-review', { encounterId: c.encounter_id })}
                    >
                      Review →
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
