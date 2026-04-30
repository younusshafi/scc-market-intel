"""
News scraper for Oman construction/infrastructure news.
Adapted from news_scraper.py — now stores results in PostgreSQL.
"""

import re
import logging
from datetime import datetime
from html import unescape

import feedparser
import requests
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import NewsArticle

logger = logging.getLogger(__name__)
settings = get_settings()

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}

FEEDS = [
    {"source": "Oman Observer — Home Page", "url": "https://www.omanobserver.om/rssFeed/home-page"},
    {"source": "Oman Observer — Oman News", "url": "https://www.omanobserver.om/rssFeed/1"},
    {"source": "Oman Observer — Business", "url": "https://www.omanobserver.om/rssFeed/4"},
    {"source": "Times of Oman", "url": "https://timesofoman.com/feed/"},
    {"source": "Google News — Oman Construction", "url": "https://news.google.com/rss/search?q=Oman+construction&hl=en-US&gl=US&ceid=US:en"},
    {"source": "Google News — Oman Infrastructure", "url": "https://news.google.com/rss/search?q=Oman+infrastructure&hl=en-US&gl=US&ceid=US:en"},
    {"source": "Google News — Galfar", "url": "https://news.google.com/rss/search?q=Galfar+Oman&hl=en-US&gl=US&ceid=US:en"},
    {"source": "Google News — Strabag", "url": "https://news.google.com/rss/search?q=Strabag+Oman&hl=en-US&gl=US&ceid=US:en"},
    {"source": "Google News — Al Tasnim", "url": "https://news.google.com/rss/search?q=Al+Tasnim+construction&hl=en-US&gl=US&ceid=US:en"},
    {"source": "Google News — L&T", "url": "https://news.google.com/rss/search?q=L%26T+Oman&hl=en-US&gl=US&ceid=US:en"},
    {"source": "Google News — Towell", "url": "https://news.google.com/rss/search?q=Towell+construction+Oman&hl=en-US&gl=US&ceid=US:en"},
    {"source": "Google News — Hassan Allam", "url": "https://news.google.com/rss/search?q=Hassan+Allam+Oman&hl=en-US&gl=US&ceid=US:en"},
    {"source": "Google News — Arab Contractors", "url": "https://news.google.com/rss/search?q=Arab+Contractors+Oman&hl=en-US&gl=US&ceid=US:en"},
    {"source": "Google News — Ozkar", "url": "https://news.google.com/rss/search?q=Ozkar+construction+Oman&hl=en-US&gl=US&ceid=US:en"},
]

NEWS_KW = [
    "construction", "infrastructure", "tender", "contract", "project",
    "investment", "industrial", "roads", "bridges", "pipeline", "ministry",
    "budget", "economic", "zone", "development", "port", "airport",
    "housing", "railway", "dam", "water", "sewage",
    "galfar", "strabag", "al tasnim", "l&t", "towell", "hassan allam",
    "arab contractors", "ozkar", "sarooj", "mtcit", "opaz", "riyada",
]

# Articles must mention Oman context OR a tracked competitor to be relevant.
# This filters out India expressways, US military news, etc.
OMAN_CONTEXT_KW = [
    "oman", "muscat", "salalah", "sohar", "duqm", "sur ",
    "sultanate", "omani", "gcc", "gulf", "tender board",
    "galfar", "strabag", "al tasnim", "l&t", "towell", "hassan allam",
    "arab contractors", "ozkar", "sarooj",
]

TAG_RE = re.compile(r"<[^>]+>")


def strip_html(text: str) -> str:
    if not text:
        return ""
    text = TAG_RE.sub("", text)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_date(entry) -> datetime | None:
    for attr in ("published_parsed", "updated_parsed"):
        tp = getattr(entry, attr, None)
        if tp:
            try:
                return datetime(*tp[:6])
            except (TypeError, ValueError):
                pass
    return None


def check_competitor_mentions(title: str, summary: str) -> list[str]:
    """Check if any tracked competitors are mentioned."""
    text = (title + " " + summary).lower()
    mentioned = []
    for comp in settings.scc_competitors:
        if comp.lower() in text:
            mentioned.append(comp)
    return mentioned


