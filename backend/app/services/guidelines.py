"""
services/guidelines.py
----------------------
Local Guideline Library and Evidence Retrieval Service.
Implements the core safety rule:
  The LLM must NEVER recall drug doses from memory.
  Doses may be displayed ONLY if directly quoted from a retrieved guideline passage,
  accompanied by full source citation.
  All sample entries are explicitly labeled: 'SAMPLE – replace with verified source'.
"""
import re
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from app.models import GuidelinePassage

SAMPLE_GUIDELINES = [
    {
        "source": "Standard Treatment Workflow Guidelines (SAMPLE – replace with verified source)",
        "version_date": "2026-01-15",
        "condition_or_topic": "Type 2 Diabetes Mellitus",
        "section": "Section 4.1: Initial Pharmacological Management",
        "passage_text": (
            "In adults with newly diagnosed Type 2 Diabetes Mellitus without symptomatic hyperglycemia, "
            "metformin is recommended as the initial first-line oral therapy provided renal function is preserved (eGFR >= 30 mL/min). "
            "Initial dosing: Metformin 500 mg orally once or twice daily with meals, titrating gradually up to 1000 mg twice daily. "
            "Contraindications: Severe renal impairment (eGFR < 30 mL/min/1.73m2), metabolic acidosis, or severe liver dysfunction. "
            "SAMPLE – replace with verified source."
        ),
        "citations": ["Standard Treatment Workflow Guidelines (SAMPLE – replace with verified source), Sec 4.1"],
        "is_sample": True
    },
    {
        "source": "Standard Hypertension Management Protocol (SAMPLE – replace with verified source)",
        "version_date": "2026-02-01",
        "condition_or_topic": "Essential Hypertension",
        "section": "Section 3.2: First-Line Monotherapy",
        "passage_text": (
            "For non-black adult patients with confirmed Stage 1 or Stage 2 Essential Hypertension without compelling contraindications, "
            "first-line agents include ACE inhibitors, ARBs, or dihydropyridine calcium channel blockers. "
            "Initial dosing: Amlodipine 5 mg orally once daily, titrating to 10 mg daily as clinically indicated, or "
            "Telmisartan 40 mg orally once daily with blood pressure reassessment at 4 weeks. "
            "SAMPLE – replace with verified source."
        ),
        "citations": ["Standard Hypertension Protocol (SAMPLE – replace with verified source), Sec 3.2"],
        "is_sample": True
    },
    {
        "source": "Adult Community-Acquired Infection Guidelines (SAMPLE – replace with verified source)",
        "version_date": "2026-03-10",
        "condition_or_topic": "Community-Acquired Pneumonia",
        "section": "Section 2.3: Outpatient Empirical Therapy",
        "passage_text": (
            "In low-severity community-acquired pneumonia (CURB-65 score 0–1) without comorbidities, "
            "first-line empirical therapy is Amoxicillin 500 mg orally three times daily for 5 days. "
            "In patients with penicillin hypersensitivity or atypical coverage requirements, Azithromycin 500 mg on day 1 followed by 250 mg once daily on days 2–5. "
            "SAMPLE – replace with verified source."
        ),
        "citations": ["Adult Infection Guidelines (SAMPLE – replace with verified source), Sec 2.3"],
        "is_sample": True
    },
    {
        "source": "Dyslipidemia Primary Prevention Guidelines (SAMPLE – replace with verified source)",
        "version_date": "2026-01-20",
        "condition_or_topic": "Dyslipidemia",
        "section": "Section 5.1: Statin Therapy",
        "passage_text": (
            "Moderate-intensity statin therapy is indicated for patients with documented atherosclerotic cardiovascular disease or diabetes aged 40–75. "
            "Initial dosing: Atorvastatin 20 mg orally once daily taken in the evening, with lipid panel reassessment in 8–12 weeks. "
            "Contraindications: Active liver disease, unexplained persistent elevation of serum transaminases, pregnancy. "
            "SAMPLE – replace with verified source."
        ),
        "citations": ["Dyslipidemia Guidelines (SAMPLE – replace with verified source), Sec 5.1"],
        "is_sample": True
    }
]


async def seed_guideline_passages(db: AsyncSession) -> int:
    """Seed sample guidelines into database if empty (idempotent)."""
    count = await db.scalar(select(GuidelinePassage.id).limit(1))
    if count is not None:
        return 0

    inserted = 0
    for g in SAMPLE_GUIDELINES:
        obj = GuidelinePassage(
            source=g["source"],
            version_date=g["version_date"],
            condition_or_topic=g["condition_or_topic"],
            section=g["section"],
            passage_text=g["passage_text"],
            citations=g["citations"],
            is_sample=g["is_sample"]
        )
        db.add(obj)
        inserted += 1
    await db.commit()
    return inserted


async def search_guidelines(
    query_text: str,
    db: AsyncSession,
    limit: int = 3
) -> List[Dict[str, Any]]:
    """
    Search guideline passages by keywords matching condition_or_topic or text.
    """
    if not query_text:
        return []

    tokens = [t.strip().lower() for t in re.split(r"[\s,;]+", query_text) if len(t.strip()) > 2]
    if not tokens:
        return []

    # Search by topic or passage keywords
    conditions = []
    for tok in tokens[:4]:
        pattern = f"%{tok}%"
        conditions.append(GuidelinePassage.condition_or_topic.ilike(pattern))
        conditions.append(GuidelinePassage.passage_text.ilike(pattern))

    stmt = select(GuidelinePassage).where(or_(*conditions)).limit(limit)
    rows = (await db.scalars(stmt)).all()

    results = []
    for r in rows:
        results.append({
            "id": r.id,
            "source": r.source,
            "version_date": r.version_date,
            "condition_or_topic": r.condition_or_topic,
            "section": r.section,
            "passage_text": r.passage_text,
            "citations": r.citations or [],
            "is_sample": r.is_sample,
        })
    return results


def verify_dose_is_quoted(dose_text: str, passage_text: str) -> bool:
    """
    Enforces the non-negotiable rule:
    Doses must be verbatim or normalized substrings of the retrieved passage text.
    Returns True if dose_text appears in passage_text.
    """
    if not dose_text or not passage_text:
        return False

    clean_dose = re.sub(r"[^\w\s]", "", dose_text.lower()).strip()
    clean_passage = re.sub(r"[^\w\s]", "", passage_text.lower()).strip()

    return clean_dose in clean_passage

