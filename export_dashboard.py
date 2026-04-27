"""Export the SCC dashboard as a static index.html for deployment."""
import os, sys
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from dashboard import (build_html, extract_articles, extract_tenders,
    load_file, load_json_file, is_scc, is_pagination, NEWS_KW, COMPETITORS)

OUT_DIR = os.path.join(SCRIPT_DIR, "dashboard-static")

def main():
    tr = load_json_file("tenders.json")
    nr = load_json_file("news.json")
    hr = load_json_file("historical_tenders.json")
    bm = load_file("briefing_output.md")
    tenders = extract_tenders(tr) if tr else []
    articles = extract_articles(nr) if nr else []
    hist = extract_tenders(hr) if hr else []
    clean = [t for t in tenders if not is_pagination(t)]
    scc = [t for t in clean if is_scc(t)]
    seen = set()
    deduped = [a for a in articles if not (a.get("title","").strip().lower() in seen or seen.add(a.get("title","").strip().lower()))]
    relevant = [a for a in deduped if any(k in (a.get("title","")+" "+a.get("summary","")).lower() for k in NEWS_KW)]
    comp = [a for a in relevant if any(c.lower() in a.get("title","").lower() for c in COMPETITORS)]

    html_str = build_html(tenders, articles, bm, tr, hist)
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(html_str)
    size = len(html_str.encode("utf-8"))
    print(f"Exported to dashboard-static/index.html ({size:,} bytes)")
    print(f"\nAbove the fold:")
    print(f"  Metric cards: 4 (Pipeline: {len(clean)}, SCC: {len(scc)}, News: {len(relevant)})")
    print(f"  Executive briefing + trend chart")
    print(f"  SCC-relevant tenders table: {len(scc)}")
    print(f"  Market composition + top entities")
    print(f"\nBelow the fold (collapsed):")
    print(f"  All tenders: {len(clean)}")
    print(f"  News: {len(relevant)} relevant ({len(comp)} competitor)")

if __name__ == "__main__": main()
