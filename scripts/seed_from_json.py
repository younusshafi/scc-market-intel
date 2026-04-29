"""
Seed the database from existing JSON files (tenders.json, news.json, historical_tenders.json).
Run once during initial setup to migrate from file-based to database-backed storage.

Usage:
    cd backend
    python -m scripts.seed_from_json --data-dir /path/to/json/files
"""

import argparse
import json
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Add parent to path so we can import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal, engine, Base
from app.models import Tender, NewsArticle
from app.scrapers.tender_scraper import (
    raw_to_tender_model, is_pagination_row, extract_tenders_from_json,
)
from app.scrapers.news_scraper import check_competitor_mentions

NEWS_KW = [
    "construction", "infrastructure", "tender", "contract", "project",
    "investment", "industrial", "roads", "bridges", "pipeline", "ministry",
    "budget", "economic", "zone", "development", "port", "airport",
    "housing", "railway", "dam", "water", "sewage",
    "galfar", "strabag", "al tasnim", "l&t", "towell", "hassan allam",
    "arab contractors", "ozkar", "sarooj", "mtcit", "opaz", "riyada",
]


def extract_tenders_from_json(raw):
    """Extract tender list from whatever structure the JSON has."""
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        for key in ("tenders", "views", "data", "results", "items"):
            if key in raw and isinstance(raw[key], list):
                return raw[key]
    return []


def extract_articles_from_json(raw):
    """Extract articles from news.json structure."""
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        if "sources" in raw and isinstance(raw["sources"], dict):
            articles = []
            for source_name, source_data in raw["sources"].items():
                if isinstance(source_data, dict) and "articles" in source_data:
                    for a in source_data["articles"]:
                        a.setdefault("source", source_name)
                        articles.append(a)
                elif isinstance(source_data, list):
                    for a in source_data:
                        a.setdefault("source", source_name)
                        articles.append(a)
            return articles
    return []


def seed_tenders(db, data_dir, filename="tenders.json"):
    path = os.path.join(data_dir, filename)
    if not os.path.exists(path):
        logger.warning(f"{filename} not found at {path}, skipping")
        return 0

    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    tenders = extract_tenders_from_json(raw)
    logger.info(f"Loaded {len(tenders)} tenders from {filename}")

    count = 0
    for t in tenders:
        if is_pagination_row(t):
            continue

        view = t.get("_view", "Unknown")
        tender_num = t.get("tender_number", "")
        if not tender_num:
            continue

        # Check if already exists
        existing = db.query(Tender).filter_by(tender_number=tender_num, view=view).first()
        if existing:
            continue

        kwargs = raw_to_tender_model(t, view)
        db.add(Tender(**kwargs))
        count += 1

    db.commit()
    logger.info(f"Seeded {count} new tenders from {filename}")
    return count


def seed_news(db, data_dir, filename="news.json"):
    path = os.path.join(data_dir, filename)
    if not os.path.exists(path):
        logger.warning(f"{filename} not found at {path}, skipping")
        return 0

    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    articles = extract_articles_from_json(raw)
    logger.info(f"Loaded {len(articles)} articles from {filename}")

    count = 0
    for a in articles:
        link = a.get("link", "")
        if not link:
            continue

        existing = db.query(NewsArticle).filter_by(link=link).first()
        if existing:
            continue

        title = a.get("title", "")
        summary = a.get("summary", "")
        competitors = check_competitor_mentions(title, summary)
        text = (title + " " + summary).lower()
        is_relevant = any(kw in text for kw in NEWS_KW)

        # Parse published date
        published = None
        pub_str = a.get("published", "")
        if pub_str:
            from datetime import datetime
            import re
            pub_str = re.sub(r"[+-]\d{2}:\d{2}$", "", pub_str.strip())
            for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%d",
                        "%a, %d %b %Y %H:%M:%S", "%a, %d %b %Y %H:%M:%S %Z",
                        "%a, %d %b %Y %H:%M:%S GMT"):
                try:
                    published = datetime.strptime(pub_str, fmt)
                    break
                except ValueError:
                    continue

        news = NewsArticle(
            source=a.get("source", "Unknown"),
            title=title,
            link=link,
            published=published,
            summary=(summary or "")[:500],
            is_competitor_mention=len(competitors) > 0,
            mentioned_competitors=competitors if competitors else None,
            is_relevant=is_relevant,
        )
        db.add(news)
        count += 1

    db.commit()
    logger.info(f"Seeded {count} new articles from {filename}")
    return count


def main():
    parser = argparse.ArgumentParser(description="Seed database from JSON files")
    parser.add_argument(
        "--data-dir",
        default=os.path.join(os.path.dirname(__file__), "..", "..", "scc-market-intel"),
        help="Directory containing tenders.json, news.json, etc.",
    )
    args = parser.parse_args()
    data_dir = os.path.abspath(args.data_dir)

    logger.info(f"Data directory: {data_dir}")
    logger.info("Creating tables...")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        t1 = seed_tenders(db, data_dir, "tenders.json")
        t2 = seed_tenders(db, data_dir, "historical_tenders.json")
        n = seed_news(db, data_dir, "news.json")
        logger.info(f"Seeding complete: {t1 + t2} tenders, {n} news articles")
    finally:
        db.close()


if __name__ == "__main__":
    main()
