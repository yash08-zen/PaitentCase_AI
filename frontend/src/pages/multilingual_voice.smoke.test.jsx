import { describe, it, expect, vi } from "vitest";
import React from "react";
import { renderToString } from "react-dom/server";
import VoiceAssistant from "../components/VoiceAssistant";
import Interview from "./Interview";
import { StoreProvider } from "../state/store";
import { apiClient } from "../api/client";

describe("Frontend Milestone M12 — Multilingual Voice Conversation Smoke Tests (FR-12)", () => {
  it("verifies M12 voice API methods exist on apiClient", () => {
    expect(typeof apiClient.getVoiceLanguages).toBe("function");
    expect(typeof apiClient.getQuestionTranslation).toBe("function");
    expect(typeof apiClient.parseVoiceTranscript).toBe("function");
    expect(typeof apiClient.setEncounterLanguage).toBe("function");
  });

  it("renders VoiceAssistant with Listen question and Voice answer controls", () => {
    const html = renderToString(
      <VoiceAssistant
        questionKey="chief_complaint"
        activeLanguage="en"
        spokenPrompt="What is troubling you the most today?"
        onTranscriptConfirmed={() => {}}
      />
    );

    expect(html).toContain("Listen question");
    expect(html).toContain("Voice answer");
    expect(html).toContain("voice-assistant-panel");
  });

  it("renders Interview screen with Multilingual Language Selector bar", () => {
    const html = renderToString(
      <StoreProvider>
        <Interview go={() => {}} />
      </StoreProvider>
    );

    expect(html).toContain("Language:");
    expect(html).toContain("English");
    expect(html).toContain("हिंदी (Hindi)");
    expect(html).toContain("मराठी (Marathi)");
  });

  it("renders VoiceAssistant in Hindi locale with appropriate spoken prompt", () => {
    const html = renderToString(
      <VoiceAssistant
        questionKey="chief_complaint"
        activeLanguage="hi"
        spokenPrompt="आज आपको सबसे ज्यादा क्या तकलीफ हो रही है?"
        onTranscriptConfirmed={() => {}}
      />
    );

    expect(html).toContain("voice-assistant-panel");
    expect(html).toContain("Listen question");
  });

  it("renders VoiceAssistant in Marathi locale with appropriate spoken prompt", () => {
    const html = renderToString(
      <VoiceAssistant
        questionKey="chief_complaint"
        activeLanguage="mr"
        spokenPrompt="आज तुम्हाला सर्वात जास्त काय त्रास होत आहे?"
        onTranscriptConfirmed={() => {}}
      />
    );

    expect(html).toContain("voice-assistant-panel");
    expect(html).toContain("Listen question");
  });
});
