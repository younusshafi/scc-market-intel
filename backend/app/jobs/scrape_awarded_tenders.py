"""
Cron job: Incrementally scrape awarded tenders from Oman Tender Board.

Fetches only awarded tenders newer than the most recent awarded_date in the database.
Inserts new records and skips duplicates (by tender_number or internal_id).
Does NOT scrape bidder details — only the listing data.
Bidder details remain populated via separate deep-probe / manual seed process.
"""

import logging
import time
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

import requests
from bs4 import BeautifulSoup

from app.core.database import SessionLocal
from app.core.config import get_settings
from app.models import AwardedTender, ScrapeLog

settings = get_settings()

BASE_URL = settings.tender_board_base_url

# Oman Tender Board — awarded tenders listing endpoint (Endpoint D)
AWARDED_LIST_URL = f"{BASE_URL}/Home/usertenderlistold"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
}

# Maximum pages to scrape per run (safety limit — incremental runs stay small)
MAX_PAGES = 20


def _get_max_awarded_date(db) -> str | None:
    """Return the most recent awarded_date in the database, or None if empty."""
    result = db.query(AwardedTender.awarded_date).filter(
        AwardedTender.awarded_date != None
    ).order_by(AwardedTender.awarded_date.desc()).first()
    return result[0] if result else None


def _get_existing_keys(db) -> tuple[set, set]:
    """Return sets of existing (tender_numbers, internal_ids) to detect duplicates."""
    tender_numbers = set(
        r[0] for r in db.query(AwardedTender.tender_number).filter(
            AwardedTender.tender_number != None
        ).all()
    )
    internal_ids = set(
        r[0] for r in db.query(AwardedTender.internal_id).filter(
            AwardedTender.internal_id != None
        ).all()
    )
    return tender_numbers, internal_ids


def scrape_awarded_page(session: requests.Session, page: int) -> list[dict]:
    """Scrape one page of the awarded tenders listing.

    Returns a list of dicts with tender metadata. Returns empty list on failure.
    The Oman Tender Board uses a form-based pagination; adjust payload as needed.
    """
    try:
        payload = {
            "pageIndex": str(page),
            "pageSize": "20",
            "tenderStatusId": "4",   # 4 = Awarded
            "lang": "1",             # 1 = English
        }
        resp = session.post(AWARDED_LIST_URL, data=payload, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("Page %d fetch failed: %s", page, exc)
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    rows = soup.select("table.tender-table tr, table tr")

    tenders = []
    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 4:
            continue
        texts = [c.get_text(strip=True) for c in cells]

        # Extract internal_id from a link if present
        link = row.find("a", href=True)
        internal_id = None
        if link:
            href = link.get("href", "")
            import re
            m = re.search(r"[?&](?:id|tenderId|tenderid)=(\d+)", href, re.IGNORECASE)
            if m:
                internal_id = m.group(1)

        tenders.append({
            "tender_number": texts[1] if len(texts) > 1 else None,
            "tender_title": texts[2] if len(texts) > 2 else None,
            "entity": texts[3] if len(texts) > 3 else None,
            "category": texts[4] if len(texts) > 4 else None,
            "awarded_date": texts[5] if len(texts) > 5 else None,
            "internal_id": internal_id,
        })

    return tenders


def scrape_awarded_tenders_incremental() -> dict:
    """Main incremental scrape function. Returns summary dict."""
    db = SessionLocal()
    log = ScrapeLog(scrape_type="awarded_tenders", status="running")
    db.add(log)
    db.commit()

    records_added = 0
    records_skipped = 0

    try:
        max_date = _get_max_awarded_date(db)
        existing_tns, existing_iids = _get_existing_keys(db)
        logger.info("Incremental awarded tender scrape — max_date_in_db=%s, existing=%d records",
                    max_date, len(existing_tns))

        session = requests.Session()

        for page in range(1, MAX_PAGES + 1):
            tenders = scrape_awarded_page(session, page)
            if not tenders:
                logger.info("Page %d: no results — stopping", page)
                break

            page_new = 0
            stop_early = False

            for t in tenders:
                tn = t.get("tender_number")
                iid = t.get("internal_id")
                awarded_date = t.get("awarded_date", "")

                # Stop if we've reached already-existing data (date-based cutoff)
                if max_date and awarded_date and awarded_date <= max_date:
                    stop_early = True
                    break

                # Skip duplicates
                if (tn and tn in existing_tns) or (iid and iid in existing_iids):
                    records_skipped += 1
                    continue

                # Insert new record
                new_record = AwardedTender(
                    internal_id=iid,
                    tender_number=tn,
                    tender_title=t.get("tender_title"),
                    entity=t.get("entity"),
                    category=t.get("category"),
                    awarded_date=awarded_date or None,
                    is_construction=False,  # Will be classified in a post-process step
                )
                db.add(new_record)
                if tn:
                    existing_tns.add(tn)
                if iid:
                    existing_iids.add(iid)
                records_added += 1
                page_new += 1

            logger.info("Page %d: +%d new, %d skipped", page, page_new, records_skipped)
            db.commit()

            if stop_early:
                logger.info("Reached existing data (awarded_date <= %s) — stopping", max_date)
                break

            time.sleep(settings.scrape_page_delay)

        log.status = "success"
        log.records_new = records_added
        log.completed_at = datetime.utcnow()
        log.details = {"records_added": records_added, "records_skipped": records_skipped}
        logger.info("Awarded tender scrape complete: added=%d, skipped=%d", records_added, records_skipped)

    except Exception as exc:
        log.status = "failed"
        log.error_message = str(exc)
        log.completed_at = datetime.utcnow()
        logger.error("Awarded tender scrape failed: %s", exc, exc_info=True)

    finally:
        db.commit()
        db.close()

    return {"records_added": records_added, "records_skipped": records_skipped}


def main():
    logger.info("=== Awarded Tender Scrape Starting ===")
    result = scrape_awarded_tenders_incremental()
    logger.info("=== Done: %s ===", result)


if __name__ == "__main__":
    main()
