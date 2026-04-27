"""
SCC Market Intelligence Dashboard — validation preview.

Serves a single-page dashboard at http://localhost:8000 displaying:
  - AI executive briefing (from briefing_output.md)
  - Tender pipeline table with filtering and tabs (from tenders.json)
  - News intelligence cards (from news.json)
  - Portal overview stats

Uses only Python standard library (http.server). All HTML/CSS/JS inline.
"""

import html
import http.server
import json
import os
import re
import sys
from datetime import datetime

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PORT = 8000

# Source tag colours
SOURCE_COLOURS = {
    "Oman Observer": "#2E75B6",
    "Times of Oman": "#D4520B",
    "Google News": "#0F9D58",
}


def load_file(name):
    path = os.path.join(SCRIPT_DIR, name)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def load_json_file(name):
    text = load_file(name)
    if text is None:
        return None
    return json.loads(text)


# ---------------------------------------------------------------------------
# Data extraction (mirrors the logic in briefing_test.py)
# ---------------------------------------------------------------------------

def extract_tenders(raw):
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        for key in ("tenders", "views", "data", "results", "items"):
            if key in raw and isinstance(raw[key], list):
                return raw[key]
        merged = []
        for k, v in raw.items():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                for item in v:
                    item.setdefault("_view", k)
                merged.extend(v)
        if merged:
            return merged
    return []


def extract_articles(raw):
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
        for key in ("articles", "items", "data"):
            if key in raw and isinstance(raw[key], list):
                return raw[key]
    return []


def get_source_colour(source):
    for key, colour in SOURCE_COLOURS.items():
        if key.lower() in source.lower():
            return colour
    return "#6c757d"


# ---------------------------------------------------------------------------
# Markdown -> HTML (minimal converter)
# ---------------------------------------------------------------------------

def md_to_html(md_text):
    if not md_text:
        return "<p><em>No briefing available. Run briefing_test.py first.</em></p>"
    lines = md_text.split("\n")
    out = []
    in_list = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append("")
            continue
        # Headers
        if stripped.startswith("# "):
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append(f"<h2>{esc(stripped[2:])}</h2>")
            continue
        if stripped.startswith("## "):
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append(f"<h3>{esc(stripped[3:])}</h3>")
            continue
        # List items
        m = re.match(r"^(\d+)\.\s+(.*)$", stripped)
        if m:
            if in_list:
                out.append("</ul>")
            out.append("<ol start=\"{}\">".format(m.group(1)))
            out.append(f"<li>{inline_md(m.group(2))}</li>")
            out.append("</ol>")
            in_list = False
            continue
        if stripped.startswith("* ") or stripped.startswith("- ") or stripped.startswith("\t*"):
            content = re.sub(r"^[\t ]*[*\-]\s+", "", stripped)
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{inline_md(content)}</li>")
            continue
        # Paragraph
        if in_list:
            out.append("</ul>")
            in_list = False
        out.append(f"<p>{inline_md(stripped)}</p>")
    if in_list:
        out.append("</ul>")
    return "\n".join(out)


def inline_md(text):
    """Convert inline markdown: **bold**, *italic*, `code`."""
    t = esc(text)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"\*(.+?)\*", r"<em>\1</em>", t)
    t = re.sub(r"`(.+?)`", r"<code>\1</code>", t)
    return t


def esc(text):
    return html.escape(str(text))


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

