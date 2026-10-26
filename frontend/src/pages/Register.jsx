import { useState } from "react";
import { useStore } from "../state/store";
import { Icon, Spinner, ErrorBanner } from "../components/ui";

const BLANK = {
  name: "",
  age: "",
  gender: "",
  phone: "",
  language: "English",
  complaint: "",
  consent: false,
};

export default function Register({ go }) {
  const { registerPatient, notify, t, language } = useStore();
  const [f, setF] = useState(BLANK);
  const [err, setErr] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [serverError, setServerError] = useState(null);
  const [done, setDone] = useState(null);

  const set = (k) => (e) => {
    const val = e.target.type === "checkbox" ? e.target.checked : e.target.value;
    setF((prev) => ({ ...prev, [k]: val }));
    if (err[k]) {
      setErr((prev) => ({ ...prev, [k]: null }));
    }
  };

  const validate = () => {
    const x = {};
    if (!f.name || !f.name.trim()) {
      x.name = "Enter the patient's full name.";
    } else if (f.name.trim().length < 2) {
      x.name = "Name must be at least 2 characters long.";
    }

    if (f.age === "" || f.age === null || Number(f.age) < 0 || Number(f.age) > 125) {
      x.age = "Enter a valid age between 0 and 125.";
    }

    if (!f.gender) {
      x.gender = "Select a gender.";
    }

    if (f.phone) {
      const digits = f.phone.replace(/\D/g, "");
      if (digits.length < 7 || digits.length > 15) {
        x.phone = "Enter a valid phone number (7-15 digits).";
      }
    }

    if (!f.consent) {
      x.consent = "Informed consent is required before registering a patient and starting an interview.";
    }

    setErr(x);
    return Object.keys(x).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (isSubmitting) return; // Prevent double-clicking

    setServerError(null);

    if (!validate()) return;

    setIsSubmitting(true);
    try {
      const result = await registerPatient(f);
      setDone({
        patientId: result.patient.id,
        encounterId: result.encounter.id,
        name: result.patient.full_name,
        timestamp: result.encounter.consent_timestamp || new Date().toISOString(),
      });
      notify("Patient registered and encounter created successfully");
    } catch (apiErr) {
      setServerError(apiErr.message || "Failed to register patient. Please verify the input and try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

  if (done) {
    return (
      <div className="card empty" role="region" aria-label="Registration Success">
        <span className="okcircle">
          <Icon n="check" size={26} />
        </span>
        <h2>{done.name} is successfully registered</h2>
        <p className="soft">
          Generated Unique Patient ID: <b>P-{done.patientId}</b> &bull; Encounter ID: <b>#{done.encounterId}</b>
        </p>

        <div style={{ margin: "0.5rem 0 1rem", padding: "0.75rem 1rem", background: "#f0f7f1", borderRadius: "10px", textAlign: "left" }}>
          <span className="tag t-ver" style={{ marginBottom: "0.3rem" }}>
            <Icon n="check" size={12} /> Informed Consent Recorded
          </span>
          <p className="small soft" style={{ margin: 0 }}>
            Consent timestamp: {new Date(done.timestamp).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "medium" })}
          </p>
        </div>

        <div className="actions">
          <button className="btn primary" onClick={() => go("interview")}>
            Start adaptive interview
          </button>
          <button
            className="btn out"
            onClick={() => {
              setDone(null);
              setF(BLANK);
              setErr({});
            }}
          >
            Register another patient
          </button>
        </div>
      </div>
    );
  }

  const renderField = (k, label, props) => (
    <div className={`fld ${err[k] ? "bad" : ""}`}>
      <label htmlFor={k}>{label}</label>
      {props.options ? (
        <select id={k} value={f[k]} onChange={set(k)} disabled={isSubmitting}>
          {props.options.map((o) => (
            <option key={o} value={o}>{o === "" ? "-- Select --" : o}</option>
          ))}
        </select>
      ) : (
        <input id={k} value={f[k]} onChange={set(k)} disabled={isSubmitting} {...props} />
      )}
      {err[k] && (
        <span className="errtxt" role="alert">
          {err[k]}
        </span>
      )}
    </div>
  );

  return (
    <>
      <div className="head">
        <div>
          <h1>{language === "en" ? "Register Patient" : t("register")}</h1>
          <p className="soft">
            {language === "hi"
              ? "मरीज़ जनसांख्यिकी, सूचित सहमति और प्रारंभिक लक्षण दर्ज करके नया सत्र बनाएं।"
              : language === "mr"
              ? "रुग्ण लोकसंख्या, संमती आणि प्रारंभिक तक्रार नोंदवून नवीन सत्र तयार करा."
              : "Capture patient demographics, consent, and initial complaint to create an encounter."}
          </p>
        </div>
      </div>

      {serverError && (
        <ErrorBanner
          title="Registration Error"
          message={serverError}
          onRetry={() => setServerError(null)}
        />
      )}

      <form className="card form" onSubmit={handleSubmit} noValidate>
        <div className="grid2">
          {renderField("name", `${t("fullName")} *`, { placeholder: t("fullNamePlaceholder") })}
          {renderField("age", `${t("age")} *`, { type: "number", min: 0, max: 125, placeholder: t("agePlaceholder") })}
          {renderField("gender", `${t("gender")} *`, { options: ["", "Female", "Male", "Other"] })}
          {renderField("phone", language === "en" ? "Contact Number" : t("phone"), { placeholder: t("phonePlaceholder") })}
          {renderField("language", t("prefLang"), { options: ["English", "Hindi", "Marathi"] })}
          {renderField("complaint", t("chiefComplaint"), { placeholder: t("complaintPlaceholder") })}
        </div>

        <div style={{ marginTop: "1rem", padding: "1rem", background: "#f8faf8", borderRadius: "12px", border: err.consent ? "1.5px solid var(--red)" : "1.5px solid var(--line)" }}>
          <label style={{ display: "flex", alignItems: "flex-start", gap: "0.75rem", cursor: "pointer", fontWeight: "normal" }}>
            <input
              type="checkbox"
              id="consent"
              checked={f.consent}
              onChange={set("consent")}
              disabled={isSubmitting}
              style={{ width: "20px", height: "20px", marginTop: "2px" }}
            />
            <span className="small">
              <b>{language === "hi" ? "सूचित सहमति आवश्यक है: *" : language === "mr" ? "माहितीपूर्ण संमती आवश्यक: *" : "Informed Consent Required: *"}</b>{" "}
              {t("consentAgreement")}
            </span>
          </label>
          {err.consent && (
            <p className="errtxt" style={{ margin: "0.4rem 0 0 2rem" }} role="alert">
              {err.consent}
            </p>
          )}
        </div>

        <div className="actions" style={{ marginTop: "1.2rem" }}>
          <button className="btn primary" type="submit" disabled={isSubmitting}>
            {isSubmitting ? (
              <Spinner text={t("registering")} />
            ) : (
              language === "en" ? "Register and continue" : `${t("registerButton")} →`
            )}
          </button>
          <button
            className="btn out"
            type="button"
            disabled={isSubmitting}
            onClick={() => {
              setF(BLANK);
              setErr({});
              setServerError(null);
            }}
          >
            {language === "hi" ? "साफ़ करें" : language === "mr" ? "साफ करा" : "Clear"}
          </button>
        </div>
      </form>
    </>
  );
}
