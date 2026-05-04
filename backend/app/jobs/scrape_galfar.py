"""Job: scrape Galfar MSX financial data.

Run weekly (MSX data only updates quarterly).

Usage:
    cd backend
    python -m app.jobs.scrape_galfar
"""

import logging
from pathlib import Path

from app.scrapers.galfar_msx_scraper import run_scraper, save_to_json

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main():
    logger.info("Starting Galfar MSX financial scrape...")

    data = run_scraper()

    hits = data.get("sources_hit", {})
    logger.info("Sources hit — MSM: %s, Mubasher: %s", hits.get("msm"), hits.get("mubasher"))

    project_root = Path(__file__).resolve().parent.parent.parent.parent
    output_path = project_root / "scraped_data" / "galfar_financials.json"
    save_to_json(data, output_path)

    logger.info("Done. share_price=%s  market_cap=%s  revenue=%s  net_profit=%s",
                data.get("share_price_omr"),
                data.get("market_cap_omr"),
                data.get("revenue_omr"),
                data.get("net_profit_omr"))


if __name__ == "__main__":
    main()
