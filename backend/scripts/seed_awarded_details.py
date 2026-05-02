"""Seed awarded tender details (bidders, values, winners) from scraped JSON."""
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.models import AwardedTender


def seed_details():
    db = SessionLocal()

    json_path = None
    candidates = [
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     '..', 'scraped_data', 'awarded_tenders_details.json'),
        '../scraped_data/awarded_tenders_details.json',
        'scraped_data/awarded_tenders_details.json',
        '../../scraped_data/awarded_tenders_details.json',
    ]
    for p in candidates:
        if os.path.exists(p):
            json_path = p
            break

    if not json_path:
        print("No details file found yet (scrape may still be running)")
        return

    with open(json_path, encoding='utf-8') as f:
        details = json.load(f)

    print(f"Details to load: {len(details)}")
    updated = 0

    for d in details:
        iid = d.get('internal_id')
        if not iid:
            continue

        tender = db.query(AwardedTender).filter(AwardedTender.internal_id == iid).first()
        if not tender:
            continue

        winner = d.get('winner')
        tender.winner_company = winner.get('company') if winner else None
        tender.winning_value = d.get('winning_value')
        tender.num_bidders = d.get('num_bidders')
        tender.lowest_bid = d.get('lowest_bid')
        tender.highest_bid = d.get('highest_bid')
        tender.bid_spread_pct = d.get('bid_spread_pct')
        tender.bidders_json = json.dumps(d.get('bidders', []), ensure_ascii=False)
        updated += 1

        if updated % 500 == 0:
            db.commit()
            print(f"  Updated {updated}...")

    db.commit()
    db.close()
    print(f"Updated {updated} tenders with bid details")


if __name__ == '__main__':
    seed_details()
