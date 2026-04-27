"""
SCC Market Intelligence Dashboard — validation preview.

Layout:
  ABOVE THE FOLD: Stats bar, AI briefing, SCC-relevant tenders table
  BELOW THE FOLD: Full tender pipeline (collapsed), Market news (collapsed)

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

SOURCE_COLOURS = {
    "Oman Observer": "#2E75B6",
    "Times of Oman": "#D4520B",
    "Google News": "#0F9D58",
}

SCC_CATEGORY_KW = [
    "Construction", "Ports", "Roads", "Bridges", "Pipeline",
    "Electromechanical", "Dams", "Marine", "مقاولات",
]
SCC_GRADE_KW = ["Excellent", "First", "Second", "الممتازة", "الأولى", "الثانية"]

NEWS_KEYWORDS = [
    "construction", "infrastructure", "tender", "contract", "project",
    "investment", "industrial", "roads", "bridges", "pipeline", "ministry",
    "budget", "economic", "zone", "development", "port", "airport",
    "housing", "railway", "dam", "water", "sewage",
    "galfar", "strabag", "al tasnim", "l&t", "towell", "hassan allam",
    "arab contractors", "ozkar", "sarooj", "mtcit", "opaz", "riyada",
]

PAGINATION_WORDS = ["الأولى", "السابقة", "التالية", "الأخيرة", "Previous", "Next", "Last"]


def load_file(name):
    path = os.path.join(SCRIPT_DIR, name)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def load_json_file(name):
    text = load_file(name)
    return json.loads(text) if text else None


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
            for src, sd in raw["sources"].items():
                if isinstance(sd, dict) and "articles" in sd:
                    for a in sd["articles"]:
                        a.setdefault("source", src)
                        articles.append(a)
                elif isinstance(sd, list):
                    for a in sd:
                        a.setdefault("source", src)
                        articles.append(a)
            return articles
        for key in ("articles", "items", "data"):
            if key in raw and isinstance(raw[key], list):
                return raw[key]
    return []


def get_source_colour(source):
    for key, c in SOURCE_COLOURS.items():
        if key.lower() in source.lower():
            return c
    return "#6c757d"


def is_pagination_row(t):
    """Return True if this 'tender' is actually a scraped pagination control."""
    for field in ("tender_number", "tender_name_ar", "tender_name_en", "tender_name"):
        val = t.get(field, "")
        if any(pw in val for pw in PAGINATION_WORDS):
            return True
    return False


def bi(t, field):
    return t.get(f"{field}_en") or t.get(f"{field}_ar") or t.get(field, "")


def split_cat_grade(cg):
    gm = re.search(r"\[([^\]]+)\]", cg)
    grade = gm.group(1) if gm else ""
    cm = re.match(r"^([^\[]+)", cg)
    cat = cm.group(1).strip() if cm else cg
    return cat, grade


def split_type(tt):
    m = re.match(r"^([^\[]+)", tt)
    return m.group(1).strip() if m else tt


def is_scc_relevant(t):
    cg_ar = t.get("category_grade_ar", t.get("category_grade", ""))
    cg_en = t.get("category_grade_en", "")
    cg = cg_ar + " " + cg_en
    cat_match = any(kw in cg for kw in SCC_CATEGORY_KW)
    grade_match = any(kw in cg for kw in SCC_GRADE_KW)
    return cat_match and grade_match


def is_retender(t):
    names = (t.get("tender_name_ar", "") + " " + t.get("tender_name_en", "") +
             " " + t.get("tender_name", ""))
    return "اعادة طرح" in names or "إعادة طرح" in names or "recall" in names.lower()


# ---------------------------------------------------------------------------
# Markdown -> HTML
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
                out.append("</ul>"); in_list = False
            out.append("")
            continue
        if stripped.startswith("# "):
            if in_list: out.append("</ul>"); in_list = False
            out.append(f"<h2>{esc(stripped[2:])}</h2>"); continue
        if stripped.startswith("## "):
            if in_list: out.append("</ul>"); in_list = False
            out.append(f"<h3>{esc(stripped[3:])}</h3>"); continue
        m = re.match(r"^(\d+)\.\s+(.*)$", stripped)
        if m:
            if in_list: out.append("</ul>"); in_list = False
            out.append(f'<ol start="{m.group(1)}"><li>{inline_md(m.group(2))}</li></ol>')
            continue
        if stripped.startswith("* ") or stripped.startswith("- ") or stripped.startswith("\t*"):
            content = re.sub(r"^[\t ]*[*\-]\s+", "", stripped)
            if not in_list: out.append("<ul>"); in_list = True
            out.append(f"<li>{inline_md(content)}</li>"); continue
        if in_list: out.append("</ul>"); in_list = False
        out.append(f"<p>{inline_md(stripped)}</p>")
    if in_list:
        out.append("</ul>")
    return "\n".join(out)


def inline_md(text):
    t = esc(text)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"\*(.+?)\*", r"<em>\1</em>", t)
    t = re.sub(r"`(.+?)`", r"<code>\1</code>", t)
    return t


def esc(text):
    return html.escape(str(text))


# ---------------------------------------------------------------------------
# Build tender row JSON
# ---------------------------------------------------------------------------

def tender_to_row(t):
    cg_ar = t.get("category_grade_ar", t.get("category_grade", ""))
    cg_en = t.get("category_grade_en", "")
    cat_ar, grade_ar = split_cat_grade(cg_ar)
    cat_en, grade_en = split_cat_grade(cg_en) if cg_en else ("", "")
    return {
        "n": t.get("tender_number", ""),
        "na": t.get("tender_name_ar", t.get("tender_name", "")),
        "ne": t.get("tender_name_en", "") or t.get("tender_name_ar", t.get("tender_name", "")),
        "ea": t.get("entity_ar", t.get("entity", "")),
        "ee": t.get("entity_en", "") or t.get("entity_ar", t.get("entity", "")),
        "ca": cat_ar, "ce": cat_en or cat_ar,
        "ga": grade_ar, "ge": grade_en or grade_ar,
        "ta": split_type(t.get("tender_type_ar", t.get("tender_type", ""))),
        "te": split_type(t.get("tender_type_en", "")) or split_type(t.get("tender_type_ar", t.get("tender_type", ""))),
        "close": t.get("bid_closing_date") or t.get("sales_end_date") or "",
        "rt": is_retender(t),
        "scc": is_scc_relevant(t),
    }


def sort_key_date(r):
    d = r.get("close", "")
    m = re.search(r"(\d{2})-(\d{2})-(\d{4})", d)
    return f"{m.group(3)}{m.group(2)}{m.group(1)}" if m else "0"


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

def build_html(tenders, articles, briefing_md, tenders_raw):
    today = datetime.now().strftime("%d %B %Y")

    # Filter out pagination rows
    tenders = [t for t in tenders if not is_pagination_row(t)]

    # --- SCC-relevant tenders ---
    scc_tenders = [t for t in tenders if is_scc_relevant(t)]
    scc_rows = sorted([tender_to_row(t) for t in scc_tenders], key=sort_key_date, reverse=True)

    # --- All tenders grouped by view ---
    views = {}
    for t in tenders:
        v = t.get("_view", "All")
        views.setdefault(v, [])
        views[v].append(t)
    all_views_json = {}
    for vn, vt in views.items():
        rows = sorted([tender_to_row(t) for t in vt], key=sort_key_date, reverse=True)
        all_views_json[vn] = rows
    total_by_view = {vn: len(vt) for vn, vt in views.items()}

    # --- News: dedup + relevance filter ---
    seen_titles = set()
    deduped = []
    for a in articles:
        title = a.get("title", "").strip().lower()
        if title and title not in seen_titles:
            seen_titles.add(title)
            deduped.append(a)
    relevant_news = []
    for a in deduped:
        text = (a.get("title", "") + " " + a.get("summary", "")).lower()
        if any(kw in text for kw in NEWS_KEYWORDS):
            relevant_news.append(a)

    # Sort by date descending
    def art_sort(a):
        p = a.get("published", "")
        m = re.match(r"(\d{4}-\d{2}-\d{2})", p)
        return m.group(1) if m else "0"
    relevant_news.sort(key=art_sort, reverse=True)

    # --- Stats ---
    stats = [
        ("New Tenders", total_by_view.get("New/Floated Tenders", 0), "#E8F0FE", "#2E75B6"),
        ("In-Process", total_by_view.get("In-Process Tenders", 0), "#E8F0FE", "#2E75B6"),
        ("Sub-Contract", total_by_view.get("Sub-Contract Tenders", 0), "#E8F0FE", "#2E75B6"),
        ("SCC-Relevant", len(scc_tenders), "#E8F7EE", "#1A7F37"),
        ("News Signals", len(relevant_news), "#FFF8E1", "#B8860B"),
    ]
    stats_html = ""
    for label, count, bg, border in stats:
        stats_html += f'<div class="stat-card" style="border-top:3px solid {border};background:{bg}"><div class="stat-number">{count}</div><div class="stat-label">{label}</div></div>\n'

    # --- Briefing ---
    briefing_html = md_to_html(briefing_md)

    # --- News cards ---
    news_cards = ""
    for a in relevant_news[:60]:
        source = esc(a.get("source", "Unknown"))
        title = esc(a.get("title", ""))
        link = a.get("link", "#")
        pub = esc(a.get("published", "")[:10])
        summary = esc(a.get("summary", ""))[:200]
        colour = get_source_colour(source)
        short_src = source
        for prefix in ["Oman Observer — ", "Google News — "]:
            ep = esc(prefix)
            if short_src.startswith(ep):
                short_src = short_src[len(ep):]
                break
        news_cards += f"""<div class="news-card">
