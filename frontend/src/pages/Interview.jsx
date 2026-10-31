import { useState, useEffect, useCallback } from "react";
import { useStore } from "../state/store";
import apiClient from "../api/client";
import { Bar, Empty, Icon, Tag, Proto, Spinner, Source } from "../components/ui";
import VoiceAssistant from "../components/VoiceAssistant";
import { getLocalQuestionTranslation, fmtT } from "../utils/i18n";

function formatValue(v) {
  if (Array.isArray(v)) return v.join(", ");
  if (v === undefined || v === null) return "";
  return String(v);
}

function AnswerInput({ q, value, setValue, onEnter }) {
  const toggleMulti = (opt) => {
    setValue((cur) => {
      const arr = Array.isArray(cur) ? cur : [];
      if (opt === "None") return ["None"];
      const withoutNone = arr.filter((x) => x !== "None");
      return withoutNone.includes(opt)
        ? withoutNone.filter((x) => x !== opt)
        : [...withoutNone, opt];
    });
  };

  const choices = q.choices || q.options || [];

  if (q.answer_type === "scale") {
    const scalePoints = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
    return (
      <div className="scale" role="radiogroup" aria-label={q.text}>
        {scalePoints.map((n) => (
          <button
            key={n}
            type="button"
            role="radio"
            aria-checked={String(value) === String(n)}
            className={`opt ${String(value) === String(n) ? "sel" : ""}`}
            onClick={() => setValue(String(n))}
          >
            {n}
          </button>
        ))}
      </div>
    );
  }

  if (q.answer_type === "choice") {
    return (
      <div className="opts" role="radiogroup" aria-label={q.text}>
        {choices.map((opt) => {
          const selected = String(value) === String(opt);
          return (
            <button
              key={opt}
              type="button"
              role="radio"
              aria-checked={selected}
              className={`opt ${selected ? "sel" : ""}`}
              onClick={() => setValue(opt)}
            >
              {selected && <Icon n="check" size={16} />}
              {opt}
            </button>
          );
        })}
      </div>
    );
  }

  if (q.answer_type === "multi") {
    const selectedArr = Array.isArray(value) ? value : [];
    return (
      <div className="opts" role="group" aria-label={q.text}>
        {choices.map((opt) => {
          const selected = selectedArr.includes(opt);
          return (
            <button
              key={opt}
              type="button"
              role="checkbox"
              aria-checked={selected}
              className={`opt ${selected ? "sel" : ""}`}
              onClick={() => toggleMulti(opt)}
            >
              {selected && <Icon n="check" size={16} />}
              {opt}
            </button>
          );
        })}
      </div>
    );
  }

  // The reason for visit is free text in the patient's own words: give it room
  if (q.key === "chief_complaint") {
    return (
      <textarea
        className="bigtext"
        autoFocus
        rows={3}
        value={value || ""}
        placeholder={q.placeholder || "Type your answer..."}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && (e.ctrlKey || e.metaKey) && onEnter()}
        aria-label={q.text}
        style={{ resize: "vertical", minHeight: 90 }}
      />
    );
  }

  // Text, number, date
  return (
    <input
      type={q.answer_type === "number" ? "number" : "text"}
      className="bigtext"
      autoFocus
      value={value || ""}
      placeholder={q.placeholder || "Type your answer..."}
      onChange={(e) => setValue(e.target.value)}
      onKeyDown={(e) => e.key === "Enter" && onEnter()}
      aria-label={q.text}
    />
  );
}

