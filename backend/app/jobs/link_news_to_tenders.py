"""Cron job: Link news articles to matching tenders using AI."""

import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

from app.core.database import SessionLocal
from app.models import ScrapeLog
from app.services.news_tender_linker_service import link_news_to_tenders


def main():
    logger.info("=== News-Tender Linking Starting ===")
    db = SessionLocal()
    log = ScrapeLog(scrape_type="news_tender_link", status="running")
    db.add(log)
    db.commit()

    try:
        result = link_news_to_tenders(db)
        logger.info(f"News-tender linking complete: {result}")

        log.status = "success" if result.get("status") == "success" else "partial"
        log.records_new = result.get("linked", 0)
        log.details = result
        log.completed_at = datetime.utcnow()

    except Exception as e:
        log.status = "failed"
        log.error_message = str(e)
        log.completed_at = datetime.utcnow()
        logger.error(f"News-tender linking failed: {e}", exc_info=True)

    finally:
        db.commit()
        db.close()


if __name__ == "__main__":
    main()
