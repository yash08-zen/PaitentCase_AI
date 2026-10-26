// Synthetic patients and cases. Not real people.
const rx = { id: "d1", type: "Prescription", file: "prescription_city_clinic.jpg", issuer: "Dr. A. Mehta, City Clinic", date: "12 Sep 2026",
  items: [
    { label: "Medicine", value: "Metformin 500 mg, twice daily", kind: "med", name: "Metformin", dose: "500 mg", conf: 94 },
    { label: "Medicine", value: "Amlodipine 5 mg, once daily", kind: "med", name: "Amlodipine", dose: "5 mg", conf: 91 },
    { label: "Prescriber", value: "Dr. A. Mehta", conf: 97 },
  ] };
const lab = { id: "d2", type: "Lab report", file: "lab_report_thyroid.pdf", issuer: "Sunrise Diagnostics", date: "02 Oct 2026",
  items: [{ label: "TSH", value: "3.2 mIU/L", conf: 93 }, { label: "Report date", value: "02 Oct 2026", conf: 96 }] };

export const PATIENTS = [
  { id: "P-1001", name: "Rahul Sharma", age: 42, gender: "Male", phone: "98765 43210", language: "Hindi", emergency: "Neha Sharma", registered: "17 Oct 2026" },
  { id: "P-1002", name: "Anita Verma", age: 29, gender: "Female", phone: "98220 11874", language: "English", emergency: "Sunil Verma", registered: "17 Oct 2026" },
  { id: "P-1003", name: "Mohammed Iqbal", age: 61, gender: "Male", phone: "99870 25531", language: "English", emergency: "Farah Iqbal", registered: "16 Oct 2026" },
  { id: "P-1004", name: "Sneha Patil", age: 35, gender: "Female", phone: "97650 88123", language: "Marathi", emergency: "", registered: "16 Oct 2026" },
  { id: "P-1005", name: "Kavita Joshi", age: 54, gender: "Female", phone: "98900 44512", language: "Hindi", emergency: "Ravi Joshi", registered: "15 Oct 2026" },
];

export const emptyCase = () => ({ answers: {}, skipped: [], stack: [], stage: "new", docs: [], flags: {}, notes: "", finalized: false });

export const CASES = {
  "P-1001": { ...emptyCase(), stage: "complete", docs: [rx], skipped: ["allergy"],
    answers: { complaint: "Chest discomfort", duration: "1 to 3 days", severity: 6, exertion: "Yes", assoc: ["Sweating"], fever: "No", conds: ["Hypertension"], meds: "No", surgery: "No", family: "Yes" },
    stack: ["complaint", "duration", "severity", "exertion", "assoc", "fever", "conds", "meds", "allergy", "surgery", "family"] },
  "P-1002": { ...emptyCase(), stage: "complete", docs: [lab],
    answers: { complaint: "Headache", duration: "More than a week", severity: 4, freq: "A few times a week", assoc: ["Nausea"], fever: "No", conds: ["Thyroid disorder"], meds: "Yes", medname: "Levothyroxine", meddose: "50 mcg, once daily", allergy: "Yes", allergen: "Penicillin", reaction: "Rash", surgery: "No", family: "No" },
    stack: ["complaint", "duration", "severity", "freq", "assoc", "fever", "conds", "meds", "medname", "meddose", "allergy", "allergen", "reaction", "surgery", "family"] },
  "P-1003": { ...emptyCase(), stage: "interview",
    answers: { complaint: "Abdominal pain", duration: "Less than a day", severity: 7, location: "Lower right", worse: "Yes" },
    stack: ["complaint", "duration", "severity", "location", "worse"] },
  "P-1004": emptyCase(),
  "P-1005": { ...emptyCase(), stage: "complete", finalized: true, notes: "Reviewed. Advised rest and fluids.",
    answers: { complaint: "Fever", duration: "1 to 3 days", severity: 5, conds: ["None"], meds: "No", allergy: "No", surgery: "No", family: "No" },
    stack: ["complaint", "duration", "severity", "conds", "meds", "allergy", "surgery", "family"] },
};
