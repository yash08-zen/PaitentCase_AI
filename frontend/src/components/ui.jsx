import { useEffect, useState } from "react";
import apiClient from "../api/client";

const P = {
  dashboard: "M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z",
  users: "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8M22 21v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8",
  plus: "M12 5v14M5 12h14", chat: "M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z",
  doc: "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M8 13h8M8 17h8",
  clip: "M9 3h6v4H9zM7 5H5a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2M8 13l3 3 5-6",
  logout: "M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9", search: "M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16zM21 21l-4.3-4.3",
  check: "M20 6 9 17l-5-5", alert: "M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0zM12 9v4M12 17h.01",
  arrow: "M7 17 17 7M7 7h10v10", reset: "M3 12a9 9 0 1 0 3-6.7L3 8M3 3v5h5",
  info: "M12 8v4M12 16h.01M22 12A10 10 0 1 1 2 12a10 10 0 0 1 20 0z",
  close: "M18 6 6 18M6 6l12 12"
};

export const Icon = ({ n, size = 18 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d={P[n] || P.doc} />
  </svg>
);

export const Logo = ({ light }) => (
  <span className={`logo ${light ? "light" : ""}`}>
    <svg viewBox="0 0 24 24" width="30" height="30" aria-hidden="true">
      <circle cx="12" cy="12" r="11" fill="currentColor" opacity=".16" />
      <rect x="10" y="4.5" width="4" height="15" rx="1.2" fill="currentColor" />
      <rect x="4.5" y="10" width="15" height="4" rx="1.2" fill="currentColor" />
    </svg>
    PatientCase AI
  </span>
);

const SRC = {
  patient: ["Patient-reported", "t-patient"],
  patient_reported: ["Patient-reported", "t-patient"],
  document: ["Document-extracted", "t-doc"],
  document_extracted_unverified: ["Document-extracted (unverified)", "t-doc"],
  system: ["System-generated", "t-sys"],
  verified: ["Clinician-verified", "t-ver"],
  doctor_verified: ["Doctor-verified", "t-ver"],
  missing_unknown: ["Not provided / unknown", "t-warn"],
};

export const Source = ({ s }) => (
  <span className={`tag ${SRC[s]?.[1] || "t-sys"}`}>
    {s === "verified" && <Icon n="check" size={12} />}
    {SRC[s]?.[0] || s}
  </span>
);

export const Tag = ({ kind = "sys", children }) => <span className={`tag t-${kind}`}>{children}</span>;

const STATUS = {
  "Needs review": "warn",
  "Ready for review": "patient",
  Finalized: "ver",
  "In interview": "doc",
  Registered: "sys",
};

export const StatusTag = ({ s }) => <Tag kind={STATUS[s] || "sys"}>{s}</Tag>;

export const Proto = ({ children = "Prototype demonstration: simulated" }) => (
  <span className="proto">{children}</span>
);

export function Ring({ value, size = 120, stroke = 12, label }) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  return (
    <div className="ring" style={{ width: size, height: size }} role="img" aria-label={`${label || "Score"} ${value} percent`}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--line)" strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="var(--g4)"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - value / 100)}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          style={{ transition: "stroke-dashoffset .5s" }}
        />
      </svg>
      <b>{value}%</b>
    </div>
  );
}

export const Bar = ({ value }) => (
  <div className="bar"><i style={{ width: `${value}%` }} /></div>
);

export const Empty = ({ title, text, action }) => (
  <div className="card empty">
    <h2>{title}</h2>
    <p className="soft">{text}</p>
    {action}
  </div>
);

/* ---------- Shared Frontend Primitives (M1) ---------- */

/**
 * Loading Spinner Primitive
 */
export const Spinner = ({ size = 20, text = "Loading..." }) => (
  <div className="spinner-container" role="status" aria-live="polite">
    <svg className="spinner-svg" width={size} height={size} viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" opacity="0.2" />
      <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
    {text && <span className="small soft">{text}</span>}
  </div>
);

/**
 * Empty State Primitive
 */
export const EmptyState = ({
  title = "No data found",
  text = "There are no records to display.",
  action = null,
  icon = "doc",
}) => (
  <div className="card empty" role="region" aria-label={title}>
    <div className="empty-icon">
      <Icon n={icon} size={30} />
    </div>
    <h2>{title}</h2>
    <p className="soft">{text}</p>
    {action && <div className="mt">{action}</div>}
  </div>
);

/**
 * Error Banner Primitive with optional retry action
 */
export const ErrorBanner = ({
  title = "An error occurred",
  message = "Please check your network connection or try again.",
  onRetry = null,
}) => (
  <div className="banner bad error-banner" role="alert">
    <Icon n="alert" size={20} />
    <div>
      <b>{title}</b>
      {message && <p className="small" style={{ margin: "2px 0 0" }}>{message}</p>}
    </div>
    {onRetry && (
      <button className="btn sm out" onClick={onRetry} type="button">
        Retry
      </button>
    )}
  </div>
);

