/**
 * services/api.js
 * ----------------
 * Centralised API client. All fetch calls go through here.
 * VITE_API_BASE_URL is set in .env (defaults to empty string so Vite proxy works).
 */

const BASE = import.meta.env.VITE_API_BASE_URL || '';

function getToken() {
  return localStorage.getItem('token');
}

async function request(path, options = {}) {
  const token = getToken();
  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers || {}),
  };

  const res = await fetch(`${BASE}${path}`, { ...options, headers });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    const msg = body.detail || body.message || `HTTP ${res.status}`;
    throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
  }

  return res.json();
}

// ── Auth ───────────────────────────────────────────────────────────────────
export const authApi = {
  login: (username, password) =>
    request('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),
  me: () => request('/api/auth/me'),
};

// ── Health ─────────────────────────────────────────────────────────────────
export const healthApi = {
  check: () => request('/api/health'),
};

// ── Dashboard ──────────────────────────────────────────────────────────────
export const dashboardApi = {
  summary: () => request('/api/dashboard/summary'),
  cases: () => request('/api/dashboard/cases'),
};

// ── Patients ───────────────────────────────────────────────────────────────
export const patientsApi = {
  create: (data) => request('/api/patients', { method: 'POST', body: JSON.stringify(data) }),
  list: (search = '', page = 1) =>
    request(`/api/patients?search=${encodeURIComponent(search)}&page=${page}&page_size=20`),
  get: (id) => request(`/api/patients/${id}`),
  update: (id, data) =>
    request(`/api/patients/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
};

// ── Encounters ─────────────────────────────────────────────────────────────
export const encountersApi = {
  create: (data) => request('/api/encounters', { method: 'POST', body: JSON.stringify(data) }),
  list: (patientId) =>
    request(`/api/encounters${patientId ? `?patient_id=${patientId}` : ''}`),
  get: (id) => request(`/api/encounters/${id}`),
  update: (id, data) =>
    request(`/api/encounters/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
};

// ── Interviews ─────────────────────────────────────────────────────────────
export const interviewsApi = {
  nextQuestion: (encId) => request(`/api/interviews/${encId}/next-question`),
  submitResponse: (encId, questionKey, answer) =>
    request(`/api/interviews/${encId}/responses`, {
      method: 'POST',
      body: JSON.stringify({ question_key: questionKey, answer }),
    }),
  progress: (encId) => request(`/api/interviews/${encId}/progress`),
  resume: (encId) =>
    request(`/api/interviews/${encId}/resume`, { method: 'POST' }),
};

// ── Documents ──────────────────────────────────────────────────────────────
export const documentsApi = {
  upload: (patientId, formData) => {
    const token = getToken();
    return fetch(`${BASE}/api/documents/upload/${patientId}`, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: formData,
    }).then(async (res) => {
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Upload failed: ${res.status}`);
      }
      return res.json();
    });
  },
  get: (id) => request(`/api/documents/${id}`),
  extraction: (id) => request(`/api/documents/${id}/extraction`),
  review: (id) => request(`/api/documents/${id}/review`, { method: 'POST' }),
};

// ── Case Analysis ──────────────────────────────────────────────────────────
export const caseApi = {
  missingInfo: (encId) => request(`/api/encounters/${encId}/missing-information`),
  contradictions: (encId) => request(`/api/encounters/${encId}/contradictions`),
  readiness: (encId) => request(`/api/encounters/${encId}/readiness`),
  summary: (encId) => request(`/api/encounters/${encId}/summary`),
};
