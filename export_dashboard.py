"""Export the SCC dashboard as a static index.html for deployment."""

import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from dashboard import (
    build_html, extract_articles, extract_tenders,
    load_file, load_json_file, is_scc_relevant, is_pagination_row,
    NEWS_KEYWORDS,
)

OUT_DIR = os.path.join(SCRIPT_DIR, "dashboard-static")


def main():
    tenders_raw = load_json_file("tenders.json")
    news_raw = load_json_file("news.json")
    briefing_md = load_file("briefing_output.md")

    tenders = extract_tenders(tenders_raw) if tenders_raw else []
    articles = extract_articles(news_raw) if news_raw else []

    # Print summary
    clean = [t for t in tenders if not is_pagination_row(t)]
    scc = [t for t in clean if is_scc_relevant(t)]

    seen = set()
    deduped = []
    for a in articles:
        title = a.get("title", "").strip().lower()
        if title and title not in seen:
            seen.add(title)
            deduped.append(a)
    relevant = [a for a in deduped if any(
        kw in (a.get("title", "") + " " + a.get("summary", "")).lower()
        for kw in NEWS_KEYWORDS
    )]

    html_str = build_html(tenders, articles, briefing_md, tenders_raw)

    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, "index.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_str)

    size = len(html_str.encode("utf-8"))
    print(f"Exported to dashboard-static/index.html ({size:,} bytes)")
    print()
    print("ABOVE THE FOLD:")
    print(f"  Stats bar: 5 cards")
    print(f"  Executive briefing: {'yes' if briefing_md else 'no'}")
    print(f"  SCC-relevant tenders table: {len(scc)} tenders")
    print()
    print("BELOW THE FOLD (collapsed):")
    print(f"  Full tender pipeline: {len(clean)} tenders across {len(set(t.get('_view','') for t in clean))} views")
    print(f"  Market news: {len(relevant)} relevant articles (from {len(articles)} total)")


if __name__ == "__main__":
    main()
