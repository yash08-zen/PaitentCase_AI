import { useState } from 'react';
import './LoginPage.css';

export default function LoginPage({ onLogin }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!username.trim() || !password.trim()) {
      setError('Please enter both username and password.');
      return;
    }
    setError('');
    setLoading(true);
    try {
      await onLogin(username.trim(), password);
    } catch (err) {
      setError(err.message || 'Login failed. Please check your credentials.');
    } finally {
      setLoading(false);
    }
  }

  function fillDemo(role) {
    const creds = {
      admin:   ['admin',   'Admin@1234'],
      doctor:  ['doctor',  'Doctor@1234'],
      staff:   ['staff',   'Staff@1234'],
      patient: ['patient', 'Patient@1234'],
    };
    const [u, p] = creds[role];
    setUsername(u); setPassword(p); setError('');
  }

  return (
    <div className="login-root">
      <div className="login-container">
        <div className="login-brand">
          <div className="login-logo">🏥</div>
          <h1 className="login-title">PatientCase AI</h1>
          <p className="login-subtitle">Adaptive Patient Case-Taking System</p>
        </div>

        <div className="login-card">
          <form className="login-form" onSubmit={handleSubmit} noValidate>
            <div className="form-group">
              <label className="form-label" htmlFor="login-username">
                Username <span className="required">*</span>
              </label>
              <input
                id="login-username"
                className={`form-input ${error ? 'error' : ''}`}
                type="text"
                placeholder="Enter username"
                value={username}
                onChange={e => setUsername(e.target.value)}
                autoComplete="username"
                autoFocus
              />
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="login-password">
                Password <span className="required">*</span>
              </label>
              <input
                id="login-password"
                className={`form-input ${error ? 'error' : ''}`}
                type="password"
                placeholder="Enter password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                autoComplete="current-password"
              />
            </div>

            {error && (
              <div className="alert alert-danger" role="alert">
                ⚠ {error}
              </div>
            )}

            <button
              id="login-submit"
              type="submit"
              className="btn btn-primary btn-lg btn-full"
              disabled={loading}
            >
              {loading ? <><span className="loader" /> Signing in…</> : '→ Sign In'}
            </button>
          </form>

          <div className="demo-creds">
            <p style={{ marginBottom: 8 }}>Quick demo sign-in:</p>
            {['admin','doctor','staff','patient'].map(role => (
              <button
                key={role}
                type="button"
                className="btn btn-ghost btn-sm"
                style={{ marginRight: 6, marginBottom: 4 }}
                onClick={() => fillDemo(role)}
              >
                {role.charAt(0).toUpperCase() + role.slice(1)}
              </button>
            ))}
          </div>
        </div>

        <div className="login-notice">
          ℹ️ This system assists with patient information collection and organization only.
          It does <strong>not</strong> diagnose diseases, prescribe medicines, or replace
          professional clinical judgment.
        </div>
      </div>
    </div>
  );
}
