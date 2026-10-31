"""
services/guidelines.py
----------------------
Local guideline library with SQLite FTS5 retrieval.

Core safety rule: the LLM never recalls doses from memory. A dose may be shown
only when quoted verbatim from a retrieved passage, with its citation.

Sample passages live in config/guidelines_sample.json and are all labelled
'SAMPLE – replace with verified source'. They are not attributed to any real
publication. Load verified sources with scripts/ingest_guidelines.py.
"""
import json
import os
import re
from typing import Any, Dict, List

from sqlalchemy import or_, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import GuidelinePassage

SAMPLE_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "config", "guidelines_sample.json")
SAMPLE_LABEL = "SAMPLE – replace with verified source"
FTS_TABLE = "guideline_passages_fts"

_STOPWORDS = {"the", "and", "with", "for", "from", "patient", "has", "have", "not", "are", "was"}


def load_passages_file(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    passages = data["passages"] if isinstance(data, dict) else data
    required = ("source", "version_date", "condition_or_topic", "section", "passage_text")
    for p in passages:
        missing = [k for k in required if not p.get(k)]
        if missing:
            raise ValueError(f"Guideline passage missing fields {missing}: {p.get('source')}")
    return passages


async def ensure_fts(db: AsyncSession) -> bool:
    """Create and repopulate the FTS5 index. Returns False if FTS5 is unavailable."""
    try:
        await db.execute(text(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS {FTS_TABLE} "
            "USING fts5(passage_id UNINDEXED, topic, section, passage_text)"
        ))
        await db.execute(text(f"DELETE FROM {FTS_TABLE}"))
        await db.execute(text(
            f"INSERT INTO {FTS_TABLE} (passage_id, topic, section, passage_text) "
            "SELECT id, condition_or_topic, section, passage_text FROM guideline_passages"
        ))
        await db.commit()
        return True
    except OperationalError:
        await db.rollback()
        return False


async def ingest_passages(db: AsyncSession, passages: List[Dict[str, Any]], *, replace: bool = False) -> int:
    """Insert passages (optionally replacing the library) and rebuild the FTS index."""
    if replace:
        for row in (await db.scalars(select(GuidelinePassage))).all():
            await db.delete(row)
    for g in passages:
        db.add(GuidelinePassage(
            source=g["source"],
            version_date=g["version_date"],
            condition_or_topic=g["condition_or_topic"],
            section=g["section"],
            passage_text=g["passage_text"],
            citations=g.get("citations") or [],
            is_sample=bool(g.get("is_sample", False)),
        ))
    await db.commit()
    await ensure_fts(db)
    return len(passages)


async def seed_guideline_passages(db: AsyncSession) -> int:
    """Seed the sample library if empty (idempotent)."""
    exists = await db.scalar(select(GuidelinePassage.id).limit(1))
    if exists is not None:
        return 0
    passages = load_passages_file(SAMPLE_PATH)
    for p in passages:
        p["is_sample"] = True
    return await ingest_passages(db, passages)


def _to_dict(r: GuidelinePassage) -> Dict[str, Any]:
    return {
        "id": r.id,
        "source": r.source,
        "version_date": r.version_date,
        "condition_or_topic": r.condition_or_topic,
        "section": r.section,
        "passage_text": r.passage_text,
        "citations": r.citations or [],
        "is_sample": r.is_sample,
    }


def _query_tokens(query_text: str) -> List[str]:
    tokens = [t.lower() for t in re.findall(r"[A-Za-z][A-Za-z0-9-]{2,}", query_text or "")]
    seen: List[str] = []
    for t in tokens:
        if t not in _STOPWORDS and t not in seen:
            seen.append(t)
    return seen[:12]


async def search_guidelines(query_text: str, db: AsyncSession, limit: int = 3) -> List[Dict[str, Any]]:
    """Retrieve passages by FTS5 bm25 ranking; falls back to LIKE if FTS5 is unavailable."""
    tokens = _query_tokens(query_text)
    if not tokens:
        return []

    match = " OR ".join(f'"{t}"' for t in tokens)
    try:
        rows = (await db.execute(
            text(f"SELECT passage_id FROM {FTS_TABLE} WHERE {FTS_TABLE} MATCH :q "
                 f"ORDER BY bm25({FTS_TABLE}) LIMIT :lim"),
            {"q": match, "lim": limit},
        )).all()
        ids = [int(r[0]) for r in rows]
        if not ids:
            return []
        found = {p.id: p for p in (await db.scalars(
            select(GuidelinePassage).where(GuidelinePassage.id.in_(ids)))).all()}
        return [_to_dict(found[i]) for i in ids if i in found]
    except OperationalError:
        await db.rollback()

    conditions = []
    for tok in tokens[:4]:
        conditions.append(GuidelinePassage.condition_or_topic.ilike(f"%{tok}%"))
        conditions.append(GuidelinePassage.passage_text.ilike(f"%{tok}%"))
    rows = (await db.scalars(select(GuidelinePassage).where(or_(*conditions)).limit(limit))).all()
    return [_to_dict(r) for r in rows]


def verify_dose_is_quoted(dose_text: str, passage_text: str) -> bool:
    """
    A dose is acceptable only as a verbatim (punctuation/case-insensitive)
    substring of the retrieved passage text.
    """
    if not dose_text or not passage_text:
        return False
    def clean(s: str) -> str:
        s = " ".join(re.sub(r"[^\w\s.]", " ", s.lower()).split())
        s = re.sub(r"\.(?!\d)", " ", s)  # keep decimal points only
        s = re.sub(r"(\d)\s+(mg|mcg|g|ml|iu|units?)\b", r"\1\2", s)
        return " ".join(s.split())

    clean_dose = clean(dose_text)
    return bool(clean_dose) and f" {clean_dose} " in f" {clean(passage_text)} "
