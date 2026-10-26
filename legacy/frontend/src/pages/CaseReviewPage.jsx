import { useState, useEffect } from 'react';
import { caseApi, encountersApi, patientsApi, documentsApi } from '../services/api';

function Section({ title, children }) {
  return (
    <div className="card" style={{ marginBottom: 'var(--sp-md)' }}>
      <div className="section-title">{title}</div>
      {children}
    </div>
  );
}

function InfoRow({ label, value, source }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--c-border-subtle)', alignItems: 'flex-start', gap: 16 }}>
      <span className="text-muted text-sm" style={{ flexShrink: 0, width: 180 }}>{label}</span>
      <span style={{ flex: 1, fontWeight: 500, textAlign: 'right' }}>{value || '—'}</span>
      {source && <span className="source-tag" style={{ flexShrink: 0 }}>📌 {source}</span>}
    </div>
  );
}

export default function CaseReviewPage({ encounterId, onNavigate }) {
  const [encounter, setEncounter] = useState(null);
  const [patient, setPatient] = useState(null);
  const [summary, setSummary]   = useState(null);
  const [readiness, setReadiness] = useState(null);
  const [missing, setMissing]   = useState(null);
  const [conflicts, setConflicts] = useState([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState('');
  const [uploadFile, setUploadFile] = useState(null);
  const [uploading, setUploading]   = useState(false);
  const [uploadMsg, setUploadMsg]   = useState('');

  useEffect(() => {
    async function load() {
      try {
        const enc = await encountersApi.get(encounterId);
        setEncounter(enc);
        const pat = await patientsApi.get(enc.patient_id);
        setPatient(pat);
        const [sum, ready, miss, confl] = await Promise.all([
          caseApi.summary(encounterId),
          caseApi.readiness(encounterId),
          caseApi.missingInfo(encounterId),
          caseApi.contradictions(encounterId),
        ]);
        setSummary(sum);
        setReadiness(ready);
        setMissing(miss);
        setConflicts(confl);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [encounterId]);

  async function handleUpload(e) {
    e.preventDefault();
    if (!uploadFile) return;
    setUploading(true);
    setUploadMsg('');
    try {
      const fd = new FormData();
      fd.append('file', uploadFile);
      fd.append('encounter_id', encounterId);
      fd.append('document_type', 'prescription');
      await documentsApi.upload(patient.id, fd);
      setUploadMsg('✅ Document uploaded. Processing in background…');
      setUploadFile(null);
      // Refresh case analysis
      const [sum, ready, miss, confl] = await Promise.all([
        caseApi.summary(encounterId),
        caseApi.readiness(encounterId),
        caseApi.missingInfo(encounterId),
        caseApi.contradictions(encounterId),
      ]);
      setSummary(sum); setReadiness(ready); setMissing(miss); setConflicts(confl);
    } catch (err) {
      setUploadMsg(`❌ Upload failed: ${err.message}`);
    } finally {
      setUploading(false);
    }
  }

  const readinessColor = (score) => {
    if (score >= 0.8) return 'var(--c-success)';
    if (score >= 0.5) return 'var(--c-warning)';
    return 'var(--c-danger)';
  };

  if (loading) return <div className="page-content"><div className="loading-center"><div className="loader loader-lg" /><p>Loading case…</p></div></div>;
  if (error)   return <div className="page-content"><div className="alert alert-danger">⚠ {error}</div></div>;

  return (
    <div className="page-content animate-fade">
      <div className="page-header">
        <div>
          <h1>Case Review</h1>
          <p className="page-subtitle">Encounter #{encounterId} · {patient?.full_name}</p>
        </div>
        <div className="flex gap-sm">
          <button className="btn btn-secondary" onClick={() => onNavigate('interview', { encounterId })}>
            Continue Interview
          </button>
          <button className="btn btn-ghost" onClick={() => onNavigate('dashboard')}>
            ← Dashboard
          </button>
        </div>
      </div>

      <div className="notice-banner mb-md">
        ⚕️ This case summary assists with information collection. Final clinical interpretation and decisions rest with the clinician.
      </div>

      {/* Readiness */}
      {readiness && (
        <div className="card" style={{ marginBottom: 'var(--sp-md)', display: 'flex', alignItems: 'center', gap: 'var(--sp-lg)', flexWrap: 'wrap' }}>
          <div>
            <div style={{ fontSize: '2.5rem', fontWeight: 800, color: readinessColor(readiness.score) }}>
              {Math.round(readiness.score * 100)}%
            </div>
            <div className="text-muted text-sm">Case Completeness</div>
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 700, color: readinessColor(readiness.score), marginBottom: 6 }}>
              {readiness.label}
            </div>
            <div className="progress-track">
              <div className="progress-fill" style={{ width: `${readiness.score * 100}%`, background: readinessColor(readiness.score) }} />
            </div>
            <div className="text-xs text-dim mt-sm">{readiness.disclaimer}</div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {missing?.total_missing > 0 && (
              <span className="badge badge-warning">⚠ {missing.total_missing} missing fields</span>
            )}
            {conflicts.length > 0 && (
              <span className="badge badge-danger">⚡ {conflicts.length} conflict{conflicts.length > 1 ? 's' : ''}</span>
            )}
          </div>
        </div>
      )}

      {/* Patient Info */}
      <Section title="Patient Information">
        <InfoRow label="Full Name"   value={patient?.full_name}          source="registration" />
        <InfoRow label="Age / DOB"   value={`${patient?.age || '?'} yrs / ${patient?.date_of_birth || '?'}`} source="registration" />
        <InfoRow label="Gender"      value={patient?.gender}             source="registration" />
        <InfoRow label="Contact"     value={patient?.contact_phone || patient?.contact_email} source="registration" />
        <InfoRow label="Language"    value={patient?.preferred_language} source="registration" />
      </Section>

      {/* Encounter */}
      <Section title="Encounter">
        <InfoRow label="Encounter ID"    value={encounter?.id} />
        <InfoRow label="Chief Complaint" value={encounter?.chief_complaint} source="patient response" />
        <InfoRow label="Status"          value={encounter?.status} />
        <InfoRow label="Started"         value={encounter ? new Date(encounter.started_at).toLocaleString() : ''} />
      </Section>

      {/* Missing Info */}
      {missing?.total_missing > 0 && (
        <Section title={`⚠ Missing Information (${missing.total_missing})`}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {missing.missing_fields.map(f => (
              <div key={f.field} className="alert alert-warning" style={{ fontSize: '0.85rem' }}>
                <div style={{ fontWeight: 700 }}>{f.field.replace(/_/g,' ')}{f.is_critical ? ' (Critical)' : ''}</div>
                <div>{f.reason}</div>
              </div>
            ))}
          </div>
          <button
            className="btn btn-secondary btn-sm mt-md"
            onClick={() => onNavigate('interview', { encounterId })}
          >
            Complete Interview →
          </button>
        </Section>
      )}

      {/* Conflicts */}
      {conflicts.length > 0 && (
        <Section title={`⚡ Conflicts Requiring Verification (${conflicts.length})`}>
          {conflicts.map(c => (
            <div key={c.id} className="alert alert-danger" style={{ flexDirection: 'column', alignItems: 'flex-start', marginBottom: 8 }}>
              <div style={{ fontWeight: 700, marginBottom: 4 }}>
                Field: <code style={{ background: 'var(--c-danger-bg)', padding: '2px 6px', borderRadius: 4 }}>{c.field}</code>
                <span className={`badge ${c.status === 'open' ? 'badge-danger' : 'badge-success'}`} style={{ marginLeft: 8 }}>{c.status}</span>
              </div>
              <div className="text-sm"><span className="source-tag">📌 {c.source_a}</span> {c.value_a}</div>
              <div className="text-sm mt-sm"><span className="source-tag">📄 {c.source_b}</span> {c.value_b}</div>
              <div className="text-sm text-muted mt-sm">{c.description}</div>
            </div>
          ))}
          <p className="text-xs text-dim mt-sm">Both sources are preserved. Clinician verification required before any changes are made.</p>
        </Section>
      )}

      {/* Document Upload */}
      <Section title="Upload Medical Documents">
        <p className="text-sm text-muted" style={{ marginBottom: 'var(--sp-md)' }}>
          Upload prescriptions or medical reports (PDF or image). Extracted information will be marked as unverified until reviewed by clinical staff.
        </p>
        <form onSubmit={handleUpload} style={{ display: 'flex', gap: 'var(--sp-sm)', flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <div className="form-group" style={{ flex: 1, minWidth: 200 }}>
            <label className="form-label" htmlFor="doc-upload">Select file (PDF / JPG / PNG)</label>
            <input
              id="doc-upload"
              type="file"
              className="form-input"
              accept=".pdf,.jpg,.jpeg,.png,.webp,.tiff"
              onChange={e => setUploadFile(e.target.files[0])}
              style={{ padding: '8px 12px' }}
            />
          </div>
          <button type="submit" className="btn btn-secondary" disabled={!uploadFile || uploading}>
            {uploading ? <><span className="loader" /> Uploading…</> : '⬆ Upload'}
          </button>
        </form>
        {uploadMsg && <div className={`alert ${uploadMsg.startsWith('✅') ? 'alert-success' : 'alert-danger'} mt-md`}>{uploadMsg}</div>}
      </Section>

      {/* Case Summary */}
      {summary && (
        <Section title="Generated Case Summary">
          <div className="notice-banner mb-md">
            ⚠ Unverified document extractions are clearly marked. This summary is for clinical reference only.
          </div>
          <pre style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: '0.78rem',
            color: 'var(--c-text-muted)',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
            background: 'var(--c-surface-2)',
            padding: 'var(--sp-md)',
            borderRadius: 'var(--r-md)',
            lineHeight: 1.7,
            overflowX: 'auto',
          }}>
            {summary.summary_text}
          </pre>
        </Section>
      )}
    </div>
  );
}