def build_html(tenders, articles, briefing_md, tenders_raw):
    today = datetime.now().strftime("%d %B %Y")

    # Group tenders by view
    views = {}
    for t in tenders:
        v = t.get("_view", "All")
        views.setdefault(v, [])
        views[v].append(t)

    # Sort each view by bid_closing_date descending
    def sort_key(t):
        d = t.get("bid_closing_date") or t.get("sales_end_date") or t.get("dates") or ""
        m = re.search(r"(\d{2})-(\d{2})-(\d{4})", d)
        if m:
            return f"{m.group(3)}{m.group(2)}{m.group(1)}"
        return "0"

    for v in views:
        views[v].sort(key=sort_key, reverse=True)

    # Portal stats from tenders_raw
    by_view = {}
    if isinstance(tenders_raw, dict):
        by_view = tenders_raw.get("by_view", {})

    # Build tender table rows JSON for each view (bilingual-aware)
    def split_cat_grade(cg):
        """Split 'Category [Grade1,Grade2]' into (category, grade_str)."""
        grade_m = re.search(r"\[([^\]]+)\]", cg)
        grade = grade_m.group(1) if grade_m else ""
        cat_m = re.match(r"^([^\[]+)", cg)
        cat = cat_m.group(1).strip() if cat_m else cg
        return cat, grade

    def split_type(tt):
        """Split 'TypeName [ VendorType]' into type name."""
        m = re.match(r"^([^\[]+)", tt)
        return m.group(1).strip() if m else tt

    views_json = {}
    for view_name, view_tenders in views.items():
        rows = []
        for t in view_tenders:
            # Bilingual fields — try _en/_ar suffixes first, fall back to unsuffixed
            name_ar = t.get("tender_name_ar", t.get("tender_name", ""))
            name_en = t.get("tender_name_en", "")
            entity_ar = t.get("entity_ar", t.get("entity", ""))
            entity_en = t.get("entity_en", "")

            cg_ar = t.get("category_grade_ar", t.get("category_grade", ""))
            cg_en = t.get("category_grade_en", "")
            cat_ar, grade_ar = split_cat_grade(cg_ar)
            cat_en, grade_en = split_cat_grade(cg_en) if cg_en else ("", "")

            type_ar = split_type(t.get("tender_type_ar", t.get("tender_type", "")))
            type_en = split_type(t.get("tender_type_en", ""))

            # Re-tender detection across both languages
            all_names = name_ar + " " + name_en
            is_retender = "اعادة طرح" in all_names or "إعادة طرح" in all_names or "recall" in name_en.lower()

            # SCC relevance — check both languages
            all_cats = cg_ar + " " + cg_en
            is_scc = any(kw in all_cats for kw in [
                "مقاولات المواني", "المقاولات العمرانيه", "مقاولات شبكات",
                "مقاولات الكهروميكانيكية", "Construction",
                "Ports", "Roads", "Bridges", "Dams", "Pipeline",
            ])

            rows.append({
                "n": t.get("tender_number", ""),
                "na": name_ar,
                "ne": name_en or name_ar,
                "ea": entity_ar,
                "ee": entity_en or entity_ar,
                "ca": cat_ar,
                "ce": cat_en or cat_ar,
                "ga": grade_ar,
                "ge": grade_en or grade_ar,
                "ta": type_ar,
                "te": type_en or type_ar,
                "close": t.get("bid_closing_date") or t.get("sales_end_date") or "",
                "fee": t.get("fee", ""),
                "rt": is_retender,
                "scc": is_scc,
            })
        views_json[view_name] = rows

    # Build article cards
    # Sort by date descending
    def article_sort_key(a):
        pub = a.get("published", "")
        if not pub:
            return "0"
        m = re.match(r"(\d{4})-(\d{2})-(\d{2})", pub)
        if m:
            return pub
        return "0"

    sorted_articles = sorted(articles, key=article_sort_key, reverse=True)
    articles_html_parts = []
    for a in sorted_articles[:80]:
        source = esc(a.get("source", "Unknown"))
        title = esc(a.get("title", ""))
        link = a.get("link", "#")
        pub = esc(a.get("published", "")[:10])
        summary = esc(a.get("summary", ""))[:200]
        colour = get_source_colour(source)
        # Shorten source for tag
        short_source = source
        for prefix in ["Oman Observer — ", "Google News — "]:
            if short_source.startswith(esc(prefix)):
                short_source = short_source[len(esc(prefix)):]
                break

        articles_html_parts.append(f"""
        <div class="news-card">
          <span class="source-tag" style="background:{colour}">{short_source}</span>
          <h4 class="news-title">{title}</h4>
          <span class="news-date">{pub}</span>
          <p class="news-summary">{summary}</p>
          <a href="{esc(link)}" target="_blank" rel="noopener" class="news-link">Read full article &rarr;</a>
        </div>""")
    articles_html = "\n".join(articles_html_parts)

    # Stats cards
    total_tenders = len(tenders)
    stat_cards = ""
    if by_view:
        for label, count in by_view.items():
            short = label.split("/")[0].split(" ")[0]
            stat_cards += f'<div class="stat-card"><div class="stat-number">{count}</div><div class="stat-label">{esc(label)}</div></div>\n'
    else:
        for vname, vtenders in views.items():
            stat_cards += f'<div class="stat-card"><div class="stat-number">{len(vtenders)}</div><div class="stat-label">{esc(vname)}</div></div>\n'

    # Category breakdown (prefer English labels)
    cat_counts = {}
    for t in tenders:
        cg = t.get("category_grade_en") or t.get("category_grade_ar") or t.get("category_grade", "")
        m = re.match(r"^([^\[]+)", cg)
        cat = m.group(1).strip() if m else cg
        if cat:
            cat_counts[cat] = cat_counts.get(cat, 0) + 1
    max_cat = max(cat_counts.values()) if cat_counts else 1
    cat_bars = ""
    for cat, count in sorted(cat_counts.items(), key=lambda x: -x[1]):
        pct = int(count / max_cat * 100)
        cat_bars += f'<div class="cat-row"><span class="cat-label">{esc(cat)}</span><div class="cat-bar-bg"><div class="cat-bar" style="width:{pct}%">{count}</div></div></div>\n'

    # View tab buttons
    view_names = list(views_json.keys())
    tab_buttons = ""
    for i, vn in enumerate(view_names):
        active = " active" if i == 0 else ""
        tab_buttons += f'<button class="tab-btn{active}" onclick="switchTab(\'{esc(vn)}\')">{esc(vn)} ({len(views_json[vn])})</button> '

    briefing_html = md_to_html(briefing_md)
    views_json_str = json.dumps(views_json, ensure_ascii=False)
    first_view = view_names[0] if view_names else ""

    return f"""<!DOCTYPE html>
<html lang="en" dir="ltr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SCC Market Intelligence Module</title>
<style>
:root {{
  --navy: #1F3A5F;
  --blue: #2E75B6;
  --blue-light: #E8F0FE;
  --amber: #FFF3CD;
  --green-accent: #2E75B6;
  --bg: #F4F6F9;
  --card-bg: #FFFFFF;
  --text: #212529;
  --text-muted: #6c757d;
  --border: #DEE2E6;
  --shadow: 0 2px 8px rgba(0,0,0,0.08);
  --radius: 8px;
}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family: 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background:var(--bg); color:var(--text); line-height:1.6; }}
a {{ color:var(--blue); text-decoration:none; }}
a:hover {{ text-decoration:underline; }}

/* Header */
.header {{ background:var(--navy); color:#fff; padding:28px 40px; display:flex; justify-content:space-between; align-items:center; }}
.header-left h1 {{ font-size:22px; font-weight:600; letter-spacing:0.5px; }}
.header-left p {{ font-size:13px; color:rgba(255,255,255,0.65); margin-top:2px; }}
.header-right {{ font-size:11px; color:rgba(255,255,255,0.45); text-align:right; }}

/* Container */
.container {{ max-width:1280px; margin:0 auto; padding:24px 32px; }}
.section {{ margin-bottom:32px; }}
.section-title {{ font-size:18px; font-weight:600; color:var(--navy); margin-bottom:14px; display:flex; align-items:center; gap:8px; }}
.section-title .badge {{ font-size:10px; background:var(--blue); color:#fff; padding:2px 8px; border-radius:10px; text-transform:uppercase; letter-spacing:0.5px; }}

/* Briefing card */
.briefing-card {{ background:linear-gradient(135deg, #EBF2FA 0%, #F7FAFC 100%); border:1px solid #C9D9EA; border-radius:var(--radius); padding:28px 32px; box-shadow:var(--shadow); }}
.briefing-card h2 {{ font-size:16px; color:var(--navy); margin-bottom:8px; }}
.briefing-card h3 {{ font-size:14px; color:var(--blue); margin:12px 0 4px; }}
.briefing-card p {{ margin:6px 0; font-size:14px; }}
.briefing-card ul, .briefing-card ol {{ margin:6px 0 6px 20px; font-size:14px; }}
.briefing-card li {{ margin:4px 0; }}
.briefing-card strong {{ color:var(--navy); }}

/* Tabs */
.tabs {{ display:flex; gap:6px; margin-bottom:12px; flex-wrap:wrap; }}
.tab-btn {{ padding:7px 16px; border:1px solid var(--border); border-radius:6px 6px 0 0; background:#fff; cursor:pointer; font-size:13px; color:var(--text-muted); transition:all 0.15s; }}
.tab-btn:hover {{ background:var(--blue-light); }}
.tab-btn.active {{ background:var(--navy); color:#fff; border-color:var(--navy); }}

/* Filter */
.filter-bar {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:10px; gap:12px; flex-wrap:wrap; }}
.filter-input {{ padding:8px 14px; border:1px solid var(--border); border-radius:6px; font-size:13px; width:320px; max-width:100%; }}
.filter-input:focus {{ outline:none; border-color:var(--blue); box-shadow:0 0 0 2px rgba(46,117,182,0.15); }}
.count-label {{ font-size:13px; color:var(--text-muted); }}

/* Table */
.table-wrap {{ overflow-x:auto; background:var(--card-bg); border-radius:var(--radius); box-shadow:var(--shadow); }}
table {{ width:100%; border-collapse:collapse; font-size:13px; }}
th {{ background:var(--navy); color:#fff; padding:10px 12px; text-align:left; font-weight:500; white-space:nowrap; position:sticky; top:0; }}
td {{ padding:9px 12px; border-bottom:1px solid var(--border); vertical-align:top; }}
tr:hover td {{ background:rgba(46,117,182,0.04); }}
tr.retender td {{ background:var(--amber); }}
tr.scc-relevant {{ border-left:3px solid var(--green-accent); }}
.td-name {{ max-width:280px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}

/* News grid */
.news-grid {{ display:grid; grid-template-columns:repeat(auto-fill, minmax(340px, 1fr)); gap:16px; }}
.news-card {{ background:var(--card-bg); border-radius:var(--radius); padding:18px 20px; box-shadow:var(--shadow); border:1px solid var(--border); display:flex; flex-direction:column; }}
.source-tag {{ display:inline-block; font-size:10px; color:#fff; padding:2px 8px; border-radius:10px; margin-bottom:8px; font-weight:500; text-transform:uppercase; letter-spacing:0.3px; align-self:flex-start; }}
.news-title {{ font-size:14px; font-weight:600; color:var(--text); margin-bottom:4px; line-height:1.4; }}
.news-date {{ font-size:11px; color:var(--text-muted); margin-bottom:6px; }}
.news-summary {{ font-size:13px; color:var(--text-muted); flex:1; margin-bottom:8px; }}
.news-link {{ font-size:12px; font-weight:500; }}

/* Stats */
.stats-row {{ display:flex; gap:16px; flex-wrap:wrap; margin-bottom:20px; }}
.stat-card {{ background:var(--card-bg); border-radius:var(--radius); padding:20px 24px; box-shadow:var(--shadow); min-width:160px; text-align:center; flex:1; border-top:3px solid var(--blue); }}
.stat-number {{ font-size:28px; font-weight:700; color:var(--navy); }}
.stat-label {{ font-size:12px; color:var(--text-muted); margin-top:4px; }}
.cat-row {{ display:flex; align-items:center; margin:4px 0; font-size:12px; }}
.cat-label {{ width:280px; min-width:200px; color:var(--text-muted); text-align:right; padding-right:10px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
.cat-bar-bg {{ flex:1; background:#EEE; border-radius:3px; height:18px; overflow:hidden; }}
.cat-bar {{ background:var(--blue); height:100%; border-radius:3px; color:#fff; font-size:10px; padding:0 6px; line-height:18px; min-width:24px; text-align:right; }}

/* Language toggle */
.lang-toggle {{ padding:5px 12px; border:1px solid var(--border); border-radius:5px; background:#fff; cursor:pointer; font-size:12px; font-weight:600; color:var(--text-muted); }}
.lang-toggle:hover {{ border-color:var(--blue); }}
.lang-active {{ color:var(--navy); }}
.lang-dim {{ color:#bbb; }}

/* Footer */
.footer {{ background:var(--navy); color:rgba(255,255,255,0.55); padding:20px 40px; font-size:12px; text-align:center; margin-top:40px; }}
.footer a {{ color:rgba(255,255,255,0.7); }}
</style>
</head>
<body>

<div class="header">
  <div class="header-left">
    <h1>SCC Market Intelligence Module</h1>
    <p>Validation Preview &mdash; {today}</p>
  </div>
  <div class="header-right">Powered by<br><strong>Zavia-ai</strong></div>
</div>

<div class="container">

  <!-- SECTION 1: Executive Briefing -->
  <div class="section">
    <div class="section-title">Weekly Executive Briefing <span class="badge">AI Generated</span></div>
    <div class="briefing-card">
      {briefing_html}
    </div>
  </div>

  <!-- SECTION 2: Tender Pipeline -->
  <div class="section">
    <div class="section-title">Tender Pipeline</div>
    <div class="tabs" id="tabs">{tab_buttons}</div>
    <div class="filter-bar">
      <input type="text" class="filter-input" id="filterInput" placeholder="Filter tenders (type to search across all columns)..." oninput="applyFilter()">
      <div style="display:flex;align-items:center;gap:10px;">
        <span class="count-label" id="countLabel"></span>
        <button class="lang-toggle" id="langToggle" onclick="toggleLang()"><span class="lang-active">EN</span> | <span class="lang-dim">AR</span></button>
      </div>
    </div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Tender No</th>
            <th>Name</th>
            <th>Entity</th>
            <th>Category</th>
            <th>Grade</th>
            <th>Type</th>
            <th>Bid Closing</th>
            <th>Fee</th>
          </tr>
        </thead>
        <tbody id="tenderBody"></tbody>
      </table>
    </div>
  </div>

  <!-- SECTION 3: News Intelligence -->
  <div class="section">
    <div class="section-title">News Intelligence</div>
    <div class="news-grid">
      {articles_html}
    </div>
  </div>

  <!-- SECTION 4: Portal Overview -->
  <div class="section">
    <div class="section-title">Portal Overview</div>
    <div class="stats-row">
      {stat_cards}
    </div>
    <div style="max-width:700px;">
      {cat_bars}
    </div>
  </div>

</div>

<div class="footer">
  Validation preview &mdash; not production. Data sourced from
  <a href="https://etendering.tenderboard.gov.om" target="_blank">etendering.tenderboard.gov.om</a>
  and Oman news RSS feeds.<br>
  Zavia-ai &copy; 2026
</div>

<script>
const ALL_VIEWS = {views_json_str};
let currentView = "{esc(first_view)}";
let currentLang = "en";

function switchTab(view) {{
  currentView = view;
  document.querySelectorAll('.tab-btn').forEach(b => {{
    const bView = b.getAttribute('onclick').match(/'([^']+)'/)[1];
    b.classList.toggle('active', bView === view);
  }});
  applyFilter();
}}

function toggleLang() {{
  currentLang = currentLang === "en" ? "ar" : "en";
  const btn = document.getElementById('langToggle');
  if (currentLang === "en") {{
    btn.innerHTML = '<span class="lang-active">EN</span> | <span class="lang-dim">AR</span>';
  }} else {{
    btn.innerHTML = '<span class="lang-dim">EN</span> | <span class="lang-active">AR</span>';
  }}
  applyFilter();
}}

function applyFilter() {{
  const filter = document.getElementById('filterInput').value.toLowerCase();
  const rows = ALL_VIEWS[currentView] || [];
  const tbody = document.getElementById('tenderBody');
  const L = currentLang;
  tbody.innerHTML = '';
  let shown = 0;
  for (const r of rows) {{
    // Search across BOTH languages regardless of display
    const searchStr = [r.n, r.na, r.ne, r.ea, r.ee, r.ca, r.ce, r.ga, r.ge, r.ta, r.te, r.close, r.fee].join(' ').toLowerCase();
    if (filter && searchStr.indexOf(filter) === -1) continue;
    shown++;
    const name = L === "en" ? r.ne : r.na;
    const entity = L === "en" ? r.ee : r.ea;
    const cat = L === "en" ? r.ce : r.ca;
    const grade = L === "en" ? r.ge : r.ga;
    const ttype = L === "en" ? r.te : r.ta;
    const nameShort = name.length > 80 ? name.substring(0, 80) + '...' : name;
    const tr = document.createElement('tr');
    if (r.rt) tr.classList.add('retender');
    if (r.scc) tr.classList.add('scc-relevant');
    tr.innerHTML =
      '<td>' + esc(r.n) + '</td>' +
      '<td class="td-name" title="' + escAttr(name) + '">' + esc(nameShort) + '</td>' +
      '<td>' + esc(entity) + '</td>' +
      '<td>' + esc(cat) + '</td>' +
      '<td>' + esc(grade) + '</td>' +
      '<td>' + esc(ttype) + '</td>' +
      '<td>' + esc(r.close) + '</td>' +
      '<td>' + esc(r.fee) + '</td>';
    tbody.appendChild(tr);
  }}
  document.getElementById('countLabel').textContent = 'Showing ' + shown + ' of ' + rows.length + ' tenders';
}}

function esc(s) {{ const d = document.createElement('div'); d.textContent = s || ''; return d.innerHTML; }}
function escAttr(s) {{ return (s || '').replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;'); }}

// Init
switchTab(currentView);
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

class DashboardHandler(http.server.BaseHTTPRequestHandler):
    html_content = b""

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(self.html_content)))
        self.end_headers()
        self.wfile.write(self.html_content)

    def log_message(self, format, *args):
        # Suppress per-request logs
        pass


def main():
    print("Loading data...")
    tenders_raw = load_json_file("tenders.json")
    news_raw = load_json_file("news.json")
    briefing_md = load_file("briefing_output.md")

    tenders = extract_tenders(tenders_raw) if tenders_raw else []
    articles = extract_articles(news_raw) if news_raw else []

    print(f"  Tenders: {len(tenders)}")
    print(f"  Articles: {len(articles)}")
    print(f"  Briefing: {'loaded' if briefing_md else 'not found'}")

    print("Building dashboard HTML...")
    html_str = build_html(tenders, articles, briefing_md, tenders_raw)
    DashboardHandler.html_content = html_str.encode("utf-8")
    print(f"  HTML size: {len(DashboardHandler.html_content):,} bytes")

    server = http.server.HTTPServer(("", PORT), DashboardHandler)
    print(f"\nDashboard running at http://localhost:{PORT} — press Ctrl+C to stop")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()


if __name__ == "__main__":
    main()
