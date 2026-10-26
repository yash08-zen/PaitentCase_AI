/**
 * src/api/client.js
 * Centralized, typed API client for PatientCase AI.
 * 
 * Features:
 *  - Base URL from VITE_API_BASE_URL (defaults to http://127.0.0.1:8000)
 *  - JSON request/response handling
 *  - Normalized error handling (Network errors, 4xx client errors, 5xx server errors)
 *  - Auth header injection (JWT bearer token support)
 *  - Session expiry listener and auto-redirect handling
 *  - Built-in health check helper
 */

export class ApiError extends Error {
  /**
   * @param {string} message - Normalized user-friendly error message
   * @param {number} status - HTTP status code (0 for network error)
   * @param {any} [data] - Parsed server payload or error details
   * @param {boolean} [isNetworkError=false] - True if request failed before server response
   */
  constructor(message, status = 0, data = null, isNetworkError = false) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
    this.isNetworkError = isNetworkError;

    if (isNetworkError) {
      this.code = "NETWORK_ERROR";
    } else if (status >= 500) {
      this.code = "SERVER_ERROR";
    } else if (status === 401) {
      this.code = "UNAUTHORIZED";
    } else if (status === 403) {
      this.code = "FORBIDDEN";
    } else if (status === 404) {
      this.code = "NOT_FOUND";
    } else if (status === 422) {
      this.code = "VALIDATION_ERROR";
    } else {
      this.code = "CLIENT_ERROR";
    }
  }
}

/**
 * Normalizes error responses from the backend or network failures.
 * @param {Response} response
 * @returns {Promise<never>}
 */
async function handleHttpError(response) {
  const status = response.status;
  let parsed = null;
  let rawText = "";

  try {
    rawText = await response.text();
    if (rawText) {
      try {
        parsed = JSON.parse(rawText);
      } catch {
        parsed = rawText;
      }
    }
  } catch {
    // ignore read error
  }

  let message = "";
  if (parsed && typeof parsed === "object") {
    if (Array.isArray(parsed.errors) && parsed.errors.length > 0) {
      const errList = parsed.errors
        .map((err) => `${err.field}: ${err.message}`)
        .join("; ");
      message = typeof parsed.detail === "string" ? `${parsed.detail} (${errList})` : errList;
    } else if (typeof parsed.detail === "string") {
      message = parsed.detail;
    } else if (Array.isArray(parsed.detail)) {
      message = parsed.detail
        .map((err) => {
          const field = Array.isArray(err.loc) ? err.loc.slice(1).join(".") : "field";
          return field ? `${field}: ${err.msg}` : err.msg;
        })
        .join("; ");
    } else if (parsed.message) {
      message = parsed.message;
    }
  }

  if (!message) {
    if (status === 401) {
      message = "Authentication required. Please log in.";
    } else if (status === 403) {
      message = "Access forbidden. You do not have permission to perform this action.";
    } else if (status === 404) {
      message = "The requested resource was not found.";
    } else if (status === 422) {
      message = "Invalid input provided. Please verify all required fields.";
    } else if (status === 429) {
      const retryAfter = response.headers.get("retry-after");
      message = retryAfter
        ? `Rate limit exceeded. Please wait ${retryAfter} seconds before retrying.`
        : "Rate limit exceeded. Please wait a moment before retrying.";
    } else if (status >= 500) {
      message = `Server error (${status}). Please try again later or contact support.`;
    } else {
      message = response.statusText || `Request failed with status code ${status}.`;
    }
  }

  throw new ApiError(message, status, parsed, false);
}

export class ApiClient {
  /**
   * @param {Object} [config]
   * @param {string} [config.baseUrl]
   * @param {Function} [config.fetchFn]
   * @param {() => string|null} [config.getToken]
   */
  constructor({ baseUrl, fetchFn, getToken } = {}) {
    if (baseUrl) {
      this.baseUrl = baseUrl.replace(/\/$/, "");
    } else if (typeof import.meta !== "undefined" && import.meta.env?.VITE_API_BASE_URL) {
      this.baseUrl = import.meta.env.VITE_API_BASE_URL.replace(/\/$/, "");
    } else {
      this.baseUrl = "http://127.0.0.1:8000";
    }

    this._fetch = fetchFn || (typeof window !== "undefined" ? window.fetch.bind(window) : globalThis.fetch);
    this._token = null;
    this._user = null;
    this._customGetToken = getToken || null;
    this._onUnauthorized = null;
  }

