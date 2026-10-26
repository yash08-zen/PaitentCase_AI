// Rule-based interview, flag and completeness logic. Pure functions, ready to move behind an API later.
import { QUESTIONS } from "../data/questions";

export const relevant = (a) => QUESTIONS.filter((q) => !q.when || q.when(a));
export const nextQ = (c) => relevant(c.answers).find((q) => !(q.key in c.answers) && !c.skipped.includes(q.key)) || null;
export const progress = (c) => {
  const r = relevant(c.answers);
  return { done: r.filter((q) => q.key in c.answers || c.skipped.includes(q.key)).length, total: r.length };
};
export const skippedByRules = (a) => QUESTIONS.filter((q) => q.when && !q.when(a));
export const fmt = (v) => (Array.isArray(v) ? v.join(", ") : v === undefined || v === null ? "" : String(v));

const medsSaid = (a) => (a.meds === "No" ? [] : a.meds === "Yes" ? (a.medname || "").split(",").map((s) => s.trim().toLowerCase()).filter(Boolean) : null);
export const docMeds = (c) => c.docs.flatMap((d) => d.items.filter((i) => i.kind === "med").map((i) => ({ ...i, file: d.file })));

export function conflicts(c) {
  const said = medsSaid(c.answers);
  if (said === null) return [];
  return docMeds(c)
    .filter((m) => !said.some((s) => m.name.toLowerCase().includes(s) || s.includes(m.name.toLowerCase())))
    .map((m) => ({ id: "c:" + m.name, type: "conflict", title: `Potential medication discrepancy: ${m.name}`,
      patient: said.length ? said.join(", ") : "No current medication", document: `${m.name} ${m.dose}`, file: m.file }));
}
export function missing(c) {
  return relevant(c.answers).filter((q) => !(q.key in c.answers))
    .map((q) => ({ id: "m:" + q.key, type: "missing", title: `${q.label} not provided`, section: q.section, why: c.skipped.includes(q.key) ? "Skipped by patient" : "Not yet asked" }));
}
export const flagsOf = (c) => [...conflicts(c), ...missing(c)].map((f) => ({ ...f, status: c.flags[f.id] || "open" }));
export const openFlags = (c) => flagsOf(c).filter((f) => f.status === "open");

export function completeness(c) {
  const a = c.answers, r = relevant(a), answered = r.filter((q) => q.key in a).length;
  const half = (k1, k2) => (a[k1] ? 0.5 : 0) + (a[k2] ? 0.5 : 0);
  const cf = conflicts(c), reviewed = cf.filter((x) => c.flags[x.id]).length;
  const parts = [
    { label: "History completeness", weight: 40, score: r.length ? answered / r.length : 0, note: `${answered} of ${r.length} relevant questions answered` },
    { label: "Medication information", weight: 15, score: !("meds" in a) ? 0 : a.meds === "Yes" ? half("medname", "meddose") : 1, note: !("meds" in a) ? "Medication question not answered" : a.meds === "Yes" ? "Medicine name and dose" : "No medication reported" },
    { label: "Allergy information", weight: 15, score: !("allergy" in a) ? 0 : a.allergy === "Yes" ? half("allergen", "reaction") : 1, note: !("allergy" in a) ? "Allergy information missing" : a.allergy === "Yes" ? "Allergen and reaction" : "No allergies reported" },
    { label: "Documents processed", weight: 10, score: c.docs.length ? 1 : 0, note: c.docs.length ? `${c.docs.length} document(s) added` : "No document added" },
    { label: "Conflict review", weight: 20, score: cf.length ? reviewed / cf.length : 1, note: cf.length ? `${reviewed} of ${cf.length} discrepancies reviewed` : "No discrepancies found" },
  ].map((p) => ({ ...p, points: Math.round(p.weight * p.score * 10) / 10 }));
  return { total: Math.round(parts.reduce((s, p) => s + p.weight * p.score, 0)), parts };
}

export function findings(c) {
  const a = c.answers, dm = docMeds(c), cf = conflicts(c);
  const verified = cf.length > 0 && cf.every((x) => c.flags[x.id] === "verified");
  const row = (label, key, fmtFn) => {
    const v = a[key] === undefined ? "" : fmtFn ? fmtFn(a[key]) : fmt(a[key]);
    return { label, value: v, source: "patient", missing: v === "" };
  };
  return [
    row("Chief complaint", "complaint"), row("Duration", "duration"), row("Severity", "severity", (v) => `${v} / 10`),
    ...(a.location ? [row("Pain location", "location")] : []), ...(a.exertion ? [row("Worse with activity", "exertion")] : []),
    ...(a.freq ? [row("Frequency", "freq")] : []), ...(a.assoc ? [row("Associated symptoms", "assoc")] : []),
    row("Medical history", "conds"),
    { label: "Medication (patient)", value: a.meds === "No" ? "No current medication" : a.meds === "Yes" ? `${fmt(a.medname)} ${fmt(a.meddose)}`.trim() : "", source: "patient", missing: !("meds" in a) },
    ...(dm.length ? [{ label: "Medication (documents)", value: dm.map((m) => `${m.name} ${m.dose}`).join(", "), source: verified ? "verified" : "document", missing: false }] : []),
    { label: "Allergies", value: a.allergy === "No" ? "None reported" : a.allergy === "Yes" ? `${fmt(a.allergen)}${a.reaction ? " (" + a.reaction + ")" : ""}` : "", source: "patient", missing: !("allergy" in a) },
    row("Previous surgery", "surgery"), row("Family history", "family"),
  ];
}

export function summary(p, c) {
  const a = c.answers, parts = [];
  parts.push(`${p.age}-year-old ${p.gender.toLowerCase()} reporting ${(a.complaint || "an unspecified problem").toLowerCase()}${a.duration ? " for " + a.duration.toLowerCase() : ""}${a.severity ? ", severity " + a.severity + "/10" : ""}.`);
  if (a.exertion === "Yes") parts.push("Symptoms increase with physical activity.");
  if (a.assoc && !a.assoc.includes("None")) parts.push(`Associated: ${a.assoc.join(", ").toLowerCase()}.`);
  if (a.conds) parts.push(a.conds.includes("None") ? "No long-term conditions reported." : `History: ${a.conds.join(", ").toLowerCase()}.`);
  parts.push(a.meds === "No" ? "Reports no current medication." : a.meds === "Yes" ? `Reports taking ${fmt(a.medname)}.` : "Medication not recorded.");
  parts.push(a.allergy === "Yes" ? `Allergy: ${fmt(a.allergen)}.` : a.allergy === "No" ? "No known allergies." : "Allergy information not provided.");
  const cf = conflicts(c);
  if (cf.length) parts.push(`${cf.length} medication discrepancy(ies) between patient report and uploaded documents need verification.`);
  return parts.join(" ");
}

export function statusOf(c) {
  if (c.finalized) return "Finalized";
  if (c.stage === "complete") return openFlags(c).length ? "Needs review" : "Ready for review";
  return c.stage === "interview" ? "In interview" : "Registered";
}
