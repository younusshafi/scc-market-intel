"""Cron job: Generate weekly executive briefing."""

import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

from app.core.database import SessionLocal
from app.models import ScrapeLog
from app.services.briefing_service import generate_and_store_briefing


def main():
    logger.info("=== Weekly Briefing Generation Starting ===")
    db = SessionLocal()
    log = ScrapeLog(scrape_type="briefing", status="running")
    db.add(log)
    db.commit()

    try:
        briefing = generate_and_store_briefing(db)

        if briefing:
            log.status = "success"
            log.records_new = 1
            log.details = {"briefing_id": briefing.id}
        else:
            log.status = "failed"
            log.error_message = "LLM call returned no result"

        log.completed_at = datetime.utcnow()

    except Exception as e:
        log.status = "failed"
        log.error_message = str(e)
        log.completed_at = datetime.utcnow()
        logger.error(f"Briefing generation failed: {e}", exc_info=True)

    finally:
        db.commit()
        db.close()


if __name__ == "__main__":
    main()