  /**
   * Register a callback to invoke when session expires (401 response on protected endpoint)
   * @param {(message: string) => void} callback
   */
  setOnUnauthorized(callback) {
    this._onUnauthorized = callback;
  }

  /**
   * Set JWT auth token for subsequent requests
   * @param {string|null} token
   */
  setToken(token) {
    this._token = token;
    if (!token) {
      this._user = null;
    }
    if (typeof window !== "undefined" && window.localStorage) {
      if (token) {
        window.localStorage.setItem("pc_auth_token", token);
      } else {
        window.localStorage.removeItem("pc_auth_token");
        window.localStorage.removeItem("pc_user");
      }
    }
  }

  /**
   * Retrieve active token
   * @returns {string|null}
   */
  getToken() {
    if (this._customGetToken) {
      return this._customGetToken();
    }
    if (this._token) {
      return this._token;
    }
    if (typeof window !== "undefined" && window.localStorage) {
      return window.localStorage.getItem("pc_auth_token");
    }
    return null;
  }

  /**
   * Store user profile
   * @param {Object|null} user
   */
  setUser(user) {
    this._user = user;
    if (typeof window !== "undefined" && window.localStorage) {
      if (user) {
        window.localStorage.setItem("pc_user", JSON.stringify(user));
      } else {
        window.localStorage.removeItem("pc_user");
      }
    }
  }

  /**
   * Get stored user profile
   * @returns {Object|null}
   */
  getUser() {
    if (this._user) {
      return this._user;
    }
    if (typeof window !== "undefined" && window.localStorage) {
      const u = window.localStorage.getItem("pc_user");
      if (u) {
        try {
          return JSON.parse(u);
        } catch {
          return null;
        }
      }
    }
    return null;
  }

  /**
   * Authenticate with backend and store access token and user
   * @param {string} username
   * @param {string} password
   */
  async login(username, password) {
    const res = await this.post("/api/auth/login", { username, password });
    if (res?.access_token) {
      this.setToken(res.access_token);
      if (res.user) {
        this.setUser(res.user);
      }
    }
    return res;
  }

  /**
   * Self-register a new patient and store access token & user session
   * @param {Object} payload
   */
  async selfRegister(payload) {
    const res = await this.post("/api/patients/self-register", payload);
    if (res?.access_token) {
      this.setToken(res.access_token);
      if (res.user) {
        this.setUser(res.user);
      }
    }
    return res;
  }

  /**
   * Retrieve current authenticated patient profile
   */
  async getMyPatientProfile() {
    return this.get("/api/patients/me");
  }

  /**
   * Logout from backend and clear stored session
   */
  async logout() {
    try {
      if (this.getToken()) {
        await this.post("/api/auth/logout");
      }
    } catch {
      // Ignore network/server errors during logout cleanup
    } finally {
      this.setToken(null);
      this.setUser(null);
    }
  }

