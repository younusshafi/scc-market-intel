"""Cron job: Build entity intelligence using AI."""

import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

from app.core.database import SessionLocal
from app.models import ScrapeLog
from app.services.entity_intel_service import build_entity_intel


def main():
    logger.info("=== Entity Intelligence Build Starting ===")
    db = SessionLocal()
    log = ScrapeLog(scrape_type="entity_intel", status="running")
    db.add(log)
    db.commit()

    try:
        result = build_entity_intel(db)
        logger.info(f"Entity intel build complete: {result}")

        log.status = "success" if result.get("status") == "success" else "partial"
        log.records_new = result.get("built", 0)
        log.details = result
        log.completed_at = datetime.utcnow()

    except Exception as e:
        log.status = "failed"
        log.error_message = str(e)
        log.completed_at = datetime.utcnow()
        logger.error(f"Entity intel build failed: {e}", exc_info=True)

    finally:
        db.commit()
        db.close()


if __name__ == "__main__":
    main()
