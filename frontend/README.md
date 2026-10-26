# PatientCase AI — Frontend Client (React 18 + Vite)

Active production frontend application for PatientCase AI (SIH26047). Fully integrated with the FastAPI backend, local neural RapidOCR, and trilingual voice intake.

## Features
- **Trilingual UI Localization:** Dynamic switching between English (`en`), Hindi (`hi`), and Marathi (`mr`).
- **Patient Self-Registration & Staff Intake:** Form validation, informed consent capture, and unique ID generation.
- **Deterministic Adaptive Clinical Interview:** 16-question dynamic interview engine with branching, back navigation, and branch pruning.
- **Voice Assistant:** Web Speech API integration with text-to-speech question reading, voice transcript parsing, and safety-critical confirmation cards.
- **Prescription Upload & OCR Canvas:** Document dropzone with local RapidOCR ONNX inference and medication discrepancy alerts.
- **Doctor Dashboard & Review Portal:** Review queue, discrepancy reconciliation, doctor observations persistence, and permanent encounter locking.
- **Offline Resilience:** Local-first operation with offline banners and local SQLite reassurance.

## Quick Start (PowerShell)

```powershell
cd "d:\Projects\New PatientCase AI\frontend"

# 1. Install dependencies
npm install

# 2. Start development server
npm run dev
```

Application URL: `http://localhost:5173`

## Running Tests

```powershell
npm test
```
Runs 14 Vitest smoke and unit test suites (75/75 tests passing).

## Directory Structure
```
frontend/
├── index.html, package.json, vite.config.js
└── src/
    ├── api/         client.js (typed error normalization and API wrapper)
    ├── components/  Shell.jsx, VoiceAssistant.jsx, ui.jsx
    ├── pages/       Login, Dashboard, Register, PatientList, Interview, Documents, DoctorReview
    ├── state/       store.jsx (React Context state)
    ├── i18n.js      System-wide trilingual localization dictionaries (EN/HI/MR)
    └── styles/      Vanilla CSS design tokens and theme
```