function QuestionCard({
  q,
  localizedQ = null,
  activeLanguage = "en",
  progressData,
  note,
  canBack,
  isSubmitting,
  onNext,
  onSkip,
  onBack,
  onSave,
}) {
  const { t } = useStore();
  const [val, setVal] = useState(() => (q.answer_type === "multi" ? [] : ""));

  // Reset local answer value when active question changes
  useEffect(() => {
    setVal(q.answer_type === "multi" ? [] : "");
  }, [q.key, q.answer_type]);

  const hasAnswer =
    q.answer_type === "multi"
      ? Array.isArray(val) && val.length > 0
      : String(val).trim() !== "";

  const handleContinue = () => {
    if (!hasAnswer || isSubmitting) return;
    const finalVal = Array.isArray(val) ? val.join(", ") : String(val).trim();
    onNext(finalVal);
  };

  const answeredCount = progressData?.answered_questions || 0;
  const totalCount = progressData?.total_questions || 1;
  const percent = progressData?.progress_percent ?? (answeredCount / totalCount) * 100;

  const [voiceNotice, setVoiceNotice] = useState(null);

  const handleVoiceToggle = () => {
    const isOnline = typeof navigator !== "undefined" ? navigator.onLine : true;
    if (!isOnline) {
      setVoiceNotice("Voice recognition service is unavailable offline. Keyboard and touch response inputs are fully enabled with local persistence.");
    } else {
      setVoiceNotice("Local voice input ready (English). Keyboard and touch response inputs remain active.");
    }
  };

  return (
    <div className="card qcard">
      <div className="row">
        <Tag kind="patient">{q.section || q.group || "Symptoms"}</Tag>
        <span className="small soft">
          {t("questionProgress")} {answeredCount + 1} {t("of")} ~{totalCount}
        </span>
      </div>

      <Bar value={percent} />

      {note && (
        <div className="adaptnote" role="status">
          <Icon n="chat" size={16} />
          {note}
        </div>
      )}

      {q.because && (
        <p className="why">Why this question? {q.because}.</p>
      )}

      <h1 className="qtext">{localizedQ?.text || q.text}</h1>
      {(localizedQ?.help || q.help) && <p className="soft">{localizedQ?.help || q.help}</p>}

      {/* Multilingual Voice Assistant (M12 / FR-12) */}
      <VoiceAssistant
        questionKey={q.key}
        activeLanguage={activeLanguage}
        spokenPrompt={localizedQ?.spoken_prompt || localizedQ?.text || q.text}
        onTranscriptConfirmed={(confirmedAnswer) => {
          setVal(q.answer_type === "multi" ? [confirmedAnswer] : confirmedAnswer);
        }}
        isSubmitting={isSubmitting}
      />

      <AnswerInput
        q={{
          ...q,
          text: localizedQ?.text || q.text,
          help: localizedQ?.help || q.help,
          choices: localizedQ?.choices || q.choices,
        }}
        value={val}
        setValue={setVal}
        onEnter={handleContinue}
      />

      <div className="row qctl">
        <div className="actions">
          <button
            type="button"
            className="btn out"
            disabled={!canBack || isSubmitting}
            onClick={onBack}
          >
            {t("backBtn")}
          </button>
          <button
            type="button"
            className="btn ghost"
            disabled={isSubmitting}
            onClick={onSave}
          >
            {t("saveExitBtn")}
          </button>
        </div>

        <div className="actions">
          <button
            type="button"
            className="btn ghost"
            disabled={isSubmitting}
            onClick={onSkip}
          >
            {t("skipBtn")}
          </button>
          <button
            type="button"
            className="btn primary"
            disabled={!hasAnswer || isSubmitting}
            onClick={handleContinue}
          >
            {isSubmitting ? t("savingBtn") : t("continueBtn")}
          </button>
        </div>
      </div>
    </div>
  );
}