<span class="source-tag" style="background:{colour}">{short_src}</span>
<h4 class="news-title">{title}</h4>
<span class="news-date">{pub}</span>
<p class="news-summary">{summary}</p>
<a href="{esc(link)}" target="_blank" rel="noopener" class="news-link">Read full article &rarr;</a>
</div>\n"""

    # --- View tab buttons for full pipeline ---
    view_names = list(all_views_json.keys())
    tab_btns = ""
    for i, vn in enumerate(view_names):
        active = " active" if i == 0 else ""
        tab_btns += f'<button class="tab-btn{active}" onclick="switchTab(\'{esc(vn)}\')">{esc(vn)} ({len(all_views_json[vn])})</button> '

    # --- File timestamp ---
    tj_path = os.path.join(SCRIPT_DIR, "tenders.json")
    if os.path.exists(tj_path):
        ts = datetime.fromtimestamp(os.path.getmtime(tj_path)).strftime("%d %b %Y %H:%M")
    else:
        ts = "unknown"

    scc_json = json.dumps(scc_rows, ensure_ascii=False)
    all_json = json.dumps(all_views_json, ensure_ascii=False)
    first_view = view_names[0] if view_names else ""

    return f"""<!DOCTYPE html>
<html lang="en" dir="ltr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SCC Market Intelligence Module</title>
<style>
:root {{ --navy:#1F3A5F; --blue:#2E75B6; --blue-light:#E8F0FE; --amber:#FFF3CD; --bg:#F4F6F9; --card:#FFF; --text:#212529; --muted:#6c757d; --border:#DEE2E6; --shadow:0 2px 8px rgba(0,0,0,0.08); --r:8px; }}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif; background:var(--bg); color:var(--text); line-height:1.6; }}
a {{ color:var(--blue); text-decoration:none; }} a:hover {{ text-decoration:underline; }}

.header {{ background:var(--navy); color:#fff; padding:24px 40px; display:flex; justify-content:space-between; align-items:center; }}
.header h1 {{ font-size:21px; font-weight:600; letter-spacing:.5px; }}
.header p {{ font-size:13px; color:rgba(255,255,255,.6); margin-top:2px; }}
.header-right {{ font-size:11px; color:rgba(255,255,255,.4); text-align:right; }}

.container {{ max-width:1280px; margin:0 auto; padding:20px 32px; }}
.section {{ margin-bottom:28px; }}
.section-title {{ font-size:17px; font-weight:600; color:var(--navy); margin-bottom:12px; display:flex; align-items:center; gap:8px; }}
.badge {{ font-size:10px; background:var(--blue); color:#fff; padding:2px 8px; border-radius:10px; text-transform:uppercase; letter-spacing:.5px; }}

/* Stats bar */
.stats-bar {{ display:flex; gap:12px; flex-wrap:wrap; margin-bottom:24px; }}
.stat-card {{ border-radius:var(--r); padding:16px 20px; box-shadow:var(--shadow); min-width:140px; text-align:center; flex:1; }}
.stat-number {{ font-size:26px; font-weight:700; color:var(--navy); }}
.stat-label {{ font-size:11px; color:var(--muted); margin-top:2px; text-transform:uppercase; letter-spacing:.3px; }}

/* Briefing */
.briefing-card {{ background:linear-gradient(135deg,#EBF2FA 0%,#F7FAFC 100%); border:1px solid #C9D9EA; border-radius:var(--r); padding:24px 28px; box-shadow:var(--shadow); }}
.briefing-card h2 {{ font-size:15px; color:var(--navy); margin-bottom:6px; }}
.briefing-card h3 {{ font-size:14px; color:var(--blue); margin:10px 0 4px; }}
.briefing-card p {{ margin:5px 0; font-size:13.5px; }}
.briefing-card ul,.briefing-card ol {{ margin:5px 0 5px 20px; font-size:13.5px; }}
.briefing-card li {{ margin:3px 0; }}
.briefing-card strong {{ color:var(--navy); }}

/* Table shared */
.filter-bar {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; gap:10px; flex-wrap:wrap; }}
.filter-input {{ padding:7px 12px; border:1px solid var(--border); border-radius:6px; font-size:13px; width:300px; max-width:100%; }}
.filter-input:focus {{ outline:none; border-color:var(--blue); box-shadow:0 0 0 2px rgba(46,117,182,.15); }}
.count-label {{ font-size:12px; color:var(--muted); }}
.lang-toggle {{ padding:4px 10px; border:1px solid var(--border); border-radius:5px; background:#fff; cursor:pointer; font-size:11px; font-weight:600; color:var(--muted); }}
.lang-toggle:hover {{ border-color:var(--blue); }}
.la {{ color:var(--navy); }}
.ld {{ color:#bbb; }}

.table-wrap {{ overflow-x:auto; background:var(--card); border-radius:var(--r); box-shadow:var(--shadow); }}
table {{ width:100%; border-collapse:collapse; font-size:12.5px; }}
th {{ background:var(--navy); color:#fff; padding:9px 10px; text-align:left; font-weight:500; white-space:nowrap; position:sticky; top:0; }}
td {{ padding:8px 10px; border-bottom:1px solid var(--border); vertical-align:top; }}
tr:hover td {{ background:rgba(46,117,182,.04); }}
tr.rt td {{ background:var(--amber); }}
.td-name {{ max-width:260px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}

/* Tabs */
.tabs {{ display:flex; gap:5px; margin-bottom:10px; flex-wrap:wrap; }}
.tab-btn {{ padding:6px 14px; border:1px solid var(--border); border-radius:6px 6px 0 0; background:#fff; cursor:pointer; font-size:12px; color:var(--muted); }}
.tab-btn:hover {{ background:var(--blue-light); }}
.tab-btn.active {{ background:var(--navy); color:#fff; border-color:var(--navy); }}

/* Collapsible */
.collapsible-header {{ display:flex; align-items:center; gap:8px; cursor:pointer; padding:14px 20px; background:var(--card); border:1px solid var(--border); border-radius:var(--r); box-shadow:var(--shadow); user-select:none; }}
.collapsible-header:hover {{ background:#F8FAFC; }}
.collapsible-header h3 {{ font-size:15px; font-weight:600; color:var(--navy); margin:0; }}
.collapsible-header .arrow {{ font-size:12px; color:var(--muted); transition:transform .2s; }}
.collapsible-header.open .arrow {{ transform:rotate(90deg); }}
.collapsible-body {{ max-height:0; overflow:hidden; transition:max-height .35s ease; }}
.collapsible-body.open {{ max-height:none; }}
.collapsible-inner {{ padding:16px 0 0; }}

/* News */
.news-grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(340px,1fr)); gap:14px; }}
.news-card {{ background:var(--card); border-radius:var(--r); padding:16px 18px; box-shadow:var(--shadow); border:1px solid var(--border); display:flex; flex-direction:column; }}
.source-tag {{ display:inline-block; font-size:9px; color:#fff; padding:2px 7px; border-radius:10px; margin-bottom:6px; font-weight:500; text-transform:uppercase; letter-spacing:.3px; align-self:flex-start; }}
.news-title {{ font-size:13px; font-weight:600; color:var(--text); margin-bottom:3px; line-height:1.4; }}
.news-date {{ font-size:10px; color:var(--muted); margin-bottom:5px; }}
.news-summary {{ font-size:12px; color:var(--muted); flex:1; margin-bottom:6px; }}
.news-link {{ font-size:11px; font-weight:500; }}

.footer {{ background:var(--navy); color:rgba(255,255,255,.5); padding:18px 40px; font-size:11px; text-align:center; margin-top:36px; }}
.footer a {{ color:rgba(255,255,255,.65); }}
</style>
</head>
<body>

<div class="header">
  <div>
    <h1>SCC Market Intelligence Module</h1>
    <p>Weekly Brief &mdash; {today}</p>
  </div>
  <div class="header-right">Powered by<br><strong>Zavia-ai</strong></div>
</div>

<div class="container">

  <!-- STATS BAR -->
  <div class="stats-bar">{stats_html}</div>

  <!-- EXECUTIVE BRIEFING -->
  <div class="section">
    <div class="section-title">Executive Briefing <span class="badge">AI Generated</span></div>
    <div class="briefing-card">{briefing_html}</div>
  </div>

  <!-- SCC-RELEVANT TENDERS -->
  <div class="section">
    <div class="section-title">SCC-Relevant Tenders ({len(scc_rows)})</div>
    <div class="filter-bar">
      <input type="text" class="filter-input" id="sccFilter" placeholder="Filter SCC tenders..." oninput="renderSCC()">
      <div style="display:flex;align-items:center;gap:8px">
        <span class="count-label" id="sccCount"></span>
        <button class="lang-toggle" id="sccLang" onclick="toggleLang('scc')"><span class="la">EN</span> | <span class="ld">AR</span></button>
      </div>
    </div>
    <div class="table-wrap">
      <table><thead><tr>
        <th>Tender No</th><th>Name</th><th>Entity</th><th>Category</th><th>Grade</th><th>Type</th><th>Bid Closing</th>
      </tr></thead><tbody id="sccBody"></tbody></table>
    </div>
  </div>

  <!-- FULL PIPELINE (collapsed) -->
  <div class="section">
    <div class="collapsible-header" onclick="toggle('pipeline')">
      <span class="arrow" id="pipelineArrow">&#9654;</span>
      <h3>All Tenders ({len(tenders)}) </h3>
    </div>
    <div class="collapsible-body" id="pipelineBody">
      <div class="collapsible-inner">
        <div class="tabs" id="tabs">{tab_btns}</div>
        <div class="filter-bar">
          <input type="text" class="filter-input" id="allFilter" placeholder="Filter all tenders..." oninput="renderAll()">
          <div style="display:flex;align-items:center;gap:8px">
            <span class="count-label" id="allCount"></span>
            <button class="lang-toggle" id="allLang" onclick="toggleLang('all')"><span class="la">EN</span> | <span class="ld">AR</span></button>
          </div>
        </div>
        <div class="table-wrap">
          <table><thead><tr>
            <th>Tender No</th><th>Name</th><th>Entity</th><th>Category</th><th>Grade</th><th>Type</th><th>Bid Closing</th>
          </tr></thead><tbody id="allBody"></tbody></table>
        </div>
      </div>
    </div>
  </div>

  <!-- MARKET NEWS (collapsed) -->
  <div class="section">
    <div class="collapsible-header" onclick="toggle('news')">
      <span class="arrow" id="newsArrow">&#9654;</span>
      <h3>Market &amp; Infrastructure News ({len(relevant_news)})</h3>
    </div>
    <div class="collapsible-body" id="newsBody">
      <div class="collapsible-inner">
        <div class="news-grid">{news_cards}</div>
      </div>
    </div>
  </div>

</div>

<div class="footer">
  Data sourced from <a href="https://etendering.tenderboard.gov.om" target="_blank">etendering.tenderboard.gov.om</a> and Oman news RSS.
  Last refreshed: {ts}<br>
  Zavia-ai &copy; 2026
</div>

<script>
const SCC_ROWS={scc_json};
const ALL_VIEWS={all_json};
let currentView="{esc(first_view)}";
const lang={{scc:"en",all:"en"}};

function esc(s){{const d=document.createElement('div');d.textContent=s||'';return d.innerHTML;}}
function escA(s){{return(s||'').replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;');}}

function renderTable(rows,filter,tbody,countEl,langKey){{
  const f=filter.toLowerCase();
  const L=lang[langKey];
  tbody.innerHTML='';
  let n=0;
  for(const r of rows){{
    const s=[r.n,r.na,r.ne,r.ea,r.ee,r.ca,r.ce,r.ga,r.ge,r.ta,r.te,r.close].join(' ').toLowerCase();
    if(f&&s.indexOf(f)===-1)continue;
    n++;
    const nm=L==='en'?r.ne:r.na;
    const en=L==='en'?r.ee:r.ea;
    const ct=L==='en'?r.ce:r.ca;
    const gr=L==='en'?r.ge:r.ga;
    const tp=L==='en'?r.te:r.ta;
    const short=nm.length>80?nm.substring(0,80)+'...':nm;
    const tr=document.createElement('tr');
    if(r.rt)tr.classList.add('rt');
    tr.innerHTML='<td>'+esc(r.n)+'</td><td class="td-name" title="'+escA(nm)+'">'+esc(short)+'</td><td>'+esc(en)+'</td><td>'+esc(ct)+'</td><td>'+esc(gr)+'</td><td>'+esc(tp)+'</td><td>'+esc(r.close)+'</td>';
    tbody.appendChild(tr);
  }}
  countEl.textContent='Showing '+n+' of '+rows.length;
}}

function renderSCC(){{
  renderTable(SCC_ROWS,document.getElementById('sccFilter').value,document.getElementById('sccBody'),document.getElementById('sccCount'),'scc');
}}
function renderAll(){{
  const rows=ALL_VIEWS[currentView]||[];
  renderTable(rows,document.getElementById('allFilter').value,document.getElementById('allBody'),document.getElementById('allCount'),'all');
}}

function switchTab(v){{
  currentView=v;
  document.querySelectorAll('.tab-btn').forEach(b=>{{
    const bv=b.getAttribute('onclick').match(/'([^']+)'/)[1];
    b.classList.toggle('active',bv===v);
  }});
  renderAll();
}}

function toggleLang(key){{
  lang[key]=lang[key]==='en'?'ar':'en';
  const btn=document.getElementById(key+'Lang');
  if(lang[key]==='en')btn.innerHTML='<span class="la">EN</span> | <span class="ld">AR</span>';
  else btn.innerHTML='<span class="ld">EN</span> | <span class="la">AR</span>';
  if(key==='scc')renderSCC();else renderAll();
}}

function toggle(id){{
  const body=document.getElementById(id+'Body');
  const arrow=document.getElementById(id+'Arrow');
  const header=arrow.parentElement;
  body.classList.toggle('open');
  header.classList.toggle('open');
}}

renderSCC();
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
        pass


def main():
    print("Loading data...")
    tenders_raw = load_json_file("tenders.json")
    news_raw = load_json_file("news.json")
    briefing_md = load_file("briefing_output.md")
    tenders = extract_tenders(tenders_raw) if tenders_raw else []
    articles = extract_articles(news_raw) if news_raw else []
    print(f"  Tenders: {len(tenders)}, Articles: {len(articles)}, Briefing: {'yes' if briefing_md else 'no'}")

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