/**
 * Toast Notification Primitive
 */
export const Toast = ({ toast, onDismiss }) => {
  if (!toast) return null;
  const isObj = typeof toast === "object";
  const message = isObj ? toast.message : toast;
  const type = isObj ? toast.type || "success" : "success";

  return (
    <div className={`toast toast-${type}`} role="status" aria-live="polite">
      <Icon n={type === "error" ? "alert" : "check"} size={16} />
      <span>{message}</span>
      {onDismiss && (
        <button
          onClick={onDismiss}
          style={{ background: "none", border: "none", color: "inherit", padding: 0, marginLeft: 8, cursor: "pointer", display: "grid", placeItems: "center" }}
          aria-label="Dismiss notification"
        >
          <Icon n="close" size={14} />
        </button>
      )}
    </div>
  );
};

/**
 * Mandatory Clinical Boundary Notice
 * "Prototype supporting clinician review — not a diagnostic tool"
 */
export const ClinicalNotice = () => (
  <div className="clinical-boundary-notice" role="note" aria-label="Clinical boundary notice">
    <div className="notice-content">
      <span className="notice-badge">CLINICAL NOTICE</span>
      <span className="notice-text">
        <strong>Prototype supporting clinician review — not a diagnostic tool.</strong> This application collects and organizes preliminary patient information. It does not diagnose, prescribe, recommend treatment, or calculate clinical risk. All findings require independent clinician verification.
      </span>
    </div>
  </div>
);

/**
 * Offline Workstation Banner Primitive (Milestone M11 / FR-13)
 * Alerts users when network connectivity is lost, reassuring them that
 * local workstation data is saved to SQLite and reminding them that cloud sync is disabled.
 */
export function OfflineBanner({ forceOffline = false, onDismiss = null }) {
  const [isOnline, setIsOnline] = useState(() => {
    if (typeof navigator !== "undefined" && typeof navigator.onLine === "boolean") {
      return navigator.onLine;
    }
    return true;
  });
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    const handleOnline = () => { setIsOnline(true); setDismissed(false); };
    const handleOffline = () => { setIsOnline(false); setDismissed(false); };
    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);
    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []);

  const show = forceOffline || (!isOnline && !dismissed);
  if (!show) return null;

  const handleDismiss = () => {
    setDismissed(true);
    if (onDismiss) onDismiss();
  };

  return (
    <div className="offline-banner" role="alert" aria-live="assertive">
      <div className="offline-banner-content">
        <span className="offline-badge">OFFLINE WORKSTATION</span>
        <span className="offline-text">
          <strong>Local Offline Mode Active.</strong> Operating on local clinic workstation with local SQLite database. All patient data, interview answers, and OCR extractions are safely saved to this device. (Remote cloud sync unavailable).
        </span>
      </div>
      <button
        type="button"
        className="offline-dismiss-btn"
        onClick={handleDismiss}
        aria-label="Dismiss offline banner"
      >
        Dismiss
      </button>
    </div>
  );
}

/**
 * Backend & Database Health Indicator
 * Displays real-time API and DB connectivity status in the app layout.
 */
export function HealthIndicator() {
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isOnline, setIsOnline] = useState(() => {
    if (typeof navigator !== "undefined" && typeof navigator.onLine === "boolean") {
      return navigator.onLine;
    }
    return true;
  });

  const fetchHealth = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiClient.checkHealth();
      setHealth(data);
    } catch (err) {
      setError(err.message || "Failed to reach backend");
      setHealth(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, 30000);
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);
    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);

    return () => {
      clearInterval(interval);
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []);

  const isHealthy = health?.status === "healthy" && health?.database === "connected";
  const stateClass = loading ? "busy" : isHealthy ? "healthy" : "offline";
  const title = loading
    ? "Checking backend health..."
    : isHealthy
    ? `Local Workstation: ${health?.service} (${health?.environment}) | DB: ${health?.database} (Local SQLite)`
    : `Backend Offline or Degraded: ${error || health?.database || "Unreachable"}`;

  return (
    <div
      className={`health-indicator ${stateClass}`}
      title={title}
      onClick={fetchHealth}
      role="status"
      tabIndex={0}
      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") fetchHealth(); }}
    >
      <span className="health-dot" />
      <span className="health-label">
        {loading
          ? "Checking API..."
          : isHealthy
          ? (isOnline ? "API Online (Local)" : "Local Offline DB")
          : "API Offline"}
      </span>
      <button
        type="button"
        className="health-refresh-btn"
        aria-label="Refresh backend health status"
        onClick={(e) => { e.stopPropagation(); fetchHealth(); }}
      >
        <Icon n="reset" size={12} />
      </button>
    </div>
  );
}

export const LoadingSpinner = Spinner;

