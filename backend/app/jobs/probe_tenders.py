"""Job runner for deep tender probing."""

import logging
from app.core.database import SessionLocal
from app.scrapers.tender_probe import run_tender_probe

logger = logging.getLogger(__name__)


def run_probe_job():
    """Execute the tender probe pipeline. Called by scheduler or API trigger."""
    logger.info("Starting tender probe job...")
    db = SessionLocal()
    try:
        result = run_tender_probe(db)
        logger.info(f"Tender probe complete: {result}")
        return result
    except Exception as e:
        logger.error(f"Tender probe job failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_probe_job()
