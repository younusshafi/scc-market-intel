"""Cron job: Score SCC-relevant tenders using AI."""

import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

from app.core.database import SessionLocal
from app.models import ScrapeLog
from app.services.tender_scoring_service import score_tenders


def main():
    logger.info("=== Tender Scoring Starting ===")
    db = SessionLocal()
    log = ScrapeLog(scrape_type="tender_scoring", status="running")
    db.add(log)
    db.commit()

    try:
        result = score_tenders(db)
        logger.info(f"Scoring complete: {result}")

        log.status = "success" if result.get("status") == "success" else "partial"
        log.records_new = result.get("scored", 0)
        log.details = result
        log.completed_at = datetime.utcnow()

    except Exception as e:
        log.status = "failed"
        log.error_message = str(e)
        log.completed_at = datetime.utcnow()
        logger.error(f"Tender scoring failed: {e}", exc_info=True)

    finally:
        db.commit()
        db.close()


if __name__ == "__main__":
    main()
