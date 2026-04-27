"""
News scraper for Oman construction/infrastructure news.

Sources:
  - Oman Observer (omanobserver.om) — RSS at /rssFeed/{section_id}
  - Times of Oman (timesofoman.com) — RSS at /feed/
  - Google News — RSS search for "Oman construction" and "Oman infrastructure"
"""

import json
import os
import re
import sys
from datetime import datetime
from html import unescape

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import feedparser
import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}

FEEDS = [
    {
        "source": "Oman Observer — Home Page",
        "url": "https://www.omanobserver.om/rssFeed/home-page",
    },
    {
        "source": "Oman Observer — Oman News",
        "url": "https://www.omanobserver.om/rssFeed/1",
    },
    {
        "source": "Oman Observer — Business",
        "url": "https://www.omanobserver.om/rssFeed/4",
    },
    {
        "source": "Times of Oman",
        "url": "https://timesofoman.com/feed/",
    },
    {
        "source": "Google News — Oman Construction",
        "url": "https://news.google.com/rss/search?q=Oman+construction&hl=en-US&gl=US&ceid=US:en",
    },
    {
        "source": "Google News — Oman Infrastructure",
        "url": "https://news.google.com/rss/search?q=Oman+infrastructure&hl=en-US&gl=US&ceid=US:en",
    },
]

# Tags for HTML stripping
TAG_RE = re.compile(r"<[^>]+>")


def strip_html(text):
    """Remove HTML tags and decode entities."""
    if not text:
        return ""
    text = TAG_RE.sub("", text)
    text = unescape(text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_date(entry):
    """Extract a date string from a feed entry, trying multiple fields."""
    # feedparser normalizes dates into published_parsed / updated_parsed
    for attr in ("published_parsed", "updated_parsed"):
        tp = getattr(entry, attr, None)
        if tp:
            try:
                return datetime(*tp[:6]).isoformat()
            except (TypeError, ValueError):
                pass

    # Fall back to raw string fields
    for attr in ("published", "updated", "dc_date"):
        raw = getattr(entry, attr, None)
        if raw:
            return raw.strip()

    return None


def fetch_feed(source, url):
    """Fetch and parse a single RSS feed. Returns list of article dicts."""
    print(f"\n  Fetching: {url}")

    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
    except requests.RequestException as e:
        print(f"  ERROR: Request failed — {e}")
        return []

    print(f"  Status: {resp.status_code}, Size: {len(resp.content):,} bytes, "
          f"Content-Type: {resp.headers.get('Content-Type', 'N/A')[:50]}")

    if resp.status_code != 200:
        print(f"  ERROR: Non-200 response")
        return []

    feed = feedparser.parse(resp.content)

    if feed.bozo and not feed.entries:
        print(f"  ERROR: Feed parse failed — {feed.bozo_exception}")
        return []

    feed_title = feed.feed.get("title", source)
    print(f"  Feed title: {feed_title}")
    print(f"  Entries: {len(feed.entries)}")

    articles = []
    for entry in feed.entries:
        # Extract summary — try multiple fields
        summary = ""
        for field in ("summary", "description", "content"):
            val = getattr(entry, field, None)
            if val:
                # content is a list of dicts in feedparser
                if isinstance(val, list):
                    val = val[0].get("value", "") if val else ""
                summary = strip_html(val)
                if summary:
                    break

        article = {
            "source": source,
            "title": strip_html(entry.get("title", "")),
            "link": entry.get("link", ""),
            "published": normalize_date(entry),
            "summary": summary[:500],  # cap length for readability
        }
        articles.append(article)

    return articles


def print_articles(source, articles):
    """Print articles for one source in a readable format."""
    print(f"\n{'='*70}")
    print(f"  {source} — {len(articles)} article(s)")
    print(f"{'='*70}")

    for i, a in enumerate(articles):
        date_str = a["published"] or "no date"
        title = a["title"][:90]
        summary = a["summary"][:150]
        link = a["link"]

        print(f"\n  [{i+1}] {title}")
        print(f"      Date: {date_str}")
        if summary:
            print(f"      {summary}...")
        print(f"      {link}")


def main():
    print("=" * 70)
    print("Oman News Scraper")
    print(f"Run at: {datetime.now().isoformat()}")
    print("=" * 70)

    all_articles = []
    by_source = {}

    for feed_cfg in FEEDS:
        source = feed_cfg["source"]
        url = feed_cfg["url"]

        print(f"\n--- {source} ---")
        articles = fetch_feed(source, url)
        all_articles.extend(articles)
        by_source[source] = articles

    # Print grouped results
    for source in by_source:
        print_articles(source, by_source[source])

    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    total = len(all_articles)
    print(f"  Total articles: {total}")
    for source, articles in by_source.items():
        status = f"{len(articles)} articles" if articles else "FAILED"
        print(f"    {source:50s} {status}")

    # Save to JSON
    output = {
        "scraped_at": datetime.now().isoformat(),
        "total_articles": total,
        "sources": {
            source: {"count": len(arts), "articles": arts}
            for source, arts in by_source.items()
        },
    }

    with open("news.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n  Saved to news.json ({total} articles)")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
