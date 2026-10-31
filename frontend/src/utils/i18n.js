/**
 * src/utils/i18n.js
 * -----------------
 * Comprehensive trilingual localization dictionary and helper functions
 * for English ('en'), Hindi ('hi'), and Marathi ('mr').
 * Translates the entire user interface and adaptive clinical questions.
 */

import { PAGE_TRANSLATIONS } from "./i18n_pages";
import { INTAKE_TRANSLATIONS } from "./i18n_intake";
import { AI_TRANSLATIONS } from "./i18n_ai";
import { LOCAL_QUESTION_TRANSLATIONS } from "./i18n_questions";
import { VISIT_TRANSLATIONS } from "./i18n_visit";

export const LANGUAGES = [
  { code: "en", name: "English", native: "English", locale: "en-IN" },
  { code: "hi", name: "Hindi", native: "हिन्दी", locale: "hi-IN" },
  { code: "mr", name: "Marathi", native: "मराठी", locale: "mr-IN" },
];

export const UI_TRANSLATIONS = {
  en: {
    // Shell & Navigation
    menu: "MENU",
    general: "GENERAL",
    dashboard: "Dashboard",
    portal: "Patient Portal",
    patients: "Patients",
    register: "Register patient",
    interview: "Adaptive interview",
    documents: "Documents",
    review: "Doctor review",
    audit: "Audit logs",
    logout: "Log out",
    resetDemo: "Reset demo data",
    activePatient: "Active patient",
    searchPatients: "Search patients",
    searchPlaceholder: "Search patients by name or ID",
    language: "Language",
    selectLanguage: "Language / भाषा",
    localNeuralOcr: "Local Neural OCR: RapidOCR ONNX (Offline Ready)",
    patientPortalSession: "Patient Portal Session",
    restrictedRecord: "Restricted to own medical record",

    // Roles
    doctor: "Doctor",
    clinicStaff: "Clinic Staff",
    patient: "Patient",
    admin: "Admin",

    // AI Clinical Insights
    aiClinicalInsights: "AI Clinical Insights",
    aiInsights: "AI Insights",
    aiGeneratedUnverified: "AI-generated, unverified",
    doctorVerified: "Doctor Verified",
    aiNoticeText: "PatientCase AI provides source-cited, AI-generated suggestions for clinician review. It makes no autonomous decisions.",
    urgencyEmergency: "EMERGENCY",
    urgencyUrgent: "URGENT",
    urgencyRoutine: "ROUTINE",
    runAIAnalysis: "Run AI Analysis",
    runningAnalysis: "Running AI Pipeline...",
    documentedDiagnoses: "Documented Diagnoses",
    possibleDiagnoses: "Possible Considerations (Differential)",
    abnormalLabs: "Abnormal & Critical Lab Results",
    allLabs: "All Extracted Lab Tests",
    computedTrends: "Computed Laboratory Trends",
    riskScores: "Deterministic Risk Scores",
    treatmentReference: "Evidence-Based Treatment Reference",
    aiCaseSummary: "AI Draft Summary",
    questionsToAsk: "Clarification Questions for Patient",
    accept: "Accept",
    edit: "Edit",
    reject: "Reject",
    caseLockedNotice: "Encounter has been finalized and locked by clinician review. All insights are read-only.",
    notCalculable: "Not calculable",
    calculateProvisional: "Calculate anyway (Provisional)",
    sourceEvidence: "Evidence / Source Spans",
    guidelineQuote: "Guideline Recommendation",
    saveEdit: "Save Doctor Edit",
    cancel: "Cancel",
    rejectionReason: "Reason for rejection",
    originalScan: "Original Medical Document",
    extractedEntities: "Extracted Grounded Entities",

    // Boundary Notice
    boundaryBadge: "NON-DIAGNOSTIC NOTICE",
    boundaryText: "This software assists with clinical case-taking and information organization. It does NOT diagnose diseases, prescribe medicines, or replace clinical judgment.",

    // Login & Auth
    loginTitle: "Welcome to PatientCase AI",
    loginSubtitle: "Adaptive pre-consultation case-taking and physician review.",
    signInTab: "Sign In",
    signUpTab: "New Patient Sign Up",
    quickDemoRoles: "Select Demo Role:",
    existingPatientNotice: "Sign in to an existing patient account.",
    patientRoleDesc: "Guided interview intake and personal health records.",
    newPatientPrompt: "First time at this hospital?",
    createAccountLink: "Create New Patient Account →",
    alreadyRegisteredPrompt: "Already an existing patient?",
    signInLink: "Sign In to Existing Account →",
    username: "Username",
    password: "Password",
    signInButton: "Sign In",
    signingIn: "Signing in...",

    // New Patient Registration / Signup
    registerPatient: "Register Patient",
    fullName: "Full Name",
    fullNamePlaceholder: "e.g., Ramesh Kumar",
    age: "Age",
    agePlaceholder: "e.g., 45",
    gender: "Gender",
    genderSelect: "Select gender",
    male: "Male",
    female: "Female",
    other: "Other",
    phone: "Phone Number",
    phonePlaceholder: "10-digit mobile number",
    prefLang: "Preferred Language",
    chiefComplaint: "Reason for visit / Chief complaint",
    complaintPlaceholder: "Briefly describe your symptoms (e.g. headache for 2 days)",
    consentAgreement: "I consent to pre-consultation case-taking and physician review.",
    registerButton: "Create Patient Account & Begin Intake",
    registering: "Creating account...",

    // Patient Portal
    portalHeading: "Patient Intake Portal",
    portalSubheading: "Complete your pre-consultation intake before your doctor visit.",
    step1Title: "Step 1: Registered",
    step1Badge: "✓ Consent Verified",
    step1Heading: "Demographics & Consent",
    step1Desc: "Demographics, contact info, and intake consent recorded.",
    step2Title: "Step 2: Documents",
    step2Heading: "Upload Prescriptions",
    step2Desc: "Upload prescriptions or test reports for local text extraction.",
    step2Button: "Upload Prescriptions",
    step3Title: "Step 3: Interview",
    step3Heading: "Adaptive Case-Taking",
    step3Desc: "Answer guided questions about your symptoms and medical history.",
    startInterview: "Start Adaptive Case-Taking",
    resumeInterview: "Resume Clinical Interview",
    reviewCase: "Review Completed Case",
    docCountLabel: "uploaded",

    // Adaptive Interview
    interviewHeading: "Adaptive interview",
    ruleBased: "Rule-based engine",
    questionProgress: "Question",
    of: "of",
    continueBtn: "Continue",
    backBtn: "Back",
    skipBtn: "Prefer not to answer",
    saveExitBtn: "Save and exit",
    confirmFinishBtn: "Confirm and finish",
    editBtn: "Edit",
    savingBtn: "Saving...",
    submittingBtn: "Submitting...",
    reviewAnswersHeading: "Review your answers",
    reviewAnswersSubheading: "Verify your answers before submitting them to the doctor. Changing an answer will automatically re-evaluate follow-up branches.",
    interviewCompleteHeading: "Interview complete for",
    interviewCompleteSubheading: "Clinical intake history recorded and persisted to backend. Ready for clinician review.",
    openDoctorReviewBtn: "Open doctor review",
    uploadPrescriptionsBtn: "Upload prescriptions",
    restartInterviewBtn: "Restart interview",
    adaptivePathHeading: "Adaptive path",
    adaptivePathDesc: "The engine dynamically selects each question from your earlier answers.",
    followUpsHeading: "Follow-ups added for you",
    noFollowUpsYet: "Answer earlier questions to see dynamic clinical follow-up branches.",
    requiredChecklist: "Required fields checklist",
    allFieldsCompleted: "All required clinical intake fields completed.",
    mildLabel: "1 (Very mild)",
    worstLabel: "10 (Worst imaginable)",

    // Voice Assistant
    voiceTitle: "Voice Assistant",
    clickToSpeak: "Click microphone to speak your answer",
    listening: "Listening... speak clearly",
    voiceConfirmed: "Voice input confirmed",
    confirmVoiceBtn: "Confirm voice input",
    retryVoiceBtn: "Retry",

    // Documents & Prescriptions
    docsHeading: "Medical documents & prescriptions",
    uploadDocHeading: "Upload document",
    uploadDocSubheading: "Upload printed prescriptions, doctor notes, or lab scans. Real OCR text recognition will process the image asynchronously.",
    docType: "Document type",
    prescriptionType: "Prescription (Printed Rx)",
    labReportType: "Lab Report",
    dischargeSummaryType: "Discharge Summary",
    otherDocType: "Other Medical Document",
    dropZoneText: "Drop prescription image or PDF here",
    dropZoneSubtext: "Supports JPEG, PNG, WebP, TIFF, PDF (max 20 MB). Files are stored outside the public web root.",
    uploadingDoc: "Uploading & starting OCR engine…",
    refreshDocs: "Refresh",
    doctorReviewBtn: "Doctor review",
    uploadFailed: "Upload failed",
    securitySpecs: "Security & OCR specs:",
    spec1: "Files stored with non-guessable UUIDs outside web root.",
    spec2: "Authentication required to inspect or download files.",
    spec3: "Real local ONNX OCR engine (RapidOCR / CLAHE preprocessing).",
    spec4: "Corrupt/empty images safely set to needs_review.",
  },

  hi: {
    // AI Clinical Insights
    aiClinicalInsights: "एआई नैदानिक अंतर्दृष्टि",
    aiInsights: "एआई अंतर्दृष्टि",
    aiGeneratedUnverified: "एआई-जनरेटेड, असत्यापित",
    doctorVerified: "डॉक्टर द्वारा सत्यापित",
    aiNoticeText: "PatientCase AI चिकित्सक समीक्षा के लिए स्रोत-उद्धृत, एआई-जनित सुझाव प्रदान करता है। यह कोई स्वायत्त निर्णय नहीं लेता है।",
    urgencyEmergency: "आपातकालीन (EMERGENCY)",
    urgencyUrgent: "अतिआवश्यक (URGENT)",
    urgencyRoutine: "नियमित (ROUTINE)",
    runAIAnalysis: "एआई विश्लेषण चलाएं",
    runningAnalysis: "एआई पाइपलाइन चल रही है...",
    documentedDiagnoses: "दस्तावेजीकृत निदान",
    possibleDiagnoses: "संभावित विचार (डिफरेंशियल)",
    abnormalLabs: "असामान्य और गंभीर लैब परिणाम",
    allLabs: "सभी निकाले गए लैब परीक्षण",
    computedTrends: "कंप्यूटेड लैब रुझान",
    riskScores: "जोखिम स्कोर (गणनाबद्ध)",
    treatmentReference: "साक्ष्य-आधारित उपचार संदर्भ",
    aiCaseSummary: "एआई ड्राफ्ट सारांश",
    questionsToAsk: "मरीज से पूछने योग्य प्रश्न",
    accept: "स्वीकार करें",
    edit: "संपादित करें",
    reject: "अस्वीकार करें",
    caseLockedNotice: "चिकित्सक समीक्षा द्वारा केस अंतिम व लॉक कर दिया गया है। सभी अंतर्दृष्टि केवल पढ़ने योग्य हैं।",
    notCalculable: "गणना संभव नहीं",
    calculateProvisional: "उपलब्ध डेटा से गणना करें (अस्थायी)",
    sourceEvidence: "साक्ष्य / स्रोत उद्धरण",
    guidelineQuote: "दिशानिर्देश सिफारिश",
    saveEdit: "संपादन सहेजें",
    cancel: "रद्द करें",
    rejectionReason: "अस्वीकृति का कारण",
    originalScan: "मूल मेडिकल दस्तावेज़",
    extractedEntities: "निकाली गई संस्थाएं", 

    // Shell & Navigation
    menu: "मेनू",
    general: "सामान्य",
    dashboard: "डैशबोर्ड",
    portal: "मरीज़ पोर्टल",
    patients: "मरीज़ सूची",
    register: "मरीज़ पंजीकरण",
    interview: "क्लिनिकल सवाल-जवाब",
    documents: "पर्चे व दस्तावेज़",
    review: "डॉक्टर समीक्षा",
    audit: "ऑडिट लॉग",
    logout: "लॉग आउट",
    resetDemo: "डेमो डेटा रीसेट करें",
    activePatient: "सक्रिय मरीज़",
    searchPatients: "मरीज़ खोजें",
    searchPlaceholder: "नाम या आईडी द्वारा मरीज़ खोजें",
    language: "भाषा",
    selectLanguage: "भाषा / Language",
    localNeuralOcr: "लोकल न्यूरल OCR: RapidOCR ONNX (ऑफ़लाइन तैयार)",
    patientPortalSession: "मरीज़ पोर्टल सत्र",
    restrictedRecord: "केवल अपने मेडिकल रिकॉर्ड तक सीमित",

    // Roles
    doctor: "डॉक्टर",
    clinicStaff: "क्लिनिक स्टाफ",
    patient: "मरीज़",
    admin: "प्रशासक",

    // Boundary Notice
    boundaryBadge: "गैर-निदान सूचना",
    boundaryText: "यह सॉफ़्टवेयर क्लिनिकल केस-टेकिंग और जानकारी व्यवस्थित करने में सहायता करता है। यह बीमारी का निदान नहीं करता, दवाइयां नहीं लिखता और डॉक्टर के निर्णय का विकल्प नहीं है।",

    // Login & Auth
    loginTitle: "PatientCase AI",
    loginSubtitle: "क्लिनिकल केस-टेकिंग और चिकित्सक समीक्षा प्रणाली।",
    signInTab: "लॉग इन करें",
    signUpTab: "नए मरीज़ का पंजीकरण",
    quickDemoRoles: "डेमो भूमिका चुनें:",
    existingPatientNotice: "मौजूदा मरीज़ खाते में प्रवेश करें।",
    patientRoleDesc: "मार्गदर्शित इनटेक प्रश्नावली और व्यक्तिगत स्वास्थ्य रिकॉर्ड।",
    newPatientPrompt: "क्या आप अस्पताल में पहली बार आए हैं?",
    createAccountLink: "नया मरीज़ खाता बनाएं →",
    alreadyRegisteredPrompt: "क्या पहले से पंजीकृत हैं?",
    signInLink: "पुराने खाते में लॉग इन करें →",
    username: "यूज़रनेम",
    password: "पासवर्ड",
    signInButton: "लॉग इन करें",
    signingIn: "लॉग इन हो रहा है...",

    // New Patient Registration / Signup
    fullName: "पूरा नाम",
    fullNamePlaceholder: "उदा. रमेश कुमार",
    age: "उम्र",
    agePlaceholder: "उदा. 45",
    gender: "लिंग",
    genderSelect: "लिंग चुनें",
    male: "पुरुष",
    female: "महिला",
    other: "अन्य",
    phone: "मोबाइल नंबर",
    phonePlaceholder: "10 अंकों का मोबाइल नंबर",
    prefLang: "पसंदीदा भाषा",
    chiefComplaint: "आने का मुख्य कारण / मुख्य तकलीफ",
    complaintPlaceholder: "अपने लक्षणों का संक्षिप्त विवरण दें (उदा. 2 दिन से सिरदर्द)",
    consentAgreement: "मैं प्री-कंसल्टेशन केस-टेकिंग और डॉक्टर समीक्षा के लिए सहमति देता/देती हूँ।",
    registerButton: "खाता बनाएं और सवाल-जवाब शुरू करें",
    registering: "खाता बनाया जा रहा है...",

    // Patient Portal
    portalHeading: "मरीज़ इनटेक पोर्टल",
    portalSubheading: "डॉक्टर परामर्श से पहले अपनी स्वास्थ्य जानकारी दर्ज करें।",
    step1Title: "चरण 1: पंजीकृत",
    step1Badge: "✓ सहमति सत्यापित",
    step1Heading: "पहचान व सहमति",
    step1Desc: "जनसांख्यिकी, संपर्क और इनटेक सहमति दर्ज।",
    step2Title: "चरण 2: दस्तावेज़",
    step2Heading: "पर्चे व नुस्खे अपलोड करें",
    step2Desc: "दवा पर्ची या टेस्ट रिपोर्ट स्थानीय रूप से अपलोड करें।",
    step2Button: "पर्चे अपलोड करें",
    step3Title: "चरण 3: स्वास्थ्य प्रश्नावली",
    step3Heading: "अनुकूली क्लिनिकल सवाल-जवाब",
    step3Desc: "अपने लक्षणों और मेडिकल हिस्ट्री के आसान सवालों के उत्तर दें।",
    startInterview: "सवाल-जवाब शुरू करें",
    resumeInterview: "सवाल-जवाब जारी रखें",
    reviewCase: "पूरा विवरण देखें",
    docCountLabel: "अपलोड किए गए",

    // Adaptive Interview
    interviewHeading: "अनुकूली क्लिनिकल सवाल-जवाब",
    ruleBased: "नियम आधारित इंजन",
    questionProgress: "प्रश्न",
    of: "का",
    continueBtn: "आगे बढ़ें",
    backBtn: "पीछे",
    skipBtn: "उत्तर नहीं देना (छोड़ें)",
    saveExitBtn: "सहेजें और बाहर निकलें",
    confirmFinishBtn: "पुष्टि करें और समाप्त करें",
    editBtn: "संपादित करें",
    savingBtn: "सहेजा जा रहा है...",
    submittingBtn: "जमा हो रहा है...",
    reviewAnswersHeading: "अपने उत्तरों की समीक्षा करें",
    reviewAnswersSubheading: "डॉक्टर को भेजने से पहले अपने जवाबों की जांच कर लें। कोई भी जवाब बदलने पर आगे के सवाल अपने-आप अपडेट हो जाएंगे।",
    interviewCompleteHeading: "सवाल-जवाब पूरे हुए:",
    interviewCompleteSubheading: "आपकी क्लिनिकल जानकारी सफलतापूर्वक दर्ज कर ली गई है। अब यह डॉक्टर की समीक्षा के लिए तैयार है।",
    openDoctorReviewBtn: "डॉक्टर समीक्षा खोलें",
    uploadPrescriptionsBtn: "नुस्खे अपलोड करें",
    restartInterviewBtn: "पुनः शुरू करें",
    adaptivePathHeading: "अनुकूली पथ",
    adaptivePathDesc: "इंजन आपके पिछले जवाबों के आधार पर ही अगले प्रासंगिक सवाल पूछता है।",
    followUpsHeading: "आपके लिए जोड़े गए फॉलो-अप सवाल",
    noFollowUpsYet: "आगे के फॉलो-अप सवाल देखने के लिए पहले सवालों के जवाब दें।",
    requiredChecklist: "आवश्यक जानकारी चेकलिस्ट",
    allFieldsCompleted: "सभी आवश्यक क्लिनिकल फ़ील्ड पूरे कर लिए गए हैं।",
    mildLabel: "1 (बहुत हल्का)",
    worstLabel: "10 (असहनीय दर्द)",

    // Voice Assistant
    voiceTitle: "आवाज़ सहायक",
    clickToSpeak: "बोलकर जवाब देने के लिए माइक दबाएं",
    listening: "सुन रहे हैं... अब बोलें",
    voiceConfirmed: "आवाज़ इनपुट सत्यापित हुआ",
    confirmVoiceBtn: "आवाज़ इनपुट की पुष्टि करें",
    retryVoiceBtn: "दोबारा बोलें",

    // Documents & Prescriptions
    docsHeading: "मेडिकल दस्तावेज़ और नुस्खे",
    uploadDocHeading: "दस्तावेज़ अपलोड करें",
    uploadDocSubheading: "डॉक्टर का पर्चा, डिस्चार्ज स्लिप या लैब रिपोर्ट अपलोड करें। स्थानीय OCR ऑन-डिवाइस काम करता है।",
    docType: "दस्तावेज़ का प्रकार",
    prescriptionType: "डॉक्टर का पर्चा / नुस्खा (Prescription)",
    labReportType: "लैब रिपोर्ट (Lab Report)",
    dischargeSummaryType: "डिस्चार्ज सारांश (Discharge Summary)",
    otherDocType: "अन्य मेडिकल दस्तावेज़ (Other)",
    dropZoneText: "पर्चे की फ़ोटो या PDF यहाँ छोड़ें",
    dropZoneSubtext: "JPEG, PNG, WebP, TIFF, PDF समर्थित (अधिकतम 20 MB)। फ़ाइलें सुरक्षित रखी जाती हैं।",
    uploadingDoc: "अपलोड हो रहा है और OCR शुरू हो रहा है…",
    refreshDocs: "रीफ़्रेश करें",
    doctorReviewBtn: "डॉक्टर समीक्षा",
    uploadFailed: "अपलोड विफल",
    securitySpecs: "सुरक्षा व OCR विशेषताएं:",
    spec1: "फ़ाइलें वेब रूट के बाहर गैर-अनुमानित UUID के साथ सुरक्षित रखी जाती हैं।",
    spec2: "फ़ाइलों को देखने या डाउनलोड करने के लिए प्रमाणीकरण आवश्यक है।",
    spec3: "वास्तविक स्थानीय ONNX OCR इंजन (RapidOCR / CLAHE प्रीप्रोसेसिंग)।",
    spec4: "धुंधली या खाली फ़ोटो सुरक्षित रूप से समीक्षा हेतु चिह्नित की जाती हैं।",
  },

  mr: {
    // AI Clinical Insights
    aiClinicalInsights: "एआय क्लिनिकल अंतर्दृष्टी",
    aiInsights: "एआय अंतर्दृष्टी",
    aiGeneratedUnverified: "एआय-निर्मित, पडताळणी बाकी",
    doctorVerified: "डॉक्टरांनी पडताळलेले",
    aiNoticeText: "PatientCase AI डॉक्टरांच्या पुनरावलोकनासाठी संदर्भ-उद्धृत, एआय-व्युत्पन्न सूचना देते. हे कोणतेही स्वायत्त निर्णय घेत नाही.",
    urgencyEmergency: "तातडीची आणीबाणी (EMERGENCY)",
    urgencyUrgent: "अतिआवश्यक (URGENT)",
    urgencyRoutine: "नियमित (ROUTINE)",
    runAIAnalysis: "एआय विश्लेषण चालवा",
    runningAnalysis: "एआय पाइपलाइन सुरू आहे...",
    documentedDiagnoses: "नोंदणीकृत निदान",
    possibleDiagnoses: "संभाव्य विचार (डिफरेंशियल)",
    abnormalLabs: "असामान्य व गंभीर प्रयोगशाळा निकाल",
    allLabs: "सर्व काढलेल्या प्रयोगशाळा चाचण्या",
    computedTrends: "प्रयोगशाळा ट्रेंड्स",
    riskScores: "धोका गुणसंख्या",
    treatmentReference: "मार्गदर्शक उपचार संदर्भ",
    aiCaseSummary: "एआय मसुदा सारांश",
    questionsToAsk: "रुग्णाला विचारण्याचे प्रश्न",
    accept: "स्वीकारा",
    edit: "संपादित करा",
    reject: "नाकारा",
    caseLockedNotice: "डॉक्टरांच्या अंतिम पडताळणीनंतर केस लॉक करण्यात आली आहे. सर्व माहिती केवळ वाचण्यासाठी उपलब्ध आहे.",
    notCalculable: "गणना शक्य नाही",
    calculateProvisional: "उपलब्ध माहितीवरून मोजा (तात्पुरते)",
    sourceEvidence: "पुरावा / मूळ संदर्भ",
    guidelineQuote: "मार्गदर्शक तत्त्व शिफारस",
    saveEdit: "बदल जतन करा",
    cancel: "रद्द करा",
    rejectionReason: "नाकारण्याचे कारण",
    originalScan: "मूळ वैद्यकीय दस्तऐवज",
    extractedEntities: "काढलेली घटक माहिती", 

    // Shell & Navigation
    menu: "मेनू",
    general: "सामान्य",
    dashboard: "डॅशबोर्ड",
    portal: "रुग्ण पोर्टल",
    patients: "रुग्ण यादी",
    register: "रुग्ण नोंदणी",
    interview: "क्लिनिकल मुलाखत",
    documents: "कागदपत्रे व प्रिस्क्रिप्शन",
    review: "डॉक्टर पुनरावलोकन",
    audit: "ऑडिट नोंदी",
    logout: "लॉग आऊट",
    resetDemo: "डेमो डेटा रीसेट करा",
    activePatient: "सक्रिय रुग्ण",
    searchPatients: "रुग्ण शोधा",
    searchPlaceholder: "नाव किंवा आयडीने रुग्ण शोधा",
    language: "भाषा",
    selectLanguage: "भाषा / Language",
    localNeuralOcr: "स्थानिक न्यूरल OCR: RapidOCR ONNX (ऑफलाइन सज्ज)",
    patientPortalSession: "रुग्ण पोर्टल सत्र",
    restrictedRecord: "केवळ स्वतःच्या वैद्यकीय नोंदीपुरते मर्यादित",

    // Roles
    doctor: "डॉक्टर",
    clinicStaff: "क्लिनिक कर्मचारी",
    patient: "रुग्ण",
    admin: "प्रशासक",

    // Boundary Notice
    boundaryBadge: "गैर-निदान सूचना",
    boundaryText: "हे सॉफ्टवेअर क्लिनिकल केस-टेकिंग आणि माहिती व्यवस्थापनासाठी मदत करते. हे रोगांचे निदान करत नाही, औषधे लिहून देत नाही आणि डॉक्टरांच्या निर्णयाचा पर्याय नाही.",

    // Login & Auth
    loginTitle: "PatientCase AI",
    loginSubtitle: "क्लिनिकल केस-टेकिंग आणि डॉक्टर पुनरावलोकन प्रणाली.",
    signInTab: "लॉग इन करा",
    signUpTab: "नवीन रुग्ण नोंदणी",
    quickDemoRoles: "डेमो भूमिका निवडा:",
    existingPatientNotice: "विद्यमान रुग्ण खात्यात प्रवेश करा.",
    patientRoleDesc: "मार्गदर्शित इनटेक प्रश्नावली आणि वैयक्तिक आरोग्य रेकॉर्ड.",
    newPatientPrompt: "रुग्णालयात पहिल्यांदाच आला आहात का?",
    createAccountLink: "नवीन रुग्ण खाते तयार करा →",
    alreadyRegisteredPrompt: "आधीच नोंदणी केली आहे का?",
    signInLink: "आधीच्या खात्यात लॉग इन करा →",
    username: "वापरकर्ता नाव (Username)",
    password: "पासवर्ड",
    signInButton: "लॉग इन करा",
    signingIn: "लॉग इन होत आहे...",

    // New Patient Registration / Signup
    fullName: "पूर्ण नाव",
    fullNamePlaceholder: "उदा. रमेश कुमार",
    age: "वय",
    agePlaceholder: "उदा. ४५",
    gender: "लिंग",
    genderSelect: "लिंग निवडा",
    male: "पुरुष",
    female: "स्त्री",
    other: "इतर",
    phone: "मोबाइल नंबर",
    phonePlaceholder: "१० अंकी मोबाइल नंबर",
    prefLang: "पसंतीची भाषा",
    chiefComplaint: "येण्याचे मुख्य कारण / मुख्य त्रास",
    complaintPlaceholder: "आपल्या त्रासाचे थोडक्यात वर्णन करा (उदा. २ दिवसांपासून डोकेदुखी)",
    consentAgreement: "मी प्री-कंसल्टेशन केस-टेकिंग आणि डॉक्टर पुनरावलोकनासाठी संमती देतो/देते.",
    registerButton: "खाते तयार करा आणि माहिती सुरू करा",
    registering: "खाते तयार होत आहे...",

    // Patient Portal
    portalHeading: "रुग्ण इनटेक पोर्टल",
    portalSubheading: "डॉक्टरांच्या भेटीपूर्वी आपली आरोग्यविषयक माहिती पूर्ण करा.",
    step1Title: "टप्पा १: नोंदणीकृत",
    step1Badge: "✓ संमती सत्यापित",
    step1Heading: "ओळख व संमती",
    step1Desc: "लोकसंख्याशास्त्र, संपर्क आणि इनटेक संमती नोंदवली.",
    step2Title: "टप्पा २: कागदपत्रे",
    step2Heading: "प्रिस्क्रिप्शन व रिपोर्ट अपलोड करा",
    step2Desc: "प्रिस्क्रिप्शन किंवा लॅब रिपोर्ट स्थानिकरित्या अपलोड करा.",
    step2Button: "प्रिस्क्रिप्शन अपलोड करा",
    step3Title: "टप्पा ३: आरोग्य मुलाखत",
    step3Heading: "अनुकूली क्लिनिकल मुलाखत",
    step3Desc: "आपल्या लक्षणांविषयी आणि वैद्यकीय इतिहासाबद्दल सोप्या प्रश्नांची उत्तरे द्या.",
    startInterview: "मुलाखत सुरू करा",
    resumeInterview: "मुलाखत पुढे सुरू ठेवा",
    reviewCase: "पूर्ण तपशील पहा",
    docCountLabel: "अपलोड केले",

    // Adaptive Interview
    interviewHeading: "अनुकूली क्लिनिकल मुलाखत",
    ruleBased: "नियम-आधारित इंजिन",
    questionProgress: "प्रश्न",
    of: "पैकी",
    continueBtn: "पुढे जा",
    backBtn: "मागे",
    skipBtn: "उत्तर द्यायचे नाही (वगळा)",
    saveExitBtn: "जतन करा आणि बाहेर पडा",
    confirmFinishBtn: "पुष्टी करा आणि पूर्ण करा",
    editBtn: "संपादित करा",
    savingBtn: "जतन करत आहे...",
    submittingBtn: "सादर करत आहे...",
    reviewAnswersHeading: "आपल्या उत्तरांचे पुनरावलोकन करा",
    reviewAnswersSubheading: "डॉक्टरांकडे सादर करण्यापूर्वी आपली उत्तरे तपासा. उत्तर बदलल्यास पुढील प्रश्न आपोआप अद्यतनित होतील.",
    interviewCompleteHeading: "मुलाखत पूर्ण झाली:",
    interviewCompleteSubheading: "आपली क्लिनिकल माहिती सुरक्षितपणे नोंदवली गेली आहे. आता डॉक्टर तपासणीसाठी तयार आहे.",
    openDoctorReviewBtn: "डॉक्टर पुनरावलोकन उघडा",
    uploadPrescriptionsBtn: "प्रिस्क्रिप्शन अपलोड करा",
    restartInterviewBtn: "मुलाखत पुन्हा सुरू करा",
    adaptivePathHeading: "अनुकूली मार्ग",
    adaptivePathDesc: "इंजिन आपल्या आधीच्या उत्तरांवरूनच पुढील योग्य प्रश्न विचारते.",
    followUpsHeading: "तुमच्यासाठी जोडलेले पुढील प्रश्न",
    noFollowUpsYet: "पुढील प्रश्न पाहण्यासाठी आधीच्या प्रश्नांची उत्तरे द्या.",
    requiredChecklist: "आवश्यक माहिती यादी",
    allFieldsCompleted: "सर्व आवश्यक क्लिनिकल बाबी पूर्ण केल्या आहेत.",
    mildLabel: "१ (अतिशय सौम्य)",
    worstLabel: "१० (असह्य वेदना)",

    // Voice Assistant
    voiceTitle: "व्हॉईस असिस्टंट (आवाज सहाय्यक)",
    clickToSpeak: "बोलण्यासाठी माइक दाबा",
    listening: "ऐकत आहोत... आता बोला",
    voiceConfirmed: "व्हॉईस इनपुट पुष्टी झाली",
    confirmVoiceBtn: "व्हॉईस इनपुट पुष्टी करा",
    retryVoiceBtn: "पुन्हा बोला",

    // Documents & Prescriptions
    docsHeading: "वैद्यकीय कागदपत्रे व प्रिस्क्रिप्शन",
    uploadDocHeading: "कागदपत्र अपलोड करा",
    uploadDocSubheading: "डॉक्टरांचे प्रिस्क्रिप्शन किंवा लॅब रिपोर्ट अपलोड करा. स्थानिक OCR तंत्रज्ञान ऑन-डिव्हाइस मजकूर वाचते.",
    docType: "कागदपत्राचा प्रकार",
    prescriptionType: "डॉक्टरांचे प्रिस्क्रिप्शन (Prescription)",
    labReportType: "लॅब रिपोर्ट (Lab Report)",
    dischargeSummaryType: "डिस्चार्ज समरी (Discharge Summary)",
    otherDocType: "इतर वैद्यकीय कागदपत्र (Other)",
    dropZoneText: "प्रिस्क्रिप्शन फोटो किंवा PDF येथे टाका",
    dropZoneSubtext: "JPEG, PNG, WebP, TIFF, PDF समर्थित (कमाल २० MB). फाइल्स सुरक्षित ठेवल्या जातात.",
    uploadingDoc: "अपलोड होत आहे व OCR सुरू होत आहे…",
    refreshDocs: "रिफ्रेश करा",
    doctorReviewBtn: "डॉक्टर पुनरावलोकन",
    uploadFailed: "अपलोड अयशस्वी",
    securitySpecs: "सुरक्षा व OCR वैशिष्ट्ये:",
    spec1: "फाइल्स वेब रूटबाहेर सुरक्षित ठेवल्या जातात.",
    spec2: "फाइल्स पाहण्यासाठी प्रमाणीकरण आवश्यक आहे.",
    spec3: "स्थानिक ONNX OCR इंजिन (RapidOCR / CLAHE प्रीप्रोसेसिंग).",
    spec4: "अस्पष्ट किंवा रिकाम्या फाइल्स डॉक्टर पुनरावलोकनासाठी पाठवल्या जातात.",
  },
};

