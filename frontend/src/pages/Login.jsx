import { useState } from "react";
import { useStore } from "../state/store";
import { Icon, Logo, ClinicalNotice, HealthIndicator, Spinner, ErrorBanner } from "../components/ui";
import apiClient, { ApiError } from "../api/client";

// Role id -> translation key (the staff role is translated as "clinicStaff")
const ROLE_KEY = { doctor: "doctor", staff: "clinicStaff", patient: "patient", admin: "admin" };

const DEMO_PRESETS = [
  {
    role: "doctor",
    label: "Doctor",
    username: "doctor",
    password: "Doctor@1234",
    desc: {
      en: "Review case summaries, verify medication conflicts, and complete review.",
      hi: "केस सारांश की समीक्षा करें और दवाओं के टकराव का समाधान करें।",
      mr: "केस सारांशाचे पुनरावलोकन करा आणि औषध विसंगती सोडवा.",
    },
  },
  {
    role: "staff",
    label: "Clinic Staff",
    username: "staff",
    password: "Staff@1234",
    desc: {
      en: "Register arriving patients and manage intake document uploads.",
      hi: "आने वाले मरीज़ों का पंजीकरण करें और दस्तावेज़ अपलोड प्रबंधित करें।",
      mr: "येणाऱ्या रुग्णांची नोंदणी करा आणि दस्तऐवज अपलोड व्यवस्थापित करा.",
    },
  },
  {
    role: "patient",
    label: "Patient",
    username: "patient",
    password: "Patient@1234",
    desc: {
      en: "Complete guided symptom interview and review personal records.",
      hi: "लक्षणों के प्रश्नों के उत्तर दें और अपने स्वास्थ्य रिकॉर्ड देखें।",
      mr: "लक्षणांच्या प्रश्नांची उत्तरे द्या आणि स्वतःचे आरोग्य रेकॉर्ड पहा.",
    },
  },
  {
    role: "admin",
    label: "Administrator",
    username: "admin",
    password: "Admin@1234",
    desc: {
      en: "Manage clinic user accounts, security controls, and audit trails.",
      hi: "उपयोगकर्ता खाते, सुरक्षा नियंत्रण और ऑडिट लॉग प्रबंधित करें।",
      mr: "वापरकर्ता खाती, सुरक्षा नियंत्रणे आणि ऑडिट नोंदी व्यवस्थापित करा.",
    },
  },
];

