"""Seed awarded tender listing data from scraped JSON."""
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal, engine
from app.models import AwardedTender
from app.core.database import Base


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # Find the JSON file
    json_path = None
    candidates = [
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     '..', 'scraped_data', 'awarded_tenders_listing.json'),
        '../scraped_data/awarded_tenders_listing.json',
        'scraped_data/awarded_tenders_listing.json',
        '../../scraped_data/awarded_tenders_listing.json',
    ]
    for p in candidates:
        if os.path.exists(p):
            json_path = p
            break

    if not json_path:
        print("ERROR: awarded_tenders_listing.json not found")
        return

    print(f"Loading from {json_path}")
    with open(json_path, encoding='utf-8') as f:
        tenders = json.load(f)

    print(f"Total tenders: {len(tenders)}")

    # Check existing
    existing_ids = set(r[0] for r in db.query(AwardedTender.internal_id).all())
    print(f"Already in DB: {len(existing_ids)}")

    count = 0
    seen_ids = set(existing_ids)
    for t in tenders:
        iid = t.get('internal_id')
        if not iid or iid in seen_ids:
            continue
        seen_ids.add(iid)

        at = AwardedTender(
            internal_id=iid,
            tender_number=t.get('tender_number', ''),
            tender_title=t.get('tender_title', ''),
            entity=t.get('entity', ''),
            category=t.get('category', ''),
            grade=t.get('grade', ''),
            awarded_date=t.get('awarded_date', ''),
            is_construction=t.get('is_construction', False),
        )
        db.add(at)
        count += 1

        if count % 1000 == 0:
            db.commit()
            print(f"  Seeded {count}...")

    db.commit()
    db.close()
    print(f"Seeded {count} new awarded tenders")


if __name__ == '__main__':
    seed()
