// SIMULATED OCR output. No real image processing happens in this prototype.
export const SAMPLE_DOCS = [
  { type: "Prescription", file: "prescription_city_clinic.jpg", issuer: "Dr. A. Mehta, City Clinic", date: "12 Sep 2026",
    items: [
      { label: "Medicine", value: "Metformin 500 mg, twice daily", kind: "med", name: "Metformin", dose: "500 mg", conf: 94 },
      { label: "Medicine", value: "Amlodipine 5 mg, once daily", kind: "med", name: "Amlodipine", dose: "5 mg", conf: 91 },
      { label: "Prescriber", value: "Dr. A. Mehta", conf: 97 },
    ] },
  { type: "Lab report", file: "lab_report_hba1c.pdf", issuer: "Sunrise Diagnostics", date: "05 Sep 2026",
    items: [
      { label: "HbA1c", value: "8.1 %", conf: 89 },
      { label: "Fasting glucose", value: "148 mg/dL", conf: 92 },
      { label: "Report date", value: "05 Sep 2026", conf: 96 },
    ] },
  { type: "Discharge summary", file: "discharge_summary_2025.pdf", issuer: "Lakeside Hospital", date: "14 Mar 2025",
    items: [
      { label: "Admission reason", value: "Observation for chest pain", conf: 86 },
      { label: "Length of stay", value: "2 days", conf: 93 },
      { label: "Follow-up advice", value: "Review with physician in 4 weeks", conf: 84 },
    ] },
];