export default function Login({ onLogin, sessionMessage }) {
  const store = useStore();
  const language = store?.language || "en";
  const setLanguage = store?.setLanguage || (() => {});
  const t = store?.t || ((k) => (k === "loginTitle" ? "Welcome to PatientCase AI" : k === "loginSubtitle" ? "Adaptive pre-consultation case-taking, with a structured, review-ready case waiting for the doctor." : k === "boundaryText" ? "Prototype supporting clinician review — not a diagnostic tool. This application collects and organizes preliminary patient information." : k === "signInTab" ? "Sign In" : k === "signUpTab" ? "New Patient Sign Up" : k === "quickDemoRoles" ? "Quick Demo Role Credentials:" : k === "existingPatientNotice" ? "Sign in to an existing hospital patient account." : k === "createAccountLink" ? "Create New Patient Account →" : k === "username" ? "Username" : k === "password" ? "Password" : k === "signInButton" ? "Log in as" : k === "signingIn" ? "Authenticating..." : k === "newPatientPrompt" ? "First time visiting this hospital?" : k === "alreadyRegisteredPrompt" ? "Already registered at this hospital?" : k === "signInLink" ? "Sign In with Hospital ID / Password →" : k === "prefLang" ? "Preferred Language" : k === "selectLanguage" ? "Language / भाषा" : k === "fullName" ? "Full Name" : k === "fullNamePlaceholder" ? "e.g. Meera Kulkarni" : k === "age" ? "Age" : k === "agePlaceholder" ? "e.g. 34" : k === "gender" ? "Gender" : k === "genderSelect" ? "Select" : k === "female" ? "Female" : k === "male" ? "Male" : k === "other" ? "Other" : k === "phone" ? "Contact Phone (Optional)" : k === "phonePlaceholder" ? "10-digit mobile number" : k === "chiefComplaint" ? "Reason for Visit / Symptoms" : k === "complaintPlaceholder" ? "e.g. Fever and dry cough for 3 days" : k === "consentAgreement" ? "I consent to pre-consultation case-taking, medical document OCR, and physician review." : k === "registerButton" ? "Register & Start Intake" : k === "registering" ? "Registering new patient..." : k));
  const LANGUAGES = store?.LANGUAGES || [
    { code: "en", name: "English", native: "English", locale: "en-IN" },
    { code: "hi", name: "Hindi", native: "हिन्दी", locale: "hi-IN" },
    { code: "mr", name: "Marathi", native: "मराठी", locale: "mr-IN" },
  ];
  const [authMode, setAuthMode] = useState("signin"); // "signin" | "signup"

  // Sign In state
  const [username, setUsername] = useState("doctor");
  const [password, setPassword] = useState("Doctor@1234");
  const [selectedRole, setSelectedRole] = useState("doctor");

  // Sign Up state (New Patient Self-Registration)
  const [signupForm, setSignupForm] = useState({
    name: "",
    age: "",
    gender: "",
    phone: "",
    language: language === "hi" ? "Hindi" : language === "mr" ? "Marathi" : "English",
    complaint: "",
    consent: false,
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  // Generated login details shown once after self sign-up
  const [newCredentials, setNewCredentials] = useState(null);

  const handleLanguageChange = (langCode, langLabel) => {
    setLanguage(langCode);
    setSignupForm((f) => ({ ...f, language: langLabel || (langCode === "hi" ? "Hindi" : langCode === "mr" ? "Marathi" : "English") }));
  };

  const handlePresetSelect = (preset) => {
    setSelectedRole(preset.role);
    setUsername(preset.username);
    setPassword(preset.password);
    setError(null);
  };

  const handleSignIn = async (e) => {
    e.preventDefault();
    if (!username.trim() || !password) {
      setError(language === "hi" ? "कृपया यूज़रनेम और पासवर्ड दोनों दर्ज करें।" : language === "mr" ? "कृपया युझरनेम आणि पासवर्ड दोन्ही प्रविष्ट करा." : "Please provide both username and password.");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const res = await apiClient.login(username.trim(), password);
      if (onLogin) {
        onLogin(res.user);
      }
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError(language === "hi" ? "लॉग इन विफल रहा। कृपया नेटवर्क कनेक्शन जांचें।" : language === "mr" ? "लॉगिन अयशस्वी झाले. कृपया नेटवर्क तपासा." : "Login failed. Please check network connection and try again.");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleSignUp = async (e) => {
    e.preventDefault();
    setError(null);

    if (!signupForm.name.trim()) {
      setError(language === "hi" ? "कृपया अपना पूरा नाम दर्ज करें।" : language === "mr" ? "कृपया आपले पूर्ण नाव प्रविष्ट करा." : "Please enter your full name.");
      return;
    }
    if (signupForm.name.trim().length < 2) {
      setError(language === "hi" ? "नाम कम से कम 2 अक्षरों का होना चाहिए।" : language === "mr" ? "नाव किमान 2 अक्षरांचे असणे आवश्यक आहे." : "Full name must be at least 2 characters.");
      return;
    }
    if (!signupForm.age || Number(signupForm.age) < 0 || Number(signupForm.age) > 125) {
      setError(language === "hi" ? "कृपया 0 से 125 के बीच मान्य उम्र दर्ज करें।" : language === "mr" ? "कृपया 0 ते 125 दरम्यान वैध वय प्रविष्ट करा." : "Please enter a valid age between 0 and 125.");
      return;
    }
    if (!signupForm.gender) {
      setError(language === "hi" ? "कृपया अपना लिंग चुनें।" : language === "mr" ? "कृपया लिंग निवडा." : "Please select a gender option.");
      return;
    }
    if (signupForm.phone) {
      const digits = signupForm.phone.replace(/\D/g, "");
      if (digits.length < 7 || digits.length > 15) {
        setError(language === "hi" ? "कृपया 7-15 अंकों का मान्य फ़ोन नंबर दर्ज करें।" : language === "mr" ? "कृपया 7-15 अंकांचा वैध फोन नंबर प्रविष्ट करा." : "Please enter a valid phone number (7-15 digits).");
        return;
      }
    }
    if (!signupForm.consent) {
      setError(language === "hi" ? "नए मरीज़ के पंजीकरण से पहले सूचित सहमति आवश्यक है।" : language === "mr" ? "नवीन रुग्ण नोंदणीपूर्वी माहितीपूर्ण संमती आवश्यक आहे." : "Informed consent is required before registering as a new patient.");
      return;
    }

    setLoading(true);
    try {
      const payload = {
        full_name: signupForm.name.trim(),
        age: Number(signupForm.age),
        gender: signupForm.gender,
        contact_phone: signupForm.phone ? signupForm.phone.trim() : null,
        preferred_language: signupForm.language,
        chief_complaint: signupForm.complaint ? signupForm.complaint.trim() : null,
        consent_given: true,
      };

      const res = await apiClient.selfRegister(payload);
      // Show the generated login details before entering the portal
      setNewCredentials({
        user: res.user,
        name: res.patient?.full_name,
        username: res.username || res.user?.username,
        password: res.temporary_password,
      });
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError(language === "hi" ? "पंजीकरण विफल रहा। कृपया नेटवर्क कनेक्शन जांचें।" : language === "mr" ? "नोंदणी अयशस्वी झाली. कृपया नेटवर्क तपासा." : "Registration failed. Please check network connection and try again.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login">
      <div className="login-art">
        <Logo light />
        <div>
          <h1>{t("loginTitle")}</h1>
          <p>
            {t("loginSubtitle")}
          </p>
        </div>
        <ul>
          {[
            language === "hi" ? "4 क्लिनिकल भूमिकाओं के लिए भूमिका-आधारित पहुँच" : language === "mr" ? "4 वैद्यकीय भूमिकांसाठी भूमिका-आधारित प्रवेश" : "Role-based access for 4 clinical roles",
            language === "hi" ? "पूर्ण ऑडिट नोंदीसह अनुकूली नियम इंजिन" : language === "mr" ? "संपूर्ण ऑडिट नोंदीसह अनुकूली नियम इंजिन" : "Deterministic adaptive rule engine with full audit logging",
            language === "hi" ? "चिकित्सक समीक्षा में सहायक प्रोटोटाइप — निदान उपकरण नहीं" : language === "mr" ? "डॉक्टर पुनरावलोकनात सहाय्यक प्रोटोटाइप — निदान साधन नाही" : "Prototype supporting clinician review - not a diagnostic tool",
          ].map((text, idx) => (
            <li key={idx}>
              <Icon n="check" size={14} />
              {text}
            </li>
          ))}
        </ul>
      </div>

      <div className="login-form">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%", marginBottom: "0.5rem" }}>
          <Logo />
          <HealthIndicator />
        </div>

        {/* Global Language Switcher in Login Card */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            background: "#f0f4f2",
            padding: "0.35rem 0.6rem",
            borderRadius: "8px",
            marginBottom: "0.6rem",
          }}
        >
          <span style={{ fontSize: "0.78rem", fontWeight: 600, color: "var(--fg-soft)" }}>
            <Icon n="globe" size={14} style={{ verticalAlign: "middle", marginRight: "4px" }} />
            {t("selectLanguage")}:
          </span>
          <div style={{ display: "flex", gap: "0.3rem" }}>
            {LANGUAGES.map((l) => (
              <button
                key={l.code}
                type="button"
                className={`btn sm ${language === l.code ? "primary" : "ghost"}`}
                onClick={() => handleLanguageChange(l.code, l.name)}
                style={{ padding: "0.2rem 0.5rem", fontSize: "0.75rem", fontWeight: language === l.code ? 700 : 500 }}
              >
                {l.native}
              </button>
            ))}
          </div>
        </div>

        <ClinicalNotice />

        {/* Tab Navigation: Sign In vs New Patient Sign Up */}
        <div
          role="tablist"
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: "0.4rem",
            marginTop: "0.8rem",
            marginBottom: "0.8rem",
            background: "#edf2f0",
            padding: "0.3rem",
            borderRadius: "10px",
          }}
        >
          <button
            type="button"
            role="tab"
            aria-selected={authMode === "signin"}
            className={`btn sm ${authMode === "signin" ? "primary" : "ghost"}`}
            onClick={() => {
              setAuthMode("signin");
              setError(null);
            }}
            style={{ fontWeight: 600, fontSize: "0.84rem" }}
          >
            {t("signInTab")}
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={authMode === "signup"}
            className={`btn sm ${authMode === "signup" ? "primary" : "ghost"}`}
            onClick={() => {
              setAuthMode("signup");
              setError(null);
            }}
            style={{ fontWeight: 600, fontSize: "0.84rem" }}
          >
            {t("signUpTab")}
          </button>
        </div>

        {sessionMessage && (
          <div className="banner" style={{ background: "var(--amberbg)", color: "var(--amber)", marginTop: "0.5rem" }}>
            <Icon n="warn" size={16} />
            <div className="small" style={{ fontWeight: 600 }}>{sessionMessage}</div>
          </div>
        )}

        {error && (
          <ErrorBanner
            message={error}
            onDismiss={() => setError(null)}
          />
        )}

        {newCredentials ? (
          <div className="card" role="region" aria-label={t("yourLoginDetails")} style={{ padding: "1.4rem" }}>
            <span className="okcircle" style={{ marginBottom: "0.6rem" }}>
              <Icon n="check" size={22} />
            </span>
            <h2 style={{ margin: "0.3rem 0", fontSize: "1.3rem" }}>{t("accountCreated")}</h2>
            <p className="soft" style={{ marginTop: 0 }}>{t("saveCredentialsHint")}</p>
            <div style={{ background: "#f4f7f4", border: "1px solid var(--line)", borderRadius: 10, padding: "0.9rem 1rem", margin: "0.8rem 0" }}>
              <div className="small soft">{t("username")}</div>
              <b style={{ fontFamily: "ui-monospace, monospace", fontSize: "1.05rem" }} data-testid="new-username">{newCredentials.username}</b>
              <div className="small soft" style={{ marginTop: "0.6rem" }}>{t("password")}</div>
              <b style={{ fontFamily: "ui-monospace, monospace", fontSize: "1.05rem" }} data-testid="new-password">{newCredentials.password}</b>
            </div>
            <div className="actions">
              <button
                type="button"
                className="btn out sm"
                onClick={() => {
                  navigator.clipboard?.writeText(`${t("username")}: ${newCredentials.username}
${t("password")}: ${newCredentials.password}`).catch(() => {});
                }}
              >
                {t("copyDetails")}
              </button>
              <button type="button" className="btn primary" onClick={() => onLogin && onLogin(newCredentials.user)}>
                {t("continueToPortal")}
              </button>
            </div>
          </div>
        ) : authMode === "signin" ? (
          <form onSubmit={handleSignIn}>
            <h2 style={{ marginTop: "0.4rem", fontSize: "1.3rem" }}>{t("signInTab")}</h2>
            <p className="soft small">
              {language === "hi"
                ? "अपनी भूमिका-सत्यापित साख के साथ प्रमाणित करें।"
                : language === "mr"
                ? "आपल्या भूमिका-सत्यापित क्रेडेन्शियलसह प्रमाणित करा."
                : "Authenticate with your role-verified credentials."}
            </p>

            <div style={{ margin: "0.7rem 0 0.4rem" }}>
              <label className="small soft" style={{ display: "block", marginBottom: "0.35rem", fontWeight: 600 }}>
                {t("quickDemoRoles")}
              </label>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.35rem" }}>
                {DEMO_PRESETS.map((preset) => (
                  <button
                    key={preset.role}
                    type="button"
                    className={`btn sm ${selectedRole === preset.role ? "primary" : "out"}`}
                    onClick={() => handlePresetSelect(preset)}
                    style={{ textAlign: "left", padding: "0.35rem 0.6rem", fontSize: "0.78rem" }}
                    disabled={loading}
                  >
                    <b>{language === "en" ? preset.label : t(ROLE_KEY[preset.role] || preset.role)}</b>
                  </button>
                ))}
              </div>

              {/* Minimal 1-liner feature description for the selected role */}
              {(() => {
                const activePreset = DEMO_PRESETS.find((p) => p.role === selectedRole) || DEMO_PRESETS[0];
                return (
                  <div
                    style={{
                      marginTop: "0.45rem",
                      padding: "0.45rem 0.65rem",
                      background: "#f4f8f5",
                      border: "1px solid #d5e5db",
                      borderRadius: "8px",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      gap: "0.5rem",
                      fontSize: "0.76rem",
                      color: "#1c5b43",
                      lineHeight: 1.3,
                    }}
                  >
                    <span style={{ display: "inline-flex", alignItems: "center", gap: "0.35rem" }}>
                      <Icon n={selectedRole === "doctor" ? "clip" : selectedRole === "staff" ? "plus" : selectedRole === "patient" ? "chat" : "shield"} size={13} />
                      <span>{activePreset.desc[language] || activePreset.desc.en}</span>
                    </span>
                    {selectedRole === "patient" && (
                      <button
                        type="button"
                        onClick={() => {
                          setAuthMode("signup");
                          setError(null);
                        }}
                        style={{
                          background: "none",
                          border: "none",
                          color: "var(--accent)",
                          fontWeight: 700,
                          cursor: "pointer",
                          textDecoration: "underline",
                          whiteSpace: "nowrap",
                          fontSize: "0.74rem",
                          padding: 0,
                          flexShrink: 0,
                        }}
                      >
                        {t("createAccountLink")}
                      </button>
                    )}
                  </div>
                );
              })()}
            </div>

            <label>
              {t("username")}
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                disabled={loading}
                placeholder="e.g. doctor, staff, patient, admin"
                autoComplete="username"
                required
              />
            </label>

            <label>
              {t("password")}
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={loading}
                placeholder="••••••••"
                autoComplete="current-password"
                required
              />
            </label>

            <button className="btn primary wide" type="submit" disabled={loading}>
              {loading ? <Spinner text={t("signingIn")} /> : `${t("signInButton")} (${(language === "en" ? selectedRole.toUpperCase() : t(ROLE_KEY[selectedRole] || selectedRole))})`}
            </button>

            <div style={{ textAlign: "center", marginTop: "0.7rem" }}>
              <span className="small soft">{t("newPatientPrompt")} </span>
              <button
                type="button"
                className="btn ghost sm"
                onClick={() => {
                  setAuthMode("signup");
                  setError(null);
                }}
                style={{ fontSize: "0.78rem", padding: "0.2rem 0.5rem" }}
              >
                {t("createAccountLink")}
              </button>
            </div>
          </form>
        ) : (
          <form onSubmit={handleSignUp} noValidate>
            <h2 style={{ marginTop: "0.4rem", fontSize: "1.3rem" }}>{t("signUpTab")}</h2>
            <p className="soft small">
              {language === "hi"
                ? "गाइडेड प्री-कंसल्टेशन इनटेक शुरू करने के लिए त्वरित पंजीकरण।"
                : language === "mr"
                ? "मार्गदर्शित प्री-कंसल्टेशन इनटेक सुरू करण्यासाठी जलद नोंदणी."
                : "Quick registration to start your guided pre-consultation intake."}
            </p>

            {/* Language Selection Buttons */}
            <div style={{ margin: "0.6rem 0" }}>
              <label className="small soft" style={{ display: "block", marginBottom: "0.3rem", fontWeight: 600 }}>
                {t("prefLang")} / भाषा:
              </label>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "0.3rem" }}>
                {LANGUAGES.map((l) => (
                  <button
                    key={l.code}
                    type="button"
                    className={`btn sm ${language === l.code ? "primary" : "out"}`}
                    onClick={() => handleLanguageChange(l.code, l.name)}
                    disabled={loading}
                    style={{ padding: "0.35rem 0.5rem", fontSize: "0.8rem" }}
                  >
                    <b>{l.native}</b>
                    <span style={{ fontSize: "0.7rem", display: "block", opacity: 0.8 }}>{l.name}</span>
                  </button>
                ))}
              </div>
            </div>

            <label>
              {t("fullName")} *
              <input
                type="text"
                value={signupForm.name}
                onChange={(e) => setSignupForm((f) => ({ ...f, name: e.target.value }))}
                disabled={loading}
                placeholder={t("fullNamePlaceholder")}
                required
              />
            </label>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem" }}>
              <label>
                {t("age")} *
                <input
                  type="number"
                  min="0"
                  max="125"
                  value={signupForm.age}
                  onChange={(e) => setSignupForm((f) => ({ ...f, age: e.target.value }))}
                  disabled={loading}
                  placeholder={t("agePlaceholder")}
                  required
                />
              </label>

              <label>
                {t("gender")} *
                <select
                  value={signupForm.gender}
                  onChange={(e) => setSignupForm((f) => ({ ...f, gender: e.target.value }))}
                  disabled={loading}
                  required
                >
                  <option value="">-- {t("genderSelect")} --</option>
                  <option value="Female">{t("female")}</option>
                  <option value="Male">{t("male")}</option>
                  <option value="Other">{t("other")}</option>
                </select>
              </label>
            </div>

            <label>
              {t("phone")}
              <input
                type="tel"
                value={signupForm.phone}
                onChange={(e) => setSignupForm((f) => ({ ...f, phone: e.target.value }))}
                disabled={loading}
                placeholder={t("phonePlaceholder")}
              />
            </label>

            <label>
              {t("chiefComplaint")}
              <input
                type="text"
                value={signupForm.complaint}
                onChange={(e) => setSignupForm((f) => ({ ...f, complaint: e.target.value }))}
                disabled={loading}
                placeholder={t("complaintPlaceholder")}
              />
            </label>

            <div
              style={{
                marginTop: "0.6rem",
                marginBottom: "0.6rem",
                padding: "0.55rem 0.7rem",
                background: "#f8faf8",
                borderRadius: "8px",
                border: "1px solid var(--line)",
              }}
            >
              <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer", fontWeight: "normal", margin: 0 }}>
                <input
                  type="checkbox"
                  checked={signupForm.consent}
                  onChange={(e) => setSignupForm((f) => ({ ...f, consent: e.target.checked }))}
                  disabled={loading}
                  style={{ width: "16px", height: "16px", flexShrink: 0 }}
                />
                <span className="small">
                  <b>{language === "hi" ? "सहमति आवश्यक: *" : language === "mr" ? "संमती आवश्यक: *" : "Consent Required: *"}</b>{" "}
                  {t("consentAgreement")}
                </span>
              </label>
            </div>

            <button className="btn primary wide" type="submit" disabled={loading}>
              {loading ? <Spinner text={t("registering")} /> : `${t("registerButton")} →`}
            </button>

            <div style={{ textAlign: "center", marginTop: "0.9rem" }}>
              <span className="small soft">{t("alreadyRegisteredPrompt")} </span>
              <button
                type="button"
                className="btn ghost sm"
                onClick={() => {
                  setAuthMode("signin");
                  setError(null);
                }}
                style={{ fontSize: "0.78rem", padding: "0.2rem 0.5rem" }}
              >
                {t("signInLink")}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