  /**
   * Core request dispatcher with normalized error handling
   * @param {string} endpoint - Path relative to baseUrl, e.g. "/api/health" or "api/health"
   * @param {RequestInit} [options]
   * @returns {Promise<any>}
   */
  async request(endpoint, options = {}) {
    const cleanEndpoint = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;
    const url = `${this.baseUrl}${cleanEndpoint}`;

    const headers = new Headers(options.headers || {});
    if (!headers.has("Accept")) {
      headers.set("Accept", "application/json");
    }

    const token = this.getToken();
    if (token && !headers.has("Authorization")) {
      headers.set("Authorization", `Bearer ${token}`);
    }

    let body = options.body;
    if (body && typeof body === "object" && !(body instanceof FormData) && !(body instanceof Blob)) {
      headers.set("Content-Type", "application/json");
      body = JSON.stringify(body);
    }

    let response;
    const timeoutMs = options.timeoutMs || 30000;
    const controller = typeof AbortController !== "undefined" ? new AbortController() : null;
    let timeoutId = null;
    if (controller && timeoutMs > 0 && !options.signal) {
      timeoutId = setTimeout(() => controller.abort(), timeoutMs);
    }

    try {
      response = await this._fetch(url, {
        ...options,
        headers,
        body,
        signal: options.signal || (controller ? controller.signal : undefined),
      });
    } catch (err) {
      if (err?.name === "AbortError") {
        throw new ApiError(
          "Request timed out. The server took too long to respond.",
          408,
          err,
          true
        );
      }
      throw new ApiError(
        "Network error: Unable to reach the backend server. Please check your connection and verify the server is running.",
        0,
        err,
        true
      );
    } finally {
      if (timeoutId) clearTimeout(timeoutId);
    }

    if (!response.ok) {
      if (response.status === 401 && !cleanEndpoint.includes("/api/auth/login")) {
        if (typeof this._onUnauthorized === "function") {
          this._onUnauthorized("Your session has expired. Please log in again.");
        }
      }
      return await handleHttpError(response);
    }

    // 204 No Content
    if (response.status === 204) {
      return null;
    }

    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      return await response.json();
    }

