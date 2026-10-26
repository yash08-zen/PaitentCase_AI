import { useState } from 'react';
import { patientsApi, encountersApi } from '../services/api';

const GENDER_OPTIONS = [
  'Male', 'Female', 'Non-binary', 'Prefer to self-describe', 'Prefer not to say',
];

const LANGUAGE_OPTIONS = [
  'English', 'Hindi', 'Bengali', 'Tamil', 'Telugu', 'Marathi', 'Gujarati', 'Other',
];

export default function PatientRegistrationPage({ onNavigate }) {
  const [form, setForm] = useState({
    full_name: '',
    date_of_birth: '',
    age: '',
    gender: '',
    contact_phone: '',
    contact_email: '',
    preferred_language: 'English',
  });
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(null);
  const [serverError, setServerError] = useState('');

  function set(field, value) {
    setForm(f => ({ ...f, [field]: value }));
    setErrors(e => ({ ...e, [field]: '' }));
  }

  function validate() {
    const errs = {};
    if (!form.full_name.trim())       errs.full_name = 'Full name is required.';
    if (!form.gender)                  errs.gender = 'Please select a gender option.';
    if (form.age && (isNaN(Number(form.age)) || Number(form.age) < 0 || Number(form.age) > 120))
      errs.age = 'Please enter a valid age (0–120).';
    if (form.contact_email && !/\S+@\S+\.\S+/.test(form.contact_email))
      errs.contact_email = 'Please enter a valid email address.';
    return errs;
  }

  async function handleSubmit(e) {
    e.preventDefault();
    const errs = validate();
    if (Object.keys(errs).length) { setErrors(errs); return; }

    setLoading(true);
    setServerError('');
    try {
      const payload = {
        full_name: form.full_name.trim(),
        date_of_birth: form.date_of_birth || null,
        age: form.age ? Number(form.age) : null,
        gender: form.gender,
        contact_phone: form.contact_phone || null,
        contact_email: form.contact_email || null,
        preferred_language: form.preferred_language,
      };
      const patient = await patientsApi.create(payload);

      // Auto-create a new encounter
      const encounter = await encountersApi.create({ patient_id: patient.id });
      setSuccess({ patient, encounter });
    } catch (err) {
      setServerError(err.message || 'Registration failed. Please try again.');
    } finally {
      setLoading(false);
    }
  }

  if (success) {
    return (
      <div className="page-content animate-fade" style={{ maxWidth: 560 }}>
        <div className="card" style={{ textAlign: 'center', padding: 'var(--sp-2xl)' }}>
          <div style={{ fontSize: '3rem', marginBottom: 'var(--sp-md)' }}>✅</div>
          <h2>Patient Registered!</h2>
          <p className="mt-md" style={{ marginBottom: 'var(--sp-lg)' }}>
            <strong>{success.patient.full_name}</strong> has been registered successfully.
            An encounter has been created (ID: {success.encounter.id}).
          </p>
          <div className="flex gap-sm justify-center" style={{ flexWrap: 'wrap' }}>
            <button
              className="btn btn-primary"
              onClick={() => onNavigate('interview', { encounterId: success.encounter.id })}
            >
              Start Interview →
            </button>
            <button className="btn btn-secondary" onClick={() => onNavigate('dashboard')}>
              Go to Dashboard
            </button>
            <button
              className="btn btn-ghost"
              onClick={() => { setSuccess(null); setForm({ full_name:'',date_of_birth:'',age:'',gender:'',contact_phone:'',contact_email:'',preferred_language:'English' }); }}
            >
              Register Another
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="page-content animate-fade" style={{ maxWidth: 680 }}>
      <div className="page-header">
        <div>
          <h1>Register Patient</h1>
          <p className="page-subtitle">Collect basic patient information to begin a case.</p>
        </div>
      </div>

      <div className="notice-banner mb-md">
        🔒 Patient information is stored securely and used only for clinical case-taking purposes.
      </div>

      {serverError && <div className="alert alert-danger mb-md">⚠ {serverError}</div>}

      <div className="card">
        <form onSubmit={handleSubmit} noValidate>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-md)' }}>

            {/* Full Name */}
            <div className="form-group">
              <label className="form-label" htmlFor="reg-name">
                Full Name <span className="required">*</span>
              </label>
              <input
                id="reg-name" className={`form-input ${errors.full_name ? 'error' : ''}`}
                type="text" placeholder="Patient's full name"
                value={form.full_name} onChange={e => set('full_name', e.target.value)}
              />
              {errors.full_name && <span className="form-error">⚠ {errors.full_name}</span>}
            </div>

            {/* DOB + Age */}
            <div className="grid-2">
              <div className="form-group">
                <label className="form-label" htmlFor="reg-dob">Date of Birth</label>
                <input
                  id="reg-dob" className="form-input" type="date"
                  value={form.date_of_birth} onChange={e => set('date_of_birth', e.target.value)}
                />
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="reg-age">Age (years)</label>
                <input
                  id="reg-age" className={`form-input ${errors.age ? 'error' : ''}`}
                  type="number" placeholder="e.g. 35" min={0} max={120}
                  value={form.age} onChange={e => set('age', e.target.value)}
                />
                {errors.age && <span className="form-error">⚠ {errors.age}</span>}
              </div>
            </div>

            {/* Gender */}
            <div className="form-group">
              <label className="form-label" htmlFor="reg-gender">
                Gender <span className="required">*</span>
              </label>
              <select
                id="reg-gender" className={`form-select ${errors.gender ? 'error' : ''}`}
                value={form.gender} onChange={e => set('gender', e.target.value)}
              >
                <option value="">Select gender…</option>
                {GENDER_OPTIONS.map(g => <option key={g} value={g}>{g}</option>)}
              </select>
              {errors.gender && <span className="form-error">⚠ {errors.gender}</span>}
            </div>

            {/* Contact */}
            <div className="grid-2">
              <div className="form-group">
                <label className="form-label" htmlFor="reg-phone">Contact Phone</label>
                <input
                  id="reg-phone" className="form-input" type="tel" placeholder="+91 98765 43210"
                  value={form.contact_phone} onChange={e => set('contact_phone', e.target.value)}
                />
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="reg-email">Contact Email</label>
                <input
                  id="reg-email" className={`form-input ${errors.contact_email ? 'error' : ''}`}
                  type="email" placeholder="patient@example.com"
                  value={form.contact_email} onChange={e => set('contact_email', e.target.value)}
                />
                {errors.contact_email && <span className="form-error">⚠ {errors.contact_email}</span>}
              </div>
            </div>

            {/* Language */}
            <div className="form-group">
              <label className="form-label" htmlFor="reg-lang">Preferred Language</label>
              <select
                id="reg-lang" className="form-select"
                value={form.preferred_language} onChange={e => set('preferred_language', e.target.value)}
              >
                {LANGUAGE_OPTIONS.map(l => <option key={l} value={l}>{l}</option>)}
              </select>
            </div>

            <hr className="divider" />

            <div className="flex gap-sm">
              <button type="submit" className="btn btn-primary btn-lg" disabled={loading} id="reg-submit">
                {loading ? <><span className="loader" /> Registering…</> : 'Register Patient →'}
              </button>
              <button type="button" className="btn btn-ghost" onClick={() => onNavigate('dashboard')}>
                Cancel
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
