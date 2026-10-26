import { useState, useEffect } from 'react';
import { patientsApi, encountersApi } from '../services/api';

export default function PatientsPage({ onNavigate }) {
  const [patients, setPatients] = useState([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      try {
        const data = await patientsApi.list(search, page);
        if (!cancelled) { setPatients(data.items); setTotal(data.total); }
      } catch (err) {
        if (!cancelled) setError(err.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [search, page]);

  async function startEncounter(patientId) {
    try {
      const enc = await encountersApi.create({ patient_id: patientId });
      onNavigate('interview', { encounterId: enc.id });
    } catch (err) {
      alert('Failed to start encounter: ' + err.message);
    }
  }

  return (
    <div className="page-content animate-fade">
      <div className="page-header">
        <div>
          <h1>Patients</h1>
          <p className="page-subtitle">{total} patient{total !== 1 ? 's' : ''} registered</p>
        </div>
        <button className="btn btn-primary" onClick={() => onNavigate('register')}>
          + Register Patient
        </button>
      </div>

      {error && <div className="alert alert-danger mb-md">⚠ {error}</div>}

      <div style={{ marginBottom: 'var(--sp-md)' }}>
        <input
          className="form-input"
          type="search"
          placeholder="🔍  Search by name…"
          value={search}
          onChange={e => { setSearch(e.target.value); setPage(1); }}
          style={{ maxWidth: 360 }}
        />
      </div>

      {loading ? (
        <div className="loading-center"><div className="loader loader-lg" /><p>Loading patients…</p></div>
      ) : patients.length === 0 ? (
        <div className="empty-state card">
          <div className="empty-state-icon">👥</div>
          <h3>No patients found</h3>
          <p>{search ? 'No results match your search.' : 'Register the first patient to get started.'}</p>
          {!search && (
            <button className="btn btn-primary mt-md" onClick={() => onNavigate('register')}>
              Register First Patient
            </button>
          )}
        </div>
      ) : (
        <>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Age</th>
                  <th>Gender</th>
                  <th>Language</th>
                  <th>Contact</th>
                  <th>Registered</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {patients.map(p => (
                  <tr key={p.id}>
                    <td style={{ fontWeight: 600 }}>{p.full_name}</td>
                    <td>{p.age || '—'}</td>
                    <td className="text-muted">{p.gender || '—'}</td>
                    <td className="text-muted">{p.preferred_language}</td>
                    <td className="text-sm text-muted">{p.contact_phone || p.contact_email || '—'}</td>
                    <td className="text-sm text-muted">{new Date(p.created_at).toLocaleDateString()}</td>
                    <td>
                      <div className="flex gap-xs">
                        <button
                          className="btn btn-primary btn-sm"
                          onClick={() => startEncounter(p.id)}
                        >
                          New Encounter
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {total > 20 && (
            <div className="flex gap-sm items-center justify-center" style={{ marginTop: 'var(--sp-lg)' }}>
              <button className="btn btn-ghost btn-sm" disabled={page === 1} onClick={() => setPage(p => p - 1)}>← Prev</button>
              <span className="text-muted text-sm">Page {page} of {Math.ceil(total / 20)}</span>
              <button className="btn btn-ghost btn-sm" disabled={page * 20 >= total} onClick={() => setPage(p => p + 1)}>Next →</button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
