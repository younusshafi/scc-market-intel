"""Cron job: Scrape news from RSS feeds and persist to database."""

import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

from app.core.database import SessionLocal
from app.models import ScrapeLog
from app.scrapers.news_scraper import scrape_all_news, persist_news


def main():
    logger.info("=== News Scrape Job Starting ===")
    db = SessionLocal()
    log = ScrapeLog(scrape_type="news", status="running")
    db.add(log)
    db.commit()

    try:
        articles = scrape_all_news()
        result = persist_news(db, articles)

        log.status = "success"
        log.records_found = result["total"]
        log.records_new = result["new"]
        log.completed_at = datetime.utcnow()
        log.details = result

        logger.info(f"News scrape complete: {result}")

    except Exception as e:
        log.status = "failed"
        log.error_message = str(e)
        log.completed_at = datetime.utcnow()
        logger.error(f"News scrape failed: {e}", exc_info=True)

    finally:
        db.commit()
        db.close()


if __name__ == "__main__":
    main()