    return await response.text();
  }

  /**
   * HTTP GET
   * @param {string} endpoint
   * @param {RequestInit} [options]
   */
  get(endpoint, options = {}) {
    return this.request(endpoint, { ...options, method: "GET" });
  }

  /**
   * HTTP POST
   * @param {string} endpoint
   * @param {any} body
   * @param {RequestInit} [options]
   */
  post(endpoint, body, options = {}) {
    return this.request(endpoint, { ...options, method: "POST", body });
  }

  /**
   * HTTP PUT
   * @param {string} endpoint
   * @param {any} body
   * @param {RequestInit} [options]
   */
  put(endpoint, body, options = {}) {
    return this.request(endpoint, { ...options, method: "PUT", body });
  }

  /**
   * HTTP DELETE
   * @param {string} endpoint
   * @param {RequestInit} [options]
   */
  delete(endpoint, options = {}) {
    return this.request(endpoint, { ...options, method: "DELETE" });
  }

  /**
   * Check backend and database health status
   * @returns {Promise<{ status: string, app: string, database: string, environment: string }>}
   */
  async checkHealth() {
    try {
      return await this.get("/health");
    } catch (err) {
      return await this.get("/api/health");
    }
  }

  // ── Adaptive Interview (M4) ──────────────────────────────────────────────

  /**
   * Fetch the next unanswered applicable question for an encounter
   * @param {number|string} encounterId
   */
  async getNextQuestion(encounterId) {
    return this.get(`/api/interviews/${encounterId}/next-question`);
  }

  /**
   * Submit or update an answer for an encounter
   * @param {number|string} encounterId
   * @param {string} questionKey
   * @param {string} answer
   * @param {string} [source="patient_reported"]
   * @param {string} [confirmationStatus="confirmed"]
   */
  async submitResponse(encounterId, questionKey, answer, source = "patient_reported", confirmationStatus = "confirmed") {
    return this.post(`/api/interviews/${encounterId}/responses`, {
      question_key: questionKey,
      answer: String(answer),
      source,
      confirmation_status: confirmationStatus,
    });
  }

  /**
   * Navigate back: remove the last response and return the previous question
   * @param {number|string} encounterId
   */
  async backQuestion(encounterId) {
    return this.post(`/api/interviews/${encounterId}/back`);
  }

  /**
   * Get detailed interview progress, active path, and skipped questions
   * @param {number|string} encounterId
   */
  async getInterviewProgress(encounterId) {
    return this.get(`/api/interviews/${encounterId}/progress`);
  }

  /**
   * Resume an interrupted interview session
   * @param {number|string} encounterId
   */
  async resumeInterview(encounterId) {
    return this.post(`/api/interviews/${encounterId}/resume`);
  }

  /**
   * Get all answered questions with human-readable labels for review
   * @param {number|string} encounterId
   */
  async getInterviewAnswers(encounterId) {
    return this.get(`/api/interviews/${encounterId}/answers`);
  }

  /**
   * Complete the interview once all required applicable questions are answered
   * @param {number|string} encounterId
   */
  async completeInterview(encounterId) {
    return this.post(`/api/interviews/${encounterId}/complete`);
  }

  // --- Case Summary & Analysis (M5) ---

  /**
   * Fetch structured case summary with per-field provenance
   * @param {number|string} encounterId
   */
  async getCaseSummary(encounterId) {
    return this.get(`/api/encounters/${encounterId}/summary`);
  }

  /**
   * Fetch checklist of required fields that are missing or incomplete
   * @param {number|string} encounterId
   */
  async getMissingInformation(encounterId) {
    return this.get(`/api/encounters/${encounterId}/missing`);
  }

  /**
   * Fetch case data completeness score, factor breakdown, and review label
   * @param {number|string} encounterId
   */
  async getCaseReadiness(encounterId) {
    return this.get(`/api/encounters/${encounterId}/readiness`);
  }

  // --- Document & Prescription OCR (M6) ---

  /**
   * Upload a prescription or medical document for real OCR processing
   * @param {number|string} patientId
   * @param {File|Blob} file
   * @param {number|string} [encounterId]
   * @param {string} [documentType="prescription"]
   */
  async uploadDocument(patientId, file, encounterId = null, documentType = "prescription") {
    const formData = new FormData();
    formData.append("file", file);
    if (encounterId) {
      formData.append("encounter_id", String(encounterId));
    }
    formData.append("document_type", documentType);

    return this.post(`/api/documents/upload/${patientId}`, formData);
  }

  /**
   * List documents with optional filters
   * @param {Object} [params]
   * @param {number|string} [params.patientId]
   * @param {number|string} [params.encounterId]
   * @param {string} [params.documentType]
   */
  async listDocuments({ patientId, encounterId, documentType } = {}) {
    const query = new URLSearchParams();
    if (patientId) query.set("patient_id", String(patientId));
    if (encounterId) query.set("encounter_id", String(encounterId));
    if (documentType) query.set("document_type", documentType);
    const qs = query.toString();
    return this.get(`/api/documents${qs ? `?${qs}` : ""}`);
  }

  /**
   * Get extraction status and parsed text for a document
   * @param {number|string} documentId
   */
  async getDocumentExtraction(documentId) {
    return this.get(`/api/documents/${documentId}/extraction`);
  }

  /**
   * Get full document metadata
   * @param {number|string} documentId
   */
  async getDocument(documentId) {
    return this.get(`/api/documents/${documentId}`);
  }

  /**
   * Fetch authenticated file blob for viewing/downloading protected uploads
   * @param {number|string} documentId
   * @returns {Promise<Blob>}
   */
  async getDocumentFileBlob(documentId) {
    const token = this.getToken();
    const headers = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const res = await this._fetch(`${this.baseUrl}/api/documents/${documentId}/file`, { headers });
    if (!res.ok) {
      throw new Error(`Failed to fetch document file: ${res.statusText}`);
    }
    return res.blob();
  }

  // --- Clinical Discrepancies & Contradictions (M7) ---

  /**
   * List conflicts for an encounter with optional status filter and rule re-evaluation
   * @param {number|string} encounterId
   * @param {Object} [options]
   * @param {string} [options.status] - open | resolved | dismissed
   * @param {boolean} [options.refresh] - whether to re-evaluate discrepancy rules
   */
  async listConflicts(encounterId, { status, refresh = false } = {}) {
    const params = new URLSearchParams({ encounter_id: String(encounterId) });
    if (status) params.set("status", status);
    if (refresh) params.set("refresh", "true");
    return this.get(`/api/conflicts?${params.toString()}`);
  }

  /**
   * Fetch detected contradictions for an encounter
   * @param {number|string} encounterId
   */
  async getContradictions(encounterId) {
    return this.get(`/api/encounters/${encounterId}/contradictions`);
  }

  /**
   * Clinician resolves or dismisses an information discrepancy
   * @param {number|string} conflictId
   * @param {Object} payload
   * @param {"resolved"|"dismissed"} payload.status
   * @param {string} payload.resolutionNote
   */
  async resolveConflict(conflictId, { status = "resolved", resolutionNote = "Clinician reviewed and resolved discrepancy." } = {}) {
    return this.put(`/api/conflicts/${conflictId}/resolve`, {
      status,
      resolution_note: resolutionNote,
    });
  }

  // --- Doctor Review & Dashboard (M8) ---

  /**
   * Save or update clinician notes for an encounter
   * @param {number|string} encounterId
   * @param {string} notes
   */
  async saveDoctorNotes(encounterId, notes) {
    return this.put(`/api/encounters/${encounterId}/notes`, {
      doctor_notes: notes,
    });
  }

  /**
   * Retrieve clinician notes for an encounter
   * @param {number|string} encounterId
   */
  async getDoctorNotes(encounterId) {
    return this.get(`/api/encounters/${encounterId}/notes`);
  }

  /**
   * Finalize review of an intake case
   * @param {number|string} encounterId
   * @param {string} [notes]
   */
  async finalizeCase(encounterId, notes) {
    return this.post(`/api/encounters/${encounterId}/finalize`, {
      doctor_notes: notes || null,
    });
  }

  /**
   * Retrieve clinical dashboard summary statistics
   */
  async getDashboardSummary() {
    return this.get("/api/dashboard/summary");
  }

  /**
   * Retrieve dashboard cases queue with optional status and search filters
   * @param {Object} [params]
   * @param {string} [params.status] - needs_review | all | reviewed | active
   * @param {string} [params.search]
   */
  async getDashboardCases({ status, search } = {}) {
    const params = new URLSearchParams();
    if (status) params.set("status", status);
    if (search) params.set("search", search);
    const qs = params.toString();
    return this.get(`/api/dashboard/cases${qs ? `?${qs}` : ""}`);
  }

  // --- System & Offline Operation (M11) ---

  /**
   * Retrieve offline workstation operational status and metadata
   */
  async getOfflineStatus() {
    return this.get("/api/system/offline-status");
  }

  /**
   * Safe sync probe (verifies that remote sync is safely rejected to avoid silent overwrite)
   */
  async rejectSync() {
    return this.post("/api/system/sync", {});
  }

  /**
   * Verify local SQLite database file integrity
   */
  async verifyDatabaseIntegrity() {
    return this.get("/api/system/backup/verify");
  }

  // --- Multilingual Voice Assistant (M12) ---

  /**
   * List verified supported languages
   */
  async getVoiceLanguages() {
    return this.get("/api/voice/languages");
  }

  /**
   * Retrieve localized question text, help, and audio prompt
   * @param {string} questionKey
   * @param {string} [lang] - en | hi | mr
   */
  async getQuestionTranslation(questionKey, lang = "en") {
    return this.get(`/api/voice/questions/${questionKey}?lang=${encodeURIComponent(lang)}`);
  }

  /**
   * Parse spoken transcript into candidate answer and determine confirmation requirement
   * @param {Object} payload
   * @param {string} payload.transcript
   * @param {string} payload.question_key
   * @param {string} [payload.language]
   * @param {number} [payload.confidence]
   */
  async parseVoiceTranscript(payload) {
    return this.post("/api/voice/parse-transcript", payload);
  }

  /**
   * Set preferred encounter language
   * @param {number|string} encounterId
   * @param {string} language - English | Hindi | Marathi
   */
  async setEncounterLanguage(encounterId, language) {
    return this.post(`/api/voice/encounters/${encounterId}/language`, { language });
  }

  /**
   * Retrieve empirical benchmark summary metrics for OCR and speech
   */
  async getBenchmarksSummary() {
    return this.get("/api/system/benchmarks/summary");
  }
}

export const apiClient = new ApiClient();
export default apiClient;
