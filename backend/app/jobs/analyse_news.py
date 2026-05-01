"""Cron job: Analyse news articles for SCC strategic intelligence."""

import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

from app.core.database import SessionLocal
from app.models import ScrapeLog
from app.services.news_intelligence_service import analyse_news


def main():
    logger.info("=== News Intelligence Analysis Starting ===")
    db = SessionLocal()
    log = ScrapeLog(scrape_type="news_analysis", status="running")
    db.add(log)
    db.commit()

    try:
        result = analyse_news(db)
        logger.info(f"Analysis complete: {result}")

        log.status = "success" if result.get("status") == "success" else "partial"
        log.records_new = result.get("analysed", 0)
        log.details = result
        log.completed_at = datetime.utcnow()

    except Exception as e:
        log.status = "failed"
        log.error_message = str(e)
        log.completed_at = datetime.utcnow()
        logger.error(f"News analysis failed: {e}", exc_info=True)

    finally:
        db.commit()
        db.close()


if __name__ == "__main__":
    main()
