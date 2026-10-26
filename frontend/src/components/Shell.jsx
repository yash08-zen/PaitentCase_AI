import { Icon, Logo, ClinicalNotice, HealthIndicator, Toast, OfflineBanner } from "./ui";
import { useStore } from "../state/store";

const ALL_NAV = [
  { key: "dashboard", label: "Dashboard", icon: "dashboard", roles: ["doctor", "staff", "admin"] },
  { key: "portal", label: "My Patient Portal", icon: "dashboard", roles: ["patient"] },
  { key: "patients", label: "Patients", icon: "users", roles: ["doctor", "staff", "admin"] },
  { key: "register", label: "Register patient", icon: "plus", roles: ["doctor", "staff", "admin"] },
  { key: "interview", label: "Adaptive interview", icon: "chat", roles: ["doctor", "staff", "admin", "patient"] },
  { key: "documents", label: "Documents", icon: "doc", roles: ["doctor", "staff", "admin", "patient"] },
  { key: "review", label: "Doctor review", icon: "clip", roles: ["doctor", "admin"] },
  { key: "audit", label: "Audit logs", icon: "shield", roles: ["admin"] },
];

export default function Shell({ user, page, go, onLogout, children }) {
  const { patients, activeId, setActiveId, query, setQuery, toast, resetDemo, notify, language, setLanguage, t, LANGUAGES } = useStore();

  const userRole = (user?.role || "doctor").toLowerCase();

  // Filter navigation items by role
  const visibleNav = ALL_NAV.filter((item) => item.roles.includes(userRole));

  const getInitials = (name) => {
    if (!name) return "PC";
    return name
      .split(" ")
      .map((part) => part[0])
      .join("")
      .toUpperCase()
      .slice(0, 2);
  };

  const getRoleBadge = (role) => {
    switch (role) {
      case "doctor":
        return { label: t("doctor"), class: "t-doc" };
      case "staff":
        return { label: t("clinicStaff"), class: "t-sys" };
      case "patient":
        return { label: t("patient"), class: "t-patient" };
      case "admin":
        return { label: t("admin"), class: "t-bad" };
      default:
        return { label: role, class: "t-sys" };
    }
  };

  const badge = getRoleBadge(userRole);

  return (
    <div className="app">
      <aside className="side">
        <Logo />
        <p className="label">{t("menu")}</p>
        <nav>
          {visibleNav.map((item) => (
            <button
              key={item.key}
              className={`nav ${page === item.key ? "on" : ""}`}
              onClick={() => go(item.key)}
              aria-current={page === item.key ? "page" : undefined}
            >
              <Icon n={item.icon} />
              {item.key === "portal" && userRole === "patient" ? (language === "en" ? "My Patient Portal" : t(item.key)) : (t(item.key) || item.label)}
            </button>
          ))}
        </nav>

        <p className="label">{t("general")}</p>
        <nav>
          {userRole !== "patient" && (
            <button className="nav" onClick={() => { resetDemo(); notify("Demo data reset"); }}>
              <Icon n="reset" />
              {t("resetDemo")}
            </button>
          )}
          <button className="nav" onClick={onLogout}>
            <Icon n="logout" />
            {t("logout")}
          </button>
        </nav>

        <div className="sidecard">
          <h3>PatientCase AI</h3>
          <p>{t("loginSubtitle")}</p>
        </div>
      </aside>

      <div className="main">
        <header className="top">
          {userRole !== "patient" ? (
            <>
              <label className="search">
                <Icon n="search" />
                <input
                  placeholder={t("searchPlaceholder")}
                  value={query}
                  onChange={(e) => { setQuery(e.target.value); go("patients"); }}
                  aria-label={t("searchPatients")}
                />
              </label>
              <label className="active">
                <span className="small soft">{t("activePatient")}</span>
                <select value={activeId} onChange={(e) => setActiveId(e.target.value)}>
                  {patients.map((p) => (
                    <option key={p.id} value={p.id}>{p.name}</option>
                  ))}
                </select>
              </label>
            </>
          ) : (
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <span className="tag t-patient">{t("patientPortalSession")}</span>
              <span className="small soft">{t("restrictedRecord")}</span>
            </div>
          )}

          <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: "0.8rem" }}>
            {/* Global Trilingual Switcher (English / हिन्दी / मराठी) */}
            <div
              className="lang-switcher-header"
              role="radiogroup"
              aria-label="Select preferred language"
              style={{
                display: "flex",
                alignItems: "center",
                gap: "0.25rem",
                background: "#f1f5f9",
                padding: "0.2rem 0.4rem",
                borderRadius: "8px",
                border: "1px solid var(--line)",
              }}
            >
              {LANGUAGES.map((l) => (
                <button
                  key={l.code}
                  type="button"
                  role="radio"
                  aria-checked={language === l.code}
                  className={`btn xs ${language === l.code ? "primary" : "ghost"}`}
                  style={{
                    padding: "0.2rem 0.5rem",
                    fontSize: "0.78rem",
                    minHeight: "auto",
                    fontWeight: language === l.code ? 700 : 500,
                  }}
                  onClick={() => setLanguage(l.code)}
                >
                  {l.native}
                </button>
              ))}
            </div>

            <HealthIndicator />
            <div className="me">
              <span className="avatar">{getInitials(user?.username || "Doctor")}</span>
              <div>
                <b>{user?.username || "Clinician"}</b>
                <p className="small">
                  <span className={`tag ${badge.class}`} style={{ fontSize: "0.7rem", padding: "0.1rem 0.4rem" }}>
                    {badge.label}
                  </span>
                </p>
              </div>
            </div>
          </div>
        </header>

        <OfflineBanner />
        <ClinicalNotice />

        <section className="panel">
          {children}
        </section>
      </div>

      <Toast toast={toast} onDismiss={() => notify(null)} />
    </div>
  );
}