/**
 * Translate a UI key to active language
 */
export function t(key, lang = "en") {
  const normLang = (lang || "en").toLowerCase();
  const dict = UI_TRANSLATIONS[normLang] || UI_TRANSLATIONS.en;
  return dict[key] || UI_TRANSLATIONS.en[key] || key;
}

/**
 * Fill {name}-style placeholders in an already translated string
 */
export function fmtT(str, vars = {}) {
  return String(str).replace(/\{(\w+)\}/g, (m, k) => (k in vars ? vars[k] : m));
}

/**
 * Parse a backend timestamp. The API stores naive UTC datetimes, so a value
 * without an explicit offset must be read as UTC, not local time.
 */
export function parseServerDate(ts) {
  if (!ts) return null;
  if (ts instanceof Date) return ts;
  const s = String(ts);
  return new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(s) || !s.includes("T") && !s.includes(" ") ? s : `${s.replace(" ", "T")}Z`);
}

// Merge page-level strings (clinician pages, intake pages, shared UI)
for (const lang of Object.keys(UI_TRANSLATIONS)) {
  UI_TRANSLATIONS[lang] = { ...PAGE_TRANSLATIONS[lang], ...INTAKE_TRANSLATIONS[lang], ...UI_TRANSLATIONS[lang], ...AI_TRANSLATIONS[lang], ...VISIT_TRANSLATIONS[lang] };
}

// Question fallback dictionary (generated from the backend; see i18n_questions.js)
export { LOCAL_QUESTION_TRANSLATIONS };

/**
 * Retrieve question translations with fallback
 */
export function getLocalQuestionTranslation(key, lang = "en") {
  const normLang = (lang || "en").toLowerCase();
  const qObj = LOCAL_QUESTION_TRANSLATIONS[key];
  if (!qObj) return null;
  return qObj[normLang] || qObj.en || null;
}
