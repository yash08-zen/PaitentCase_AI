import { useState, useEffect, useRef } from "react";
import { Icon, Spinner } from "./ui";
import apiClient from "../api/client";

const LOCALES = {
  en: "en-IN",
  hi: "hi-IN",
  mr: "mr-IN",
};

export default function VoiceAssistant({
  questionKey,
  activeLanguage = "en",
  spokenPrompt = "",
  onTranscriptConfirmed,
  isSubmitting = false,
}) {
  const [isListening, setIsListening] = useState(false);
  const [isPlayingAudio, setIsPlayingAudio] = useState(false);
  const [recognitionResult, setRecognitionResult] = useState(null);
  const [isParsing, setIsParsing] = useState(false);
  const [errorNotice, setErrorNotice] = useState(null);

  const recognitionRef = useRef(null);
  const timeoutRef = useRef(null);

  // Stop any active speech synthesis on unmount or question change
  useEffect(() => {
    return () => {
      if (typeof window !== "undefined" && "speechSynthesis" in window) {
        window.speechSynthesis.cancel();
      }
      if (recognitionRef.current) {
        try {
          recognitionRef.current.abort();
        } catch {
          // ignore
        }
      }
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, [questionKey]);

  // Reset local state when active question changes
  useEffect(() => {
    setRecognitionResult(null);
    setErrorNotice(null);
    setIsListening(false);
  }, [questionKey]);

  // 1. Text-to-Speech: Spoken Question Audio
  const handleSpeakQuestion = () => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) {
      setErrorNotice("Speech synthesis is not supported on this browser device.");
      return;
    }
    window.speechSynthesis.cancel();

    const textToSpeak = spokenPrompt || "Please answer the question on your screen.";
    const utterance = new SpeechSynthesisUtterance(textToSpeak);
    utterance.lang = LOCALES[activeLanguage] || "en-IN";
    utterance.rate = 0.95;

    utterance.onstart = () => setIsPlayingAudio(true);
    utterance.onend = () => setIsPlayingAudio(false);
    utterance.onerror = () => {
      setIsPlayingAudio(false);
      setErrorNotice("Audio playback failed or service unavailable.");
    };

    window.speechSynthesis.speak(utterance);
  };

  // 2. Speech-to-Text: Microphone Recording & Silence Handling
  const handleStartListening = () => {
    setErrorNotice(null);
    setRecognitionResult(null);

    const isOnline = typeof navigator !== "undefined" ? navigator.onLine : true;
    if (!isOnline) {
      setErrorNotice("Voice recognition service is unavailable offline. Keyboard and touch inputs remain fully operational.");
      return;
    }

    const SpeechRecognition =
      typeof window !== "undefined" &&
      (window.SpeechRecognition || window.webkitSpeechRecognition);

    if (!SpeechRecognition) {
      // Simulate accessible voice prompt for browsers without Web Speech
      setErrorNotice(
        "Browser speech recognition engine not available in this environment. Please type or touch-select your answer."
      );
      return;
    }

    try {
      const recognition = new SpeechRecognition();
      recognition.lang = LOCALES[activeLanguage] || "en-IN";
      recognition.continuous = false;
      recognition.interimResults = false;
      recognition.maxAlternatives = 1;

      recognition.onstart = () => {
        setIsListening(true);
        // 6-second silence detector
        timeoutRef.current = setTimeout(() => {
          if (recognitionRef.current) {
            recognitionRef.current.stop();
            setErrorNotice("No speech detected within 6 seconds. Please speak clearly or use keyboard input.");
            setIsListening(false);
          }
        }, 6000);
      };

      recognition.onresult = async (event) => {
        if (timeoutRef.current) clearTimeout(timeoutRef.current);
        const transcript = event.results[0][0].transcript;
        const confidence = event.results[0][0].confidence || 0.9;
        setIsListening(false);
        await processTranscript(transcript, confidence);
      };

      recognition.onerror = (event) => {
        if (timeoutRef.current) clearTimeout(timeoutRef.current);
        setIsListening(false);
        if (event.error === "not-allowed" || event.error === "permission-denied") {
          setErrorNotice("Microphone permission was denied. Keyboard and touch input remain active.");
        } else if (event.error === "no-speech") {
          setErrorNotice("No speech was detected. Please try again or type your answer below.");
        } else {
          setErrorNotice(`Speech recognition error (${event.error}). Please use keyboard input.`);
        }
      };

      recognition.onend = () => {
        setIsListening(false);
      };

      recognitionRef.current = recognition;
      recognition.start();
    } catch (err) {
      setIsListening(false);
      setErrorNotice(`Unable to initialize microphone: ${err.message}`);
    }
  };

  const handleStopListening = () => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {
        // ignore
      }
    }
    setIsListening(false);
  };

  // 3. Backend Transcript Parsing & Safety Confirmation Logic
  const processTranscript = async (rawTranscript, speechConfidence) => {
    setIsParsing(true);
    try {
      const parseData = await apiClient.parseVoiceTranscript({
        transcript: rawTranscript,
        question_key: questionKey,
        language: activeLanguage,
        confidence: speechConfidence,
      });
      setRecognitionResult(parseData);
    } catch (err) {
      setErrorNotice(`Failed to parse speech: ${err.message}`);
    } finally {
      setIsParsing(false);
    }
  };

  // 4. Confirmation Actions
  const handleConfirm = () => {
    if (!recognitionResult) return;
    const answerToUse = recognitionResult.parsed_value || recognitionResult.raw_transcript;
    onTranscriptConfirmed(answerToUse, recognitionResult.normalized_english);
    setRecognitionResult(null);
  };

  const handleDiscard = () => {
    setRecognitionResult(null);
  };

  return (
    <div className="voice-assistant-panel" role="region" aria-label="Multilingual Voice Assistant">
      <div className="voice-controls-row">
        <button
          type="button"
          className={`btn sm out ${isPlayingAudio ? "primary" : ""}`}
          onClick={handleSpeakQuestion}
          disabled={isPlayingAudio || isSubmitting}
          aria-label="Listen to question spoken audio"
        >
          <Icon n="chat" size={14} />
          {isPlayingAudio ? "Playing question..." : "Listen question"}
        </button>

        {!isListening ? (
          <button
            type="button"
            className="btn sm primary"
            onClick={handleStartListening}
            disabled={isSubmitting || isParsing}
            aria-label="Start voice input recording"
          >
            <Icon n="check" size={14} />
            Voice answer
          </button>
        ) : (
          <button
            type="button"
            className="btn sm out"
            style={{ borderColor: "#c53030", color: "#c53030" }}
            onClick={handleStopListening}
            aria-label="Stop recording"
          >
            <span className="health-dot offline" style={{ animation: "pulse 0.8s infinite" }} />
            Listening... (Stop)
          </button>
        )}
      </div>

      {isParsing && (
        <div style={{ marginTop: 8 }}>
          <Spinner size={16} text="Analyzing spoken answer..." />
        </div>
      )}

      {/* Error or Fallback Notice */}
      {errorNotice && (
        <div className="banner bad" style={{ marginTop: 8, padding: "0.5rem 0.8rem", fontSize: "0.82rem" }} role="alert">
          <Icon n="alert" size={14} />
          <span>{errorNotice}</span>
          <button
            type="button"
            onClick={() => setErrorNotice(null)}
            style={{ background: "none", border: "none", marginLeft: "auto", cursor: "pointer", color: "inherit" }}
            aria-label="Dismiss error"
          >
            ✕
          </button>
        </div>
      )}

      {/* Transcript Review & Confirmation Modal/Bar */}
      {recognitionResult && (
        <div className="voice-confirmation-card" role="region" aria-label="Spoken Answer Confirmation">
          <div className="voice-confirmation-header" style={{ display: "flex", gap: "8px", alignItems: "center", flexWrap: "wrap" }}>
            <b>Verify Spoken Answer</b>
            {recognitionResult.is_code_mixed && (
              <span className="tag t-info" style={{ fontSize: "0.72rem", background: "#ebf8ff", color: "#2b6cb0", borderColor: "#bee3f8" }}>
                🌐 Code-Mixed ({recognitionResult.detected_dialect})
              </span>
            )}
            {recognitionResult.requires_confirmation && (
              <span className="tag t-warn" style={{ fontSize: "0.72rem" }}>
                Confirmation Required
              </span>
            )}
          </div>

          <p className="small soft" style={{ margin: "4px 0" }}>
            Heard: <em>"{recognitionResult.raw_transcript}"</em>
          </p>

          <p style={{ margin: "6px 0", fontSize: "0.92rem" }}>
            Mapped Answer: <strong>{recognitionResult.parsed_value}</strong>
            {recognitionResult.normalized_english && recognitionResult.normalized_english !== recognitionResult.parsed_value && (
              <span className="small soft"> (Clinical English: {recognitionResult.normalized_english})</span>
            )}
          </p>

          {recognitionResult.confirmation_reason && (
            <p className="small" style={{ color: "#b7791f", margin: "4px 0" }}>
              Note: {recognitionResult.confirmation_reason}
            </p>
          )}

          <div className="actions" style={{ marginTop: 10 }}>
            <button
              type="button"
              className="btn sm primary"
              onClick={handleConfirm}
              disabled={isSubmitting}
            >
              Confirm & use answer
            </button>
            <button
              type="button"
              className="btn sm out"
              onClick={handleStartListening}
              disabled={isSubmitting}
            >
              Re-record
            </button>
            <button
              type="button"
              className="btn sm ghost"
              onClick={handleDiscard}
            >
              Discard
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
