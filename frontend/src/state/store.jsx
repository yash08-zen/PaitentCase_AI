import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { CASES, PATIENTS, emptyCase } from "../data/patients";
import apiClient from "../api/client";
import { t as i18nT, LANGUAGES } from "../utils/i18n";

export const Ctx = createContext(null);
export const useStore = () => useContext(Ctx);

export function StoreProvider({ children }) {
  const [patients, setPatients] = useState(PATIENTS);
  const [cases, setCases] = useState(CASES);
  const [activeId, setActiveId] = useState("P-1001");
  const [query, setQuery] = useState("");
  const [toast, setToast] = useState(null);
  const [loading, setLoading] = useState(false);
  const [language, setLanguageState] = useState(() => {
    try {
      return localStorage.getItem("patientcase_lang") || "en";
    } catch {
      return "en";
    }
  });

  const setLanguage = useCallback((newLang) => {
    const code = (newLang || "en").toLowerCase();
    const valid = ["en", "hi", "mr"].includes(code) ? code : "en";
    setLanguageState(valid);
    try {
      localStorage.setItem("patientcase_lang", valid);
    } catch {}
  }, []);

  const t = useCallback((key) => i18nT(key, language), [language]);

  const notify = useCallback((msg, type = "success") => {
    if (!msg) {
      setToast(null);
      return;
    }
    const toastObj = typeof msg === "object" ? msg : { message: msg, type };
    setToast(toastObj);
    setTimeout(() => setToast(null), 3500);
  }, []);

  const patch = (id, fn) => setCases((cs) => ({ ...cs, [id]: fn(cs[id] || emptyCase()) }));

  // Load real patients from backend if token is available
  const refreshPatients = useCallback(async () => {
    const token = apiClient.getToken();
    if (!token) return;

    const currentUser = apiClient.getUser();
    const isPatient = (currentUser?.role || "").toLowerCase() === "patient";

    try {
      setLoading(true);

      if (isPatient) {
        // Patient role: fetch own profile and encounters
        const [myProfile, encRes] = await Promise.all([
          apiClient.getMyPatientProfile().catch(() => null),
          apiClient.get("/api/encounters").catch(() => []),
        ]);

        if (myProfile) {
          const loadedPatient = {
            id: `P-${myProfile.id}`,
            backendId: myProfile.id,
            name: myProfile.full_name,
            age: myProfile.age || 0,
            gender: myProfile.gender || "Other",
            phone: myProfile.contact_phone || "",
            language: myProfile.preferred_language || "English",
            registered: myProfile.created_at
              ? new Date(myProfile.created_at).toLocaleDateString("en-GB", {
                  day: "2-digit",
                  month: "short",
                  year: "numeric",
                })
              : "Today",
          };

          const encList = Array.isArray(encRes) ? encRes : [];
          const matchedEnc = encList.find((e) => e.patient_id === myProfile.id) || encList[0];

          if (myProfile.preferred_language) {
            const pl = myProfile.preferred_language.toLowerCase();
            if (pl.includes("hindi") || pl === "hi") setLanguage("hi");
            else if (pl.includes("marathi") || pl === "mr") setLanguage("mr");
            else if (pl.includes("english") || pl === "en") setLanguage("en");
          }

          setPatients([loadedPatient]);
          setActiveId(loadedPatient.id);
          setCases((prevCases) => ({
            ...prevCases,
            [loadedPatient.id]: {
              ...(prevCases[loadedPatient.id] || emptyCase()),
              encounterId: matchedEnc ? matchedEnc.id : undefined,
              stage: matchedEnc?.status === "completed" ? "complete" : "interview",
            },
          }));
        }
        return;
      }

      // Clinician / Staff / Admin roles
      const [res, encRes] = await Promise.all([
        apiClient.get("/api/patients?page=1&page_size=50"),
        apiClient.get("/api/encounters").catch(() => []),
      ]);

      if (res?.items && Array.isArray(res.items)) {
        const loadedPatients = res.items.map((p) => ({
          id: `P-${p.id}`,
          backendId: p.id,
          name: p.full_name,
          age: p.age || 0,
          gender: p.gender || "Other",
          phone: p.contact_phone || "",
          language: p.preferred_language || "English",
          registered: p.created_at
            ? new Date(p.created_at).toLocaleDateString("en-GB", {
                day: "2-digit",
                month: "short",
                year: "numeric",
              })
            : "Today",
        }));

        const encountersList = Array.isArray(encRes) ? encRes : [];

        if (loadedPatients.length > 0) {
          setPatients(loadedPatients);
          // Ensure cases exist for all loaded patients with linked encounterId
          setCases((prevCases) => {
            const nextCases = { ...prevCases };
            loadedPatients.forEach((lp) => {
              const matchedEnc = encountersList.find((e) => e.patient_id === lp.backendId);
              const existing = nextCases[lp.id] || emptyCase();
              nextCases[lp.id] = {
                ...existing,
                encounterId: matchedEnc ? matchedEnc.id : existing.encounterId,
                stage: matchedEnc?.status === "completed" ? "complete" : matchedEnc?.status === "in_progress" ? "interview" : existing.stage,
              };
            });
            return nextCases;
          });

          // Set active patient if not already set or invalid
          setActiveId((curr) => {
            const exists = loadedPatients.some((p) => p.id === curr);
            return exists ? curr : loadedPatients[0].id;
          });
        }
      }
    } catch {
      // Keep existing patients if fetch fails or user is role-restricted
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshPatients();
  }, [refreshPatients]);

  const actions = {
    async registerPatient({ name, age, gender, phone, language, complaint, consent }) {
      // 1. Create Patient on Backend
      const patientPayload = {
        full_name: name.trim(),
        age: Number(age),
        gender,
        contact_phone: phone ? phone.trim() : null,
        preferred_language: language || "English",
      };

      const newPatient = await apiClient.post("/api/patients", patientPayload);

      // 2. Create Encounter linked to Patient with Consent
      const encounterPayload = {
        patient_id: newPatient.id,
        chief_complaint: complaint ? complaint.trim() : null,
        consent_given: Boolean(consent),
      };

      const newEncounter = await apiClient.post("/api/encounters", encounterPayload);

      // 3. Update local state
      const localId = `P-${newPatient.id}`;
      const mappedPatient = {
        id: localId,
        backendId: newPatient.id,
        name: newPatient.full_name,
        age: newPatient.age,
        gender: newPatient.gender,
        phone: newPatient.contact_phone || "",
        language: newPatient.preferred_language,
        registered: "Today",
      };

      setPatients((prev) => [mappedPatient, ...prev.filter((p) => p.id !== localId)]);
      setCases((prev) => ({
        ...prev,
        [localId]: {
          ...emptyCase(),
          encounterId: newEncounter.id,
          consentGiven: newEncounter.consent_given,
          consentTimestamp: newEncounter.consent_timestamp,
          answers: complaint ? { complaint: complaint.trim() } : {},
        },
      }));

      setActiveId(localId);
      return { patient: newPatient, encounter: newEncounter, localId };
    },

    async selfRegisterPatient({ name, age, gender, phone, language, complaint, consent }) {
      const payload = {
        full_name: name.trim(),
        age: age ? Number(age) : null,
        gender: gender || null,
        contact_phone: phone ? phone.trim() : null,
        preferred_language: language || "English",
        chief_complaint: complaint ? complaint.trim() : null,
        consent_given: Boolean(consent),
      };

      const res = await apiClient.selfRegister(payload);
      const localId = `P-${res.patient.id}`;
      const mappedPatient = {
        id: localId,
        backendId: res.patient.id,
        name: res.patient.full_name,
        age: res.patient.age || 0,
        gender: res.patient.gender || "Other",
        phone: res.patient.contact_phone || "",
        language: res.patient.preferred_language || "English",
        registered: "Today",
      };

      setPatients([mappedPatient]);
      setActiveId(localId);
      setCases((prev) => ({
        ...prev,
        [localId]: {
          ...emptyCase(),
          encounterId: res.encounter.id,
          consentGiven: res.encounter.consent_given,
          consentTimestamp: res.encounter.consent_timestamp,
          answers: complaint ? { complaint: complaint.trim() } : {},
          stage: "interview",
        },
      }));

      return res;
    },

    addPatient(p) {
      const id = "P-" + (1001 + patients.length);
      setPatients((ps) => [{ ...p, id, registered: "Today" }, ...ps]);
      setCases((cs) => ({ ...cs, [id]: emptyCase() }));
      setActiveId(id);
      return id;
    },

    answer: (id, key, val) =>
      patch(id, (c) => ({
        ...c,
        stage: "interview",
        answers: { ...c.answers, [key]: val },
        stack: [...c.stack, key],
      })),

    skip: (id, key) =>
      patch(id, (c) => ({
        ...c,
        stage: "interview",
        skipped: [...c.skipped, key],
        stack: [...c.stack, key],
      })),

    back: (id) =>
      patch(id, (c) => {
        const k = c.stack[c.stack.length - 1];
        if (!k) return c;
        const { [k]: _, ...rest } = c.answers;
        return {
          ...c,
          answers: rest,
          skipped: c.skipped.filter((x) => x !== k),
          stack: c.stack.slice(0, -1),
        };
      }),

    editTo: (id, key) =>
      patch(id, (c) => {
        const i = c.stack.indexOf(key),
          gone = c.stack.slice(i);
        const answers = { ...c.answers };
        gone.forEach((k) => delete answers[k]);
        return {
          ...c,
          stage: "interview",
          answers,
          skipped: c.skipped.filter((k) => !gone.includes(k)),
          stack: c.stack.slice(0, i),
        };
      }),

    complete: (id) => patch(id, (c) => ({ ...c, stage: "complete" })),
    restart: (id) => patch(id, () => emptyCase()),
    addDoc: (id, doc) => patch(id, (c) => ({ ...c, docs: [...c.docs, doc] })),
    setFlag: (id, flagId, status) =>
      patch(id, (c) => {
        const flags = { ...c.flags };
        status ? (flags[flagId] = status) : delete flags[flagId];
        return { ...c, flags };
      }),
    setNotes: (id, notes) => patch(id, (c) => ({ ...c, notes })),
    finalize: (id) => patch(id, (c) => ({ ...c, finalized: true })),
    resetDemo() {
      setPatients(PATIENTS);
      setCases(CASES);
      setActiveId("P-1001");
    },
    refreshPatients,
  };

  return (
    <Ctx.Provider
      value={{
        patients,
        cases,
        activeId,
        setActiveId,
        query,
        setQuery,
        toast,
        notify,
        loading,
        language,
        setLanguage,
        t,
        LANGUAGES,
        ...actions,
      }}
    >
      {children}
    </Ctx.Provider>
  );
}
