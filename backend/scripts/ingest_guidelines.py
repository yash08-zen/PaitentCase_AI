"""
scripts/ingest_guidelines.py
----------------------------
Load guideline passages from a JSON file into GUIDELINE_PASSAGES and rebuild
the FTS5 index.

File format (same as config/guidelines_sample.json):
  {"passages": [{"source", "version_date", "condition_or_topic", "section",
                 "passage_text", "citations": [...], "is_sample": false}]}

Usage (from backend/):
  .\\.venv312\\Scripts\\python.exe scripts\\ingest_guidelines.py path\\to\\verified.json [--replace]

--replace removes every existing passage (including the samples) first.
Only load passages whose source, version and section you have verified.
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import AsyncSessionLocal, init_db  # noqa: E402
from app.services.guidelines import ingest_passages, load_passages_file  # noqa: E402


async def main(path: str, replace: bool) -> None:
    passages = load_passages_file(path)
    await init_db()
    async with AsyncSessionLocal() as db:
        n = await ingest_passages(db, passages, replace=replace)
    flagged = sum(1 for p in passages if p.get("is_sample"))
    print(f"Ingested {n} passage(s) from {path} ({flagged} marked as sample). FTS index rebuilt.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path")
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.path, args.replace))
