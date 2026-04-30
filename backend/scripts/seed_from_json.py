"""
Seed the database with historical tender data from JSON files.

Usage (from backend/ directory):
    python -m scripts.seed_from_json --data-dir ../

Loads tenders.json and historical_tenders.json, deduplicates by tender_number,
and inserts into the tenders table. Connects to Render Postgres via DATABASE_URL.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

# Load .env before importing app modules
def _load_env():
    try:
        from dotenv import load_dotenv
    except ImportError:
        pass
    else:
        backend_dir = Path(__file__).resolve().parent.parent
        for env_path in [backend_dir / ".env", backend_dir.parent / ".env"]:
            if env_path.exists():
                load_dotenv(env_path, override=False)

    if not os.environ.get("DATABASE_URL"):
        print("ERROR: DATABASE_URL not set.")
        print("Add it to backend/.env:")
        print("  DATABASE_URL=postgresql://user:pass@host:5432/dbname")
        sys.exit(1)

_load_env()

from app.core.database import SessionLocal, engine, Base
from app.models import Tender
from app.scrapers.tender_scraper import (
    split_category_grade, split_type, is_retender, is_scc_relevant, parse_date_str,
)


def parse_fee(raw_fee) -> float | None:
    """Parse fee from various formats."""
    if raw_fee is None:
        return None
    if isinstance(raw_fee, (int, float)):
        return float(raw_fee)
    if isinstance(raw_fee, str):
        if not raw_fee or raw_fee in ("N/A", "-", ""):
            return None
        try:
            return float(re.sub(r"[^\d.]", "", raw_fee))
        except (ValueError, TypeError):
            return None
    return None


def map_view(raw_view: str) -> str:
    """Normalize _view values to DB view names."""
    v = raw_view.lower()
    if "inprocess" in v or "in process" in v:
        return "InProcessTenders"
    if "sub" in v:
        return "SubContractTenders"
    return "NewTenders"


def raw_to_model_kwargs(raw: dict) -> dict:
    """Convert a raw JSON tender dict into Tender model kwargs."""
    cg_ar = raw.get("category_grade_ar", raw.get("category_grade", ""))
    cg_en = raw.get("category_grade_en", "")
    cat_ar, grade_ar = split_category_grade(cg_ar)
    cat_en, grade_en = split_category_grade(cg_en) if cg_en else ("", "")

    type_ar = split_type(raw.get("tender_type_ar", raw.get("tender_type", "")))
    type_en = split_type(raw.get("tender_type_en", "")) or type_ar

    view = map_view(raw.get("_view", "NewTenders"))

    return {
        "tender_number": raw.get("tender_number", ""),
        "tender_number_en": raw.get("tender_number_en"),
        "tender_name_ar": raw.get("tender_name_ar", raw.get("tender_name")),
        "tender_name_en": raw.get("tender_name_en"),
        "entity_ar": raw.get("entity_ar", raw.get("entity")),
        "entity_en": raw.get("entity_en"),
        "category_ar": cat_ar,
        "category_en": cat_en or cat_ar,
        "grade_ar": grade_ar,
        "grade_en": grade_en or grade_ar,
        "tender_type_ar": type_ar,
        "tender_type_en": type_en,
        "sales_end_date": parse_date_str(raw.get("sales_end_date")),
        "bid_closing_date": parse_date_str(raw.get("bid_closing_date")),
        "fee": parse_fee(raw.get("fee")),
        "bank_guarantee": raw.get("bank_guarantee"),
        "view": view,
        "is_retender": is_retender(raw),
        "is_scc_relevant": is_scc_relevant(raw),
        "is_subcontract": view == "SubContractTenders",
        "raw_data": raw,
    }


def load_json(path: Path) -> list[dict]:
    """Load tenders from a JSON file."""
    if not path.exists():
        print(f"  SKIP: {path} does not exist")
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    tenders = data.get("tenders", []) if isinstance(data, dict) else data
    print(f"  Loaded {len(tenders)} tenders from {path.name}")
    return tenders


def main():
    parser = argparse.ArgumentParser(description="Seed database from JSON tender files")
    parser.add_argument("--data-dir", required=True, help="Directory containing tenders.json and historical_tenders.json")
    args = parser.parse_args()

    data_dir = Path(args.data_dir).resolve()
    print("=" * 70)
    print("  SCC Tender Database Seeder")
    print(f"  Data directory: {data_dir}")
    print(f"  Database: {os.environ.get('DATABASE_URL', '?')[:50]}...")
    print("=" * 70)

    # Ensure tables exist
    print("\n  Ensuring tables exist...")
    Base.metadata.create_all(bind=engine)
    print("  OK")

    # Load JSON files
    print("\n  Loading JSON files...")
    raw_tenders = []
    for filename in ["historical_tenders.json", "tenders.json"]:
        raw_tenders.extend(load_json(data_dir / filename))

    if not raw_tenders:
        print("\n  No tenders found in JSON files.")
        return

    # Deduplicate by tender_number (later entries win)
    by_number = {}
    for raw in raw_tenders:
        tn = raw.get("tender_number", "")
        if tn:
            by_number[tn] = raw
    print(f"\n  Unique tenders after dedup: {len(by_number)} (from {len(raw_tenders)} total)")

    # Check existing tenders in DB
    db = SessionLocal()
    try:
        existing_numbers = set(
            r[0] for r in db.query(Tender.tender_number).all()
        )
        print(f"  Already in database: {len(existing_numbers)}")

        new_tenders = {tn: raw for tn, raw in by_number.items() if tn not in existing_numbers}
        print(f"  New tenders to insert: {len(new_tenders)}")

        if not new_tenders:
            print("\n  Nothing to insert — database is up to date.")
            return

        # Insert in batches
        batch_size = 200
        inserted = 0
        items = list(new_tenders.values())

        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            for raw in batch:
                try:
                    kwargs = raw_to_model_kwargs(raw)
                    tender = Tender(**kwargs)
                    db.add(tender)
                    inserted += 1
                except Exception as e:
                    tn = raw.get("tender_number", "?")
                    print(f"    WARN: skipped {tn}: {e}")
                    db.rollback()
                    continue

            db.commit()
            print(f"    Inserted batch {i // batch_size + 1}: {min(i + batch_size, len(items))}/{len(items)}")

        # Summary
        total_db = db.query(Tender).count()
        scc_count = db.query(Tender).filter(Tender.is_scc_relevant == True).count()
        with_fee = db.query(Tender).filter(Tender.fee != None, Tender.fee > 0).count()

        print(f"\n{'='*70}")
        print(f"  SEED COMPLETE")
        print(f"{'='*70}")
        print(f"  Inserted: {inserted}")
        print(f"  Total in DB: {total_db}")
        print(f"  SCC-relevant: {scc_count}")
        print(f"  With fee data: {with_fee}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