function AdaptivePathPanel({ progressData }) {
  const { t } = useStore();
  const activePath = progressData?.active_path || [];
  const skippedList = progressData?.skipped_questions || [];

  // Group answered questions by section
  const answeredItems = activePath.filter((item) => item.is_answered);
  const sections = [...new Set(answeredItems.map((item) => item.section).filter(Boolean))];

  const followUps = activePath.filter((item) => item.because);

  return (
    <aside className="card adapt" aria-label={t("adaptivePathAria")}>
      <div className="row">
        <h2>{t("adaptivePathHeading")}</h2>
        <Proto>{t("ruleBasedShort")}</Proto>
      </div>
      <p className="small soft">
        {t("adaptivePathDesc")}
      </p>

      <h3>{t("followUpsHeading")}</h3>
      {followUps.length ? (
        <ul>
          {followUps.map((item) => (
            <li key={item.key}>
              <Icon n="check" size={14} />
              <span>
                <b>{item.label || item.key}</b>
                <br />
                <span className="small soft">{item.because}</span>
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="small soft">{t("noFollowUps")}</p>
      )}

      <h3>{t("skippedNotRelevant")}</h3>
      {skippedList.length ? (
        <ul className="muted">
          {skippedList.map((item) => (
            <li key={item.key}>
              <span className="dash">–</span>
              <span>
                <b>{item.label || item.key}</b>
                <br />
                <span className="small soft">{item.skip_why}</span>
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="small soft">{t("nothingSkipped")}</p>
      )}

      <h3>{t("answersSoFar")}</h3>
      {sections.length === 0 ? (
        <p className="small soft">{t("noAnswersYet")}</p>
      ) : (
        sections.map((sec) => (
          <div key={sec} className="grp">
            <p className="small soft">{sec}</p>
            {answeredItems
              .filter((item) => item.section === sec)
              .map((item) => (
                <p key={item.key} className="small">
                  <span className="soft">{item.label || item.key}:</span>{" "}
                  <b>{formatValue(item.value)}</b>
                </p>
              ))}
          </div>
        ))
      )}
    </aside>
  );
}

export default function Interview({ go, user }) {
  const isPatientRole = (user?.role || "").toLowerCase() === "patient";
  const { patients, cases, activeId, notify, language, setLanguage, t, LANGUAGES } = useStore();
  const [loading, setLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [currentQuestion, setCurrentQuestion] = useState(null);
  const [progressData, setProgressData] = useState(null);
  const [reviewAnswers, setReviewAnswers] = useState([]);
  const [isComplete, setIsComplete] = useState(false);
  const [note, setNote] = useState("");
  const [encounterId, setEncounterId] = useState(null);
  const [summaryData, setSummaryData] = useState(null);
  const [missingData, setMissingData] = useState(null);
  const [readinessData, setReadinessData] = useState(null);

  const [localizedQuestion, setLocalizedQuestion] = useState(null);

  const p = patients.find((x) => x.id === activeId);
  const c = cases[activeId];

  // Resolve encounter ID for the selected patient
  const loadInterview = useCallback(async () => {
    if (!p) return;
    setLoading(true);
    try {
      let resolvedEncId = c?.encounterId;
      if (!resolvedEncId && p.backendId) {
        // Query encounters from backend
        const encList = await apiClient.get("/api/encounters");
        const match = Array.isArray(encList)
          ? encList.find((e) => e.patient_id === p.backendId)
          : null;
        if (match) {
          resolvedEncId = match.id;
        } else {
          // Create encounter with consent if missing
          const created = await apiClient.post("/api/encounters", {
            patient_id: p.backendId,
            consent_given: true,
          });
          resolvedEncId = created.id;
        }
      }

      setEncounterId(resolvedEncId);

      if (resolvedEncId) {
        // Fetch next question and progress concurrently
        const [nextRes, progRes] = await Promise.all([
          apiClient.getNextQuestion(resolvedEncId),
          apiClient.getInterviewProgress(resolvedEncId),
        ]);

        setCurrentQuestion(nextRes.question || null);
        setProgressData(progRes);
        setNote(nextRes.adaptive_note || "");

        if (nextRes.is_complete || progRes.is_complete || c?.stage === "complete") {
          const [answersList, sumRes, misRes, readRes] = await Promise.all([
            apiClient.getInterviewAnswers(resolvedEncId),
            apiClient.getCaseSummary(resolvedEncId),
            apiClient.getMissingInformation(resolvedEncId),
            apiClient.getCaseReadiness(resolvedEncId),
          ]);
          setReviewAnswers(answersList || []);
          setSummaryData(sumRes);
          setMissingData(misRes);
          setReadinessData(readRes);
          if (c?.stage === "complete" || nextRes.is_complete) {
            setIsComplete(true);
          }
        }
      }
    } catch (err) {
      notify(err.message || "Failed to load interview state", "error");
    } finally {
      setLoading(false);
    }
  }, [p, c?.encounterId, c?.stage, notify]);

  useEffect(() => {
    loadInterview();
  }, [loadInterview]);

  const handleSubmit = async (answerVal) => {
    if (!encounterId || !currentQuestion) return;
    setIsSubmitting(true);
    try {
      await apiClient.submitResponse(encounterId, currentQuestion.key, answerVal);

      // Fetch next question & updated progress
      const [nextRes, progRes] = await Promise.all([
        apiClient.getNextQuestion(encounterId),
        apiClient.getInterviewProgress(encounterId),
      ]);

      setCurrentQuestion(nextRes.question || null);
      setProgressData(progRes);
      setNote(nextRes.adaptive_note || "");

      if (nextRes.is_complete) {
        const answersList = await apiClient.getInterviewAnswers(encounterId);
        setReviewAnswers(answersList || []);
      }
    } catch (err) {
      notify(err.message || "Failed to save response", "error");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSkip = async () => {
    if (!encounterId || !currentQuestion) return;
    setIsSubmitting(true);
    try {
      await apiClient.submitResponse(encounterId, currentQuestion.key, "[Skipped by patient]");
      const [nextRes, progRes] = await Promise.all([
        apiClient.getNextQuestion(encounterId),
        apiClient.getInterviewProgress(encounterId),
      ]);

      setCurrentQuestion(nextRes.question || null);
      setProgressData(progRes);
      setNote("");

      if (nextRes.is_complete) {
        const answersList = await apiClient.getInterviewAnswers(encounterId);
        setReviewAnswers(answersList || []);
      }
    } catch (err) {
      notify(err.message || "Failed to skip question", "error");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleBack = async () => {
    if (!encounterId) return;
    setIsSubmitting(true);
    try {
      const nextRes = await apiClient.backQuestion(encounterId);
      const progRes = await apiClient.getInterviewProgress(encounterId);
      setCurrentQuestion(nextRes.question || null);
      setProgressData(progRes);
      setNote(nextRes.adaptive_note || "");
    } catch (err) {
      notify(err.message || "Failed to navigate back", "error");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleEditQuestion = async (key) => {
    if (!encounterId) return;
    setIsSubmitting(true);
    try {
      // Find question definition
      const qRes = await apiClient.get(`/api/interviews/${encounterId}/next-question`);
      // Rewind or re-answer: submit empty or use back
      await apiClient.backQuestion(encounterId);
      const [refreshedQ, progRes] = await Promise.all([
        apiClient.getNextQuestion(encounterId),
        apiClient.getInterviewProgress(encounterId),
      ]);
      setCurrentQuestion(refreshedQ.question || null);
      setProgressData(progRes);
      setReviewAnswers([]);
    } catch (err) {
      notify(err.message || "Failed to edit question", "error");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleConfirmAndFinish = async () => {
    if (!encounterId) return;
    setIsSubmitting(true);
    try {
      await apiClient.completeInterview(encounterId);
      const [sumRes, misRes, readRes] = await Promise.all([
        apiClient.getCaseSummary(encounterId),
        apiClient.getMissingInformation(encounterId),
        apiClient.getCaseReadiness(encounterId),
      ]);
      setSummaryData(sumRes);
      setMissingData(misRes);
      setReadinessData(readRes);
      setIsComplete(true);
      notify("Interview completed successfully! Case sent for clinician review.");
    } catch (err) {
      notify(err.message || "Failed to finalize interview", "error");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRestart = async () => {
    if (!encounterId) return;
    setLoading(true);
    try {
      // Rewind to beginning
      const prog = await apiClient.getInterviewProgress(encounterId);
      for (let i = 0; i < (prog.answered_questions || 0); i++) {
        await apiClient.backQuestion(encounterId);
      }
      setIsComplete(false);
      await loadInterview();
      notify("Interview restarted.");
    } catch (err) {
      notify(err.message || "Failed to restart interview", "error");
    } finally {
      setLoading(false);
    }
  };

  const handleLanguageChange = async (newLang) => {
    setLanguage(newLang);
    const langObj = LANGUAGES.find((l) => l.code === newLang);
    const langName = langObj ? (langObj.name || langObj.native) : "English";
    if (encounterId) {
      try {
        await apiClient.setEncounterLanguage(encounterId, langName);
        notify(`${t("prefLang")}: ${langObj?.native || langName}`);
      } catch (err) {
        console.warn("Language persistence warning:", err);
      }
    }
  };

  // Sync localized question when current question or language changes
  useEffect(() => {
    if (!currentQuestion?.key) {
      setLocalizedQuestion(null);
      return;
    }
    // Instant local translation fallback
    const local = getLocalQuestionTranslation(currentQuestion.key, language);
    if (local) {
      setLocalizedQuestion(local);
    }
    apiClient
      .getQuestionTranslation(currentQuestion.key, language)
      .then((data) => {
        if (data) setLocalizedQuestion(data);
      })
      .catch(() => {
        // Keeps local translation if backend translation not reached
      });
  }, [currentQuestion?.key, language]);

  if (!p) {
    return (
      <Empty
        title={t("noPatientSelected")}
        text={t("chooseForInterview")}
        action={
          <button className="btn primary" onClick={() => go(isPatientRole ? "portal" : "patients")}>
            {isPatientRole ? t("portal") : t("openPatientList")}
          </button>
        }
      />
    );
  }

  let body;
  if (loading) {
    body = (
      <div style={{ padding: "40px 0", textAlign: "center" }}>
        <Spinner text={fmtT(t("loadingInterviewFor"), { name: p.name })} />
      </div>
    );
  } else if (isComplete) {
    const findingsList = summaryData?.structured_findings || [];
    const missingFields = missingData?.missing_fields || [];
    const scoreVal = readinessData?.score != null ? Math.round(readinessData.score * 100) : 100;
    const reqAnswered = readinessData?.factors?.required_fields_answered || `${Math.max(0, 6 - missingFields.length)}/6`;

    body = (
      <div className="card" style={{ padding: "1.5rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "1rem" }}>
          <span className="okcircle" style={{ flexShrink: 0 }}>
            <Icon n="check" size={24} />
          </span>
          <div>
            <h1 style={{ margin: 0 }}>{t("interviewCompleteHeading")} {p.name}</h1>
            <p className="soft" style={{ margin: "4px 0 0 0" }}>
              {t("interviewCompleteSubheading")}
            </p>
          </div>
        </div>

        {/* Case Completeness & Readiness bar */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            background: "#f0fdf4",
            border: "1px solid #bbf7d0",
            padding: "12px 16px",
            borderRadius: "8px",
            marginBottom: "1.5rem",
          }}
        >
          <div>
            <span style={{ fontWeight: "600", color: "#166534" }}>
              {t("caseDataCompleteness")}: {scoreVal}% — {readinessData?.label || t("readyForReview")}
            </span>
            <p className="small soft" style={{ margin: "2px 0 0 0", color: "#15803d" }}>
              {readinessData?.disclaimer || t("scoreDisclaimer")}
            </p>
          </div>
          <Tag kind={scoreVal >= 80 ? "ok" : "warn"}>{fmtT(t("nRequiredAnswered"), { n: reqAnswered })}</Tag>
        </div>

        {/* Structured findings table with provenance */}
        <h2>{t("intakeSummary")}</h2>
        <p className="small soft">
          {t("intakeSummaryDesc")}
        </p>
        <div className="scroll" style={{ margin: "1rem 0" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ textAlign: "left", borderBottom: "2px solid #e5e7eb" }}>
                <th style={{ padding: "8px 12px" }}>{t("colItem")}</th>
                <th style={{ padding: "8px 12px" }}>{t("colRecordedResponse")}</th>
                <th style={{ padding: "8px 12px" }}>{t("colProvenance")}</th>
              </tr>
            </thead>
            <tbody>
              {findingsList.map((r) => (
                <tr
                  key={r.key}
                  className={r.is_missing ? "missrow" : ""}
                  style={{ borderBottom: "1px solid #f3f4f6" }}
                >
                  <td style={{ padding: "8px 12px" }}>
                    <b>{r.label}</b>
                  </td>
                  <td style={{ padding: "8px 12px" }}>
                    {r.is_missing ? (
                      <Tag kind="warn">{t("srcMissing")}</Tag>
                    ) : (
                      <b>{r.value}</b>
                    )}
                  </td>
                  <td style={{ padding: "8px 12px" }}>
                    <Source s={r.source} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Missing information checklist */}
        <h2>{t("requiredChecklist")}</h2>
        <div style={{ margin: "0.75rem 0 1.5rem 0" }}>
          {missingFields.map((f) => (
            <div
              key={f.field}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                padding: "8px 12px",
                background: "#fef3c7",
                borderRadius: "6px",
                marginBottom: "6px",
              }}
            >
              <Icon n="alert" size={16} />
              <span style={{ fontWeight: "600", color: "#92400e" }}>
                {f.label || f.field}: {f.status || t("srcMissing")}
              </span>
              <span className="small soft" style={{ marginLeft: "auto", color: "#b45309" }}>
                {f.reason}
              </span>
            </div>
          ))}
          {missingFields.length === 0 && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                padding: "8px 12px",
                background: "#f0fdf4",
                borderRadius: "6px",
                color: "#166534",
              }}
            >
              <Icon n="check" size={16} />
              <span>{t("allFieldsCompleted")}</span>
            </div>
          )}
        </div>

        <div className="actions" style={{ marginTop: "1.5rem" }}>
          {!isPatientRole && (
            <button className="btn primary" onClick={() => go("review")}>
              {t("openDoctorReviewBtn")}
            </button>
          )}
          <button className="btn out" onClick={() => go("documents")}>
            {t("uploadPrescriptionsBtn")}
          </button>
          <button className="btn ghost" onClick={handleRestart}>
            {t("restartInterviewBtn")}
          </button>
        </div>
      </div>
    );
  } else if (!currentQuestion) {
    // Review screen when all questions are answered
    body = (
      <div className="card qcard">
        <h1>{t("reviewAnswersHeading")}</h1>
        <p className="soft">
          {t("reviewAnswersSubheading")}
        </p>

        <div className="reviewlist">
          {reviewAnswers.map((item) => (
            <div key={item.question_key} className="li">
              <div>
                <p className="small soft">
                  {item.section || "History"} · {item.label || item.question_key}
                </p>
                <b>{formatValue(item.answer)}</b>
              </div>
              <button
                type="button"
                className="btn out sm"
                disabled={isSubmitting}
                onClick={() => handleEditQuestion(item.question_key)}
              >
                {t("editBtn")}
              </button>
            </div>
          ))}
        </div>

        <div className="row qctl">
          <button
            type="button"
            className="btn out"
            disabled={isSubmitting}
            onClick={handleBack}
          >
            {t("backBtn")}
          </button>
          <button
            type="button"
            className="btn primary"
            disabled={isSubmitting}
            onClick={handleConfirmAndFinish}
          >
            {isSubmitting ? t("submittingBtn") : t("confirmFinishBtn")}
          </button>
        </div>
      </div>
    );
  } else {
    // Active Question Screen
    body = (
      <QuestionCard
        key={currentQuestion.key}
        q={currentQuestion}
        localizedQ={localizedQuestion}
        activeLanguage={language}
        progressData={progressData}
        note={note}
        canBack={Boolean(progressData?.answered_questions > 0)}
        isSubmitting={isSubmitting}
        onNext={handleSubmit}
        onSkip={handleSkip}
        onBack={handleBack}
        onSave={() => {
          notify("Progress saved to server. Resume anytime from the Patients directory.");
          go("patients");
        }}
      />
    );
  }

  return (
    <>
      <div className="head">
        <div>
          <h1>{t("interviewHeading") || "Adaptive interview"}</h1>
          <p className="soft">
            {p?.name} · {p?.id} · {language.toUpperCase()}
          </p>
        </div>
      </div>

      {/* Multilingual Language Selector (M12 / FR-12) */}
      <div className="language-selector-bar" role="radiogroup" aria-label="Select interview language">
        <span className="small soft" style={{ marginRight: 4 }}>{t("languageLabel")}</span>
        <button
          type="button"
          role="radio"
          aria-checked={language === "en"}
          className={`lang-btn ${language === "en" ? "active" : ""}`}
          onClick={() => handleLanguageChange("en")}
        >
          English
        </button>
        <button
          type="button"
          role="radio"
          aria-checked={language === "hi"}
          className={`lang-btn ${language === "hi" ? "active" : ""}`}
          onClick={() => handleLanguageChange("hi")}
        >
          हिंदी (Hindi)
        </button>
        <button
          type="button"
          role="radio"
          aria-checked={language === "mr"}
          className={`lang-btn ${language === "mr" ? "active" : ""}`}
          onClick={() => handleLanguageChange("mr")}
        >
          मराठी (Marathi)
        </button>
      </div>

      <div className="iv">
        {body}
        <AdaptivePathPanel progressData={progressData} />
      </div>
    </>
  );
}
