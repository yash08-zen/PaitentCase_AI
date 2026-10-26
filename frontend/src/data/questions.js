// Predefined branching rules. `when` decides if a question applies; `because` / `skipWhy` explain the branch.
const YN = ["Yes", "No"];
const is = (k, v) => (a) => a[k] === v;
const oneOf = (k, vs) => (a) => vs.includes(a[k]);
const PAIN = ["Chest discomfort", "Headache", "Abdominal pain"];

export const QUESTIONS = [
  { key: "complaint", label: "Chief complaint", section: "Symptoms", type: "choice", text: "What is troubling you the most today?", help: "Choose the closest match.", options: ["Headache", "Abdominal pain", "Chest discomfort", "Fever", "Cough", "Other"] },
  { key: "duration", label: "Duration", section: "Symptoms", type: "choice", text: "How long have you had this problem?", options: ["Less than a day", "1 to 3 days", "4 to 7 days", "More than a week"] },
  { key: "severity", label: "Severity (1 to 10)", section: "Symptoms", type: "scale", text: "How severe is it right now?", help: "1 is very mild. 10 is the worst you can imagine." },
  { key: "location", label: "Pain location", section: "Symptoms", type: "choice", text: "Where exactly is the pain?", options: ["Upper abdomen", "Lower right", "Lower left", "Around the navel"], when: is("complaint", "Abdominal pain"), because: "You reported abdominal pain", skipWhy: "Only asked for abdominal pain" },
  { key: "worse", label: "Getting worse", section: "Symptoms", type: "choice", text: "Has the pain become worse since it started?", options: YN, when: is("complaint", "Abdominal pain"), because: "You reported abdominal pain", skipWhy: "Only asked for abdominal pain" },
  { key: "exertion", label: "Worse with activity", section: "Symptoms", type: "choice", text: "Does it increase with physical activity?", options: YN, when: is("complaint", "Chest discomfort"), because: "You reported chest discomfort", skipWhy: "Only asked for chest discomfort" },
  { key: "freq", label: "Frequency", section: "Symptoms", type: "choice", text: "How often does the headache come?", options: ["Constant", "Daily", "A few times a week", "Rarely"], when: is("complaint", "Headache"), because: "You reported a headache", skipWhy: "Only asked for headache" },
  { key: "assoc", label: "Associated symptoms", section: "Symptoms", type: "multi", text: "Do you have any of these along with it?", help: "Select all that apply.", options: ["Nausea", "Dizziness", "Shortness of breath", "Sweating", "None"], when: oneOf("complaint", PAIN), because: "Common with pain complaints", skipWhy: "Not needed for this complaint" },
  { key: "fever", label: "Fever", section: "Symptoms", type: "choice", text: "Have you had a fever?", options: YN, when: (a) => a.complaint !== "Fever", because: "Your main problem is not fever", skipWhy: "Fever is already your main complaint" },
  { key: "conds", label: "Medical history", section: "Medical history", type: "multi", text: "Do you have any long-term conditions?", help: "Select all that apply.", options: ["Hypertension", "Diabetes", "Asthma", "Thyroid disorder", "None"] },
  { key: "meds", label: "Taking medicine", section: "Medication", type: "choice", text: "Are you currently taking any medicine?", help: "Include tablets, injections and regular supplements.", options: YN },
  { key: "medname", label: "Medicine name", section: "Medication", type: "text", text: "Which medicine are you taking?", help: "If more than one, separate the names with commas.", placeholder: "e.g. Metformin", when: is("meds", "Yes"), because: "You said you take medicine", skipWhy: "You said you take no medicine" },
  { key: "meddose", label: "Dose and frequency", section: "Medication", type: "text", text: "What is the dose, and how often do you take it?", placeholder: "e.g. 500 mg, twice daily", when: is("meds", "Yes"), because: "You said you take medicine", skipWhy: "You said you take no medicine" },
  { key: "allergy", label: "Allergies", section: "Allergies", type: "choice", text: "Do you have any known medicine or food allergies?", options: YN },
  { key: "allergen", label: "Allergic to", section: "Allergies", type: "text", text: "What are you allergic to?", placeholder: "e.g. Penicillin", when: is("allergy", "Yes"), because: "You reported an allergy", skipWhy: "You reported no allergies" },
  { key: "reaction", label: "Allergic reaction", section: "Allergies", type: "choice", text: "What happens when you are exposed to it?", options: ["Rash", "Swelling", "Breathing difficulty", "Not sure"], when: is("allergy", "Yes"), because: "You reported an allergy", skipWhy: "You reported no allergies" },
  { key: "surgery", label: "Previous surgery", section: "Background", type: "choice", text: "Have you had any surgery before?", options: YN },
  { key: "surgyear", label: "Surgery year", section: "Background", type: "text", text: "In which year was the surgery?", placeholder: "e.g. 2019", when: is("surgery", "Yes"), because: "You reported a previous surgery", skipWhy: "You reported no previous surgery" },
  { key: "family", label: "Family history", section: "Background", type: "choice", text: "Does anyone in your family have heart disease or diabetes?", options: YN },
];