# JV detection patterns
JV_PATTERNS = [
    re.compile(r"\bjoint\s+venture\b", re.IGNORECASE),
    re.compile(r"\bJV\b"),
    re.compile(r"\bjv\s+(?:partner|agreement|consortium|bid|project)\b", re.IGNORECASE),
    re.compile(r"\bconsortium\b", re.IGNORECASE),
    re.compile(r"\bpartnership\s+(?:agreement|deal|formed|signed)\b", re.IGNORECASE),
    re.compile(r"\bteaming\s+agreement\b", re.IGNORECASE),
    re.compile(r"\balliance\b", re.IGNORECASE),
]

# Known company names to identify JV partners
ALL_TRACKED = ["Sarooj"] + list(settings.scc_competitors)


def detect_jv_mentions(title: str, summary: str) -> list[dict] | None:
    """Detect joint venture mentions and try to identify partners."""
    text = title + " " + summary

    is_jv = any(pat.search(text) for pat in JV_PATTERNS)
    if not is_jv:
        return None

    # Find which tracked companies are mentioned as potential partners
    text_lower = text.lower()
    partners = [c for c in ALL_TRACKED if c.lower() in text_lower]

    # Extract context — sentence containing JV keyword
    context = ""
    for pat in JV_PATTERNS:
        m = pat.search(text)
        if m:
            start = max(0, m.start() - 80)
            end = min(len(text), m.end() + 80)
            context = text[start:end].strip()
            break

    return [{"partners": partners, "context": context}]


def fetch_feed(source: str, url: str) -> list[dict]:
    """Fetch and parse a single RSS feed."""
    logger.info(f"Fetching: {source}")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
    except requests.RequestException as e:
        logger.error(f"Request failed for {source}: {e}")
        return []

    if resp.status_code != 200:
        logger.error(f"Non-200 response for {source}: {resp.status_code}")
        return []

    feed = feedparser.parse(resp.content)
    if feed.bozo and not feed.entries:
        logger.error(f"Feed parse failed for {source}: {feed.bozo_exception}")
        return []

    logger.info(f"  {source}: {len(feed.entries)} entries")

    articles = []
    for entry in feed.entries:
        summary = ""
        for field in ("summary", "description", "content"):
            val = getattr(entry, field, None)
            if val:
                if isinstance(val, list):
                    val = val[0].get("value", "") if val else ""
                summary = strip_html(val)
                if summary:
                    break

        title = strip_html(entry.get("title", ""))
        competitors = check_competitor_mentions(title, summary)
        jv_details = detect_jv_mentions(title, summary)
        text = (title + " " + summary).lower()
        has_topic_kw = any(kw in text for kw in NEWS_KW)
        has_oman_context = any(kw in text for kw in OMAN_CONTEXT_KW)
        is_relevant = has_topic_kw and has_oman_context

        articles.append({
            "source": source,
            "title": title,
            "link": entry.get("link", ""),
            "published": normalize_date(entry),
            "summary": summary[:500],
            "is_competitor_mention": len(competitors) > 0,
            "mentioned_competitors": competitors if competitors else None,
            "is_relevant": is_relevant,
            "is_jv_mention": jv_details is not None,
            "jv_details": jv_details,
        })

    return articles


def scrape_all_news() -> list[dict]:
    """Scrape all configured news feeds. Returns list of article dicts."""
    all_articles = []
    for feed_cfg in FEEDS:
        articles = fetch_feed(feed_cfg["source"], feed_cfg["url"])
        all_articles.extend(articles)
    logger.info(f"News scrape complete: {len(all_articles)} articles total")
    return all_articles


def persist_news(db: Session, articles: list[dict]) -> dict:
    """Store scraped news in the database. Deduplicates by link."""
    new_count = 0
    skipped = 0

    for article in articles:
        link = article.get("link", "")
        if not link:
            continue

        existing = db.query(NewsArticle).filter_by(link=link).first()
        if existing:
            skipped += 1
            continue

        try:
            news = NewsArticle(
                source=article["source"],
                title=article["title"],
                link=link,
                published=article.get("published"),
                summary=article.get("summary"),
                is_competitor_mention=article.get("is_competitor_mention", False),
                mentioned_competitors=article.get("mentioned_competitors"),
                is_relevant=article.get("is_relevant", True),
                is_jv_mention=article.get("is_jv_mention", False),
                jv_details=article.get("jv_details"),
            )
            db.add(news)
            db.flush()
            new_count += 1
        except Exception:
            db.rollback()
            skipped += 1

    db.commit()
    return {"new": new_count, "skipped": skipped, "total": len(articles)}
