"""Cron job: Scrape tenders from Oman Tender Board and persist to database."""

import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

from app.core.database import SessionLocal
from app.models import ScrapeLog
from app.scrapers.tender_scraper import scrape_all_tenders, persist_tenders


def main():
    logger.info("=== Tender Scrape Job Starting ===")
    db = SessionLocal()
    log = ScrapeLog(scrape_type="tenders", status="running")
    db.add(log)
    db.commit()

    try:
        raw_tenders = scrape_all_tenders()
        result = persist_tenders(db, raw_tenders)

        log.status = "success"
        log.records_found = result["total"]
        log.records_new = result["new"]
        log.records_updated = result["updated"]
        log.completed_at = datetime.utcnow()
        log.details = result

        logger.info(f"Scrape complete: {result}")

    except Exception as e:
        log.status = "failed"
        log.error_message = str(e)
        log.completed_at = datetime.utcnow()
        logger.error(f"Scrape failed: {e}", exc_info=True)

    finally:
        db.commit()
        db.close()


if __name__ == "__main__":
    main()
