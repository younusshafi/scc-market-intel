"""
Export the SCC dashboard as a static index.html for deployment.
Reuses build_html() from dashboard.py.
"""

import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from dashboard import build_html, extract_articles, extract_tenders, load_file, load_json_file

OUT_DIR = os.path.join(SCRIPT_DIR, "dashboard-static")


def main():
    tenders_raw = load_json_file("tenders.json")
    news_raw = load_json_file("news.json")
    briefing_md = load_file("briefing_output.md")

    tenders = extract_tenders(tenders_raw) if tenders_raw else []
    articles = extract_articles(news_raw) if news_raw else []

    html_str = build_html(tenders, articles, briefing_md, tenders_raw)

    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, "index.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_str)

    print(f"Exported to dashboard-static/index.html ({len(html_str):,} bytes)")


if __name__ == "__main__":
    main()
