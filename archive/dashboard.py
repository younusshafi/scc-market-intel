"""
SCC Market Intelligence Dashboard — premium product-grade interface.

Reads: tenders.json, historical_tenders.json, news.json, briefing_output.md,
       major_project_intelligence.json
Outputs: single self-contained HTML file with inline CSS/JS/SVG.
"""

import html
import http.server
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PORT = 8000

SCC_CAT_KW = ["Construction", "Ports", "Roads", "Bridges", "Pipeline",
              "Electromechanical", "Dams", "Marine", "مقاولات"]
SCC_GRADE_KW = ["Excellent", "First", "Second", "الممتازة", "الأولى", "الثانية"]
NEWS_KW = ["construction", "infrastructure", "tender", "contract", "project",
           "investment", "industrial", "roads", "bridges", "pipeline", "ministry",
           "budget", "economic", "zone", "development", "port", "airport",
           "housing", "railway", "dam", "water", "sewage",
           "galfar", "strabag", "al tasnim", "l&t", "towell", "hassan allam",
           "arab contractors", "ozkar", "sarooj", "mtcit", "opaz", "riyada"]
COMPETITORS = ["Galfar", "Strabag", "Al Tasnim", "L&T", "Towell",
               "Hassan Allam", "Arab Contractors", "Ozkar"]
PAGINATION_PW = ["الأولى", "السابقة", "التالية", "الأخيرة", "Previous", "Next", "Last"]

COMP_COLOURS = {
    "Sarooj": "#2563EB", "SCC": "#2563EB",
    "Galfar": "#DC2626", "Strabag": "#EA580C",
    "Al Tasnim": "#16A34A", "L&T": "#7C3AED",
    "Towell": "#0891B2", "Hassan Allam": "#CA8A04",
    "Arab Contractors": "#BE185D", "Ozkar": "#6B7280",
}

TRACKED_ALIASES = {
    "SAROOJ CONSTRUCTION COMPANY": "Sarooj",
    "Sarooj Construction Company": "Sarooj",
    "GALFAR ENGINEERING AND CONTRACTING": "Galfar",
    "STRABAG OMAN": "Strabag",
    "AL TASNIM ENTERPRISES": "Al Tasnim",
    "LARSEN AND TOUBRO (OMAN)": "L&T",
    "LARSEN AND TOUBRO": "L&T",
    "TOWELL CONSTRUCTION AND CO LLC": "Towell",
    "TOWELL INFRASTRUCTURE PROJECTS CO": "Towell",
    "HASSAN ALLAM CONSTRUCTION": "Hassan Allam",
    "Hassan Allam Construction": "Hassan Allam",
    "HASSAN ALLAM CONTRACTING AND CONSTRUCTION": "Hassan Allam",
    "THE ARAB CONTRACTORS OMAN LIMITED": "Arab Contractors",
    "The Arab Contractors Oman Limited": "Arab Contractors",
    "OZKAR": "Ozkar",
}

SOURCE_COLOURS = {
    "Times of Oman": "#2563EB",
    "Oman Observer": "#10B981",
    "Oman Construction": "#F59E0B",
    "Oman Infrastructure": "#7C3AED",
}


def load_file(name):
    p = os.path.join(SCRIPT_DIR, name)
    return open(p, "r", encoding="utf-8").read() if os.path.exists(p) else None

def load_json_file(name):
    t = load_file(name)
    return json.loads(t) if t else None

def extract_tenders(raw):
    if isinstance(raw, list): return raw
    if isinstance(raw, dict):
        for k in ("tenders", "views", "data", "results", "items"):
            if k in raw and isinstance(raw[k], list): return raw[k]
    return []

def extract_articles(raw):
    if isinstance(raw, list): return raw
    if isinstance(raw, dict):
        if "sources" in raw and isinstance(raw["sources"], dict):
            arts = []
            for sn, sd in raw["sources"].items():
                if isinstance(sd, dict) and "articles" in sd:
                    for a in sd["articles"]:
                        a.setdefault("source", sn)
                        arts.append(a)
                elif isinstance(sd, list):
                    for a in sd:
                        a.setdefault("source", sn)
                        arts.append(a)
            return arts
    return []

def esc(text): return html.escape(str(text))

def bi(t, field):
    return t.get(f"{field}_en") or t.get(f"{field}_ar") or t.get(field, "")

def is_pagination(t):
    for f in ("tender_number", "tender_name_ar", "tender_name_en", "tender_name"):
        if any(pw in t.get(f, "") for pw in PAGINATION_PW): return True
    return False

def is_scc(t):
    cg = (t.get("category_grade_ar", "") + " " + t.get("category_grade_en", "") +
          " " + t.get("category_grade", ""))
    return any(k in cg for k in SCC_CAT_KW) and any(k in cg for k in SCC_GRADE_KW)

def is_retender(t):
    n = t.get("tender_name_ar", "") + " " + t.get("tender_name_en", "") + " " + t.get("tender_name", "")
    return "اعادة طرح" in n or "إعادة طرح" in n or "recall" in n.lower()

def split_cg(cg):
    gm = re.search(r"\[([^\]]+)\]", cg)
    cm = re.match(r"^([^\[]+)", cg)
    return (cm.group(1).strip() if cm else cg), (gm.group(1) if gm else "")

def split_type(tt):
    m = re.match(r"^([^\[]+)", tt)
    return m.group(1).strip() if m else tt

def get_source_colour(src):
    for k, c in SOURCE_COLOURS.items():
        if k.lower() in src.lower(): return c
    if any(comp.lower() in src.lower() for comp in COMPETITORS): return "#EF4444"
    return "#64748B"

def tender_row(t):
    cg_ar = t.get("category_grade_ar", t.get("category_grade", ""))
    cg_en = t.get("category_grade_en", "")
    ca, ga = split_cg(cg_ar)
    ce, ge = split_cg(cg_en) if cg_en else ("", "")
    return {
        "n": t.get("tender_number", ""),
        "na": t.get("tender_name_ar", t.get("tender_name", "")),
        "ne": t.get("tender_name_en", "") or t.get("tender_name_ar", t.get("tender_name", "")),
        "ea": t.get("entity_ar", t.get("entity", "")),
        "ee": t.get("entity_en", "") or t.get("entity_ar", t.get("entity", "")),
        "ca": ca, "ce": ce or ca, "ga": ga, "ge": ge or ga,
        "ta": split_type(t.get("tender_type_ar", t.get("tender_type", ""))),
        "te": split_type(t.get("tender_type_en", "")) or split_type(t.get("tender_type_ar", t.get("tender_type", ""))),
        "close": t.get("bid_closing_date") or t.get("sales_end_date") or "",
        "rt": is_retender(t), "scc": is_scc(t),
    }

def sort_key_d(r):
    m = re.search(r"(\d{2})-(\d{2})-(\d{4})", r.get("close", ""))
    return f"{m.group(3)}{m.group(2)}{m.group(1)}" if m else "0"

def md_to_html(md):
    if not md: return "<p><em>No briefing available.</em></p>"
    lines = md.split("\n")
    out, in_list = [], False
    for line in lines:
        s = line.strip()
        if not s:
            if in_list: out.append("</ul>"); in_list = False
            continue
        if s.startswith("# "):
            if in_list: out.append("</ul>"); in_list = False
            out.append(f"<h2>{_inl(s[2:])}</h2>"); continue
        if s.startswith("## "):
            if in_list: out.append("</ul>"); in_list = False
            out.append(f"<h3>{_inl(s[3:])}</h3>"); continue
        m = re.match(r"^(\d+)\.\s+(.*)$", s)
        if m:
            if in_list: out.append("</ul>"); in_list = False
            out.append(f'<ol start="{m.group(1)}"><li>{_inl(m.group(2))}</li></ol>'); continue
        if s.startswith(("* ", "- ", "\t*")):
            c = re.sub(r"^[\t ]*[*\-]\s+", "", s)
            if not in_list: out.append("<ul>"); in_list = True
            out.append(f"<li>{_inl(c)}</li>"); continue
        if in_list: out.append("</ul>"); in_list = False
        out.append(f"<p>{_inl(s)}</p>")
    if in_list: out.append("</ul>")
    return "\n".join(out)

def _inl(t):
    t = esc(t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"\*(.+?)\*", r"<em>\1</em>", t)
    return t


def resolve_competitor(company_name):
    """Map a company name to a tracked competitor short name, or None."""
    if company_name in TRACKED_ALIASES:
        return TRACKED_ALIASES[company_name]
    low = company_name.lower()
    for alias, short in TRACKED_ALIASES.items():
        if alias.lower() in low or low in alias.lower():
            return short
    for comp in ["Sarooj", "Galfar", "Strabag", "Al Tasnim", "L&T", "Towell",
                 "Hassan Allam", "Arab Contractors", "Ozkar"]:
        if comp.lower() in low:
            return comp
    return None


def build_competitive_intel(intel_data):
    """Process major_project_intelligence.json into dashboard-ready structures."""
    if not intel_data:
        return [], [], [], []

    tenders = intel_data.get("tenders", [])

    # --- Major Project Cards (fee >= 200) ---
    major_projects = []
    for t in tenders:
        fee = t.get("fee", 0) or 0
        if fee < 200:
            continue

        bidders = t.get("bidders", [])
        purchasers = t.get("purchasers", [])
        nit = t.get("nit", {})

        # Map competitors
        comp_bids = {}  # short_name -> {value, status}
        comp_docs = {}  # short_name -> purchase_date
        for b in bidders:
            if b.get("offer_type") != "Main":
                continue
            name = resolve_competitor(b.get("company", ""))
            if name:
                val = b.get("quoted_value", "")
                try:
                    fval = float(val) if val else 0
                except (ValueError, TypeError):
                    fval = 0
                comp_bids[name] = {"value": fval, "status": b.get("status", "")}
        for p in purchasers:
            name = resolve_competitor(p.get("company", ""))
            if name:
                comp_docs[name] = p.get("purchase_date", "")

        # Merge into competitor presence list
        comp_presence = []
        all_comp_names = set(list(comp_bids.keys()) + list(comp_docs.keys()))
        for c in all_comp_names:
            role = "BID" if c in comp_bids else "DOCS"
            comp_presence.append({"name": c, "role": role,
                                  "value": comp_bids.get(c, {}).get("value", 0)})

        sarooj_present = "Sarooj" in all_comp_names
        num_bidders = len([b for b in bidders if b.get("offer_type") == "Main"])
        num_purchasers = len(purchasers)

        # Competition intensity
        if num_bidders >= 10:
            border_colour = "#EF4444"  # red — highly competitive
        elif num_bidders >= 5:
            border_colour = "#F59E0B"  # amber
        else:
            border_colour = "#10B981"  # green

        project_name = nit.get("title", "") or t.get("name", "")
        major_projects.append({
            "name": project_name,
            "entity": t.get("entity", ""),
            "fee": fee,
            "category": t.get("category", ""),
            "tender_number": t.get("tender_number_en") or t.get("tender_number", ""),
            "num_bidders": num_bidders,
            "num_purchasers": num_purchasers,
            "competitors": comp_presence,
            "sarooj_present": sarooj_present,
            "border_colour": border_colour,
            "view": t.get("view", ""),
        })

    major_projects.sort(key=lambda x: -x["fee"])

    # --- Head-to-Head: tenders where Sarooj bid AND competitors also bid ---
    head_to_head = []
    for t in tenders:
        bidders = t.get("bidders", [])
        nit = t.get("nit", {})
        sarooj_val = None
        comp_vals = []
        for b in bidders:
            if b.get("offer_type") != "Main":
                continue
            name = resolve_competitor(b.get("company", ""))
            val_str = b.get("quoted_value", "")
            try:
                val = float(val_str) if val_str else 0
            except (ValueError, TypeError):
                val = 0
            if name == "Sarooj" and val > 0:
                sarooj_val = val
            elif name and name != "Sarooj" and val > 0:
                comp_vals.append({"name": name, "value": val})
        if sarooj_val and comp_vals:
            rows = [{"name": "Sarooj (SCC)", "value": sarooj_val, "diff": 0, "diff_pct": 0, "is_scc": True}]
            for c in sorted(comp_vals, key=lambda x: x["value"]):
                diff = c["value"] - sarooj_val
                diff_pct = round(diff / sarooj_val * 100, 1)
                rows.append({"name": c["name"], "value": c["value"],
                             "diff": diff, "diff_pct": diff_pct, "is_scc": False})
            project_name = nit.get("title", "") or t.get("name", "")
            head_to_head.append({
                "project": project_name,
                "tender_number": t.get("tender_number_en") or t.get("tender_number", ""),
                "rows": rows,
            })

    # --- Live Competitive Tenders (multiple tracked competitors, may still be open) ---
    live_comp = []
    for t in tenders:
        bidders = t.get("bidders", [])
        purchasers = t.get("purchasers", [])
        nit = t.get("nit", {})
        if bidders:  # already has bids = not "live" in the pre-bid sense
            # Still include if it has many tracked competitors for interest
            pass

        tracked_in = []
        for p in purchasers:
            name = resolve_competitor(p.get("company", ""))
            if name:
                tracked_in.append({"name": name, "date": p.get("purchase_date", "")})
        if len(tracked_in) >= 2:
            project_name = nit.get("title", "") or t.get("name", "")
            live_comp.append({
                "project": project_name,
                "tender_number": t.get("tender_number_en") or t.get("tender_number", ""),
                "total_purchasers": len(purchasers),
                "tracked": tracked_in,
                "tracked_count": len(tracked_in),
                "has_bids": len(bidders) > 0,
                "dates": t.get("dates", ""),
            })
    live_comp.sort(key=lambda x: -x["tracked_count"])

    # --- Competitor Activity Summary ---
    activity = {}
    for comp in ["Sarooj", "Galfar", "Strabag", "Al Tasnim", "L&T", "Towell",
                 "Hassan Allam", "Arab Contractors", "Ozkar"]:
        activity[comp] = {"docs": 0, "bids": 0, "max_bid": 0}
    for t in tenders:
        bidders = t.get("bidders", [])
        purchasers = t.get("purchasers", [])
        seen_bid = set()
        seen_doc = set()
        for b in bidders:
            if b.get("offer_type") != "Main":
                continue
            name = resolve_competitor(b.get("company", ""))
            if name and name in activity and name not in seen_bid:
                seen_bid.add(name)
                activity[name]["bids"] += 1
                val_str = b.get("quoted_value", "")
                try:
                    val = float(val_str) if val_str else 0
                except (ValueError, TypeError):
                    val = 0
                if val > activity[name]["max_bid"]:
                    activity[name]["max_bid"] = val
        for p in purchasers:
            name = resolve_competitor(p.get("company", ""))
            if name and name in activity and name not in seen_doc:
                seen_doc.add(name)
                activity[name]["docs"] += 1

    activity_list = []
    for comp, d in activity.items():
        conv = round(d["bids"] / max(d["docs"], 1) * 100) if d["docs"] else 0
        activity_list.append({"name": comp, "docs": d["docs"], "bids": d["bids"],
                              "conv": conv, "max_bid": d["max_bid"]})
    activity_list.sort(key=lambda x: -(x["docs"] + x["bids"]))

    return major_projects, head_to_head, live_comp, activity_list


def build_trend_data(hist_tenders):
    """Build monthly trend data for SVG chart from historical data."""
    by_month = defaultdict(int)
    scc_month = defaultdict(int)
    entity_counts = defaultdict(int)
    for t in hist_tenders:
        for f in ("bid_closing_date", "sales_end_date", "date"):
            d = t.get(f, "")
            m = re.match(r"(\d{2})-(\d{2})-(\d{4})", d)
            if m:
                key = f"{m.group(3)}-{m.group(2)}"
                by_month[key] += 1
                if is_scc(t):
                    scc_month[key] += 1
                    entity_counts[bi(t, "entity") or "Unknown"] += 1
                break
    months = sorted(by_month.keys())[-6:]
    chart = [{"m": m, "all": by_month[m], "scc": scc_month.get(m, 0)} for m in months]
    top_entities = sorted(entity_counts.items(), key=lambda x: -x[1])[:8]
    return chart, top_entities


def build_cat_breakdown(tenders):
    """Category breakdown with SCC relevance flagging."""
    cats = defaultdict(int)
    for t in tenders:
        cg = bi(t, "category_grade")
        cm = re.match(r"^([^\[]+)", cg)
        c = cm.group(1).strip() if cm else cg
        if c and len(c) >= 3 and not c.isdigit():
            cats[c] += 1
    total = sum(cats.values()) or 1
    result = []
    for c, n in sorted(cats.items(), key=lambda x: -x[1]):
        is_scc_cat = any(k in c for k in SCC_CAT_KW)
        result.append({"name": c, "count": n, "pct": round(n/total*100, 1), "scc": is_scc_cat})
    return result


def build_html(tenders, articles, briefing_md, tenders_raw, hist_tenders, intel_data=None):
    today_str = datetime.now().strftime("%d %B %Y")
    now_str = datetime.now().strftime("%d %b %Y, %H:%M")
    tenders = [t for t in tenders if not is_pagination(t)]

    # Data prep
    scc_tenders = [t for t in tenders if is_scc(t)]
    scc_rows = sorted([tender_row(t) for t in scc_tenders], key=sort_key_d, reverse=True)
    rt_count = sum(1 for t in tenders if is_retender(t))
    views = {}
    for t in tenders:
        v = t.get("_view", "All")
        views.setdefault(v, []).append(t)
    all_views = {}
    for vn, vt in views.items():
        all_views[vn] = sorted([tender_row(t) for t in vt], key=sort_key_d, reverse=True)
    by_view = {vn: len(vt) for vn, vt in views.items()}

    # News
    seen = set()
    deduped = []
    for a in articles:
        title = a.get("title", "").strip().lower()
        if title and title not in seen:
            seen.add(title)
            deduped.append(a)
    relevant = [a for a in deduped if any(k in (a.get("title","")+" "+a.get("summary","")).lower() for k in NEWS_KW)]
    comp_news = [a for a in relevant if any(c.lower() in a.get("title","").lower() for c in COMPETITORS)]
    gen_news = [a for a in relevant if a not in comp_news]
    def art_sort(a):
        m = re.match(r"(\d{4}-\d{2}-\d{2})", a.get("published", ""))
        return m.group(1) if m else "0"
    comp_news.sort(key=art_sort, reverse=True)
    gen_news.sort(key=art_sort, reverse=True)
    all_news = comp_news + gen_news

    # Historical trends
    chart_data, top_entities = build_trend_data(hist_tenders) if hist_tenders else ([], [])
    cat_breakdown = build_cat_breakdown(tenders)

    # Competitive intelligence
    major_projects, head_to_head, live_comp, activity_list = build_competitive_intel(intel_data)

    # SVG chart (dark themed)
    if chart_data:
        max_val = max(d["all"] for d in chart_data) or 1
        bar_w = 60
        chart_w = len(chart_data) * (bar_w + 20) + 40
        chart_h = 200
        svg_bars = ""
        for i, d in enumerate(chart_data):
            x = 30 + i * (bar_w + 20)
            h_all = int(d["all"] / max_val * 160)
            h_scc = int(d["scc"] / max_val * 160)
            y_all = chart_h - 30 - h_all
            y_scc = chart_h - 30 - h_scc
            label = d["m"][5:] + "/" + d["m"][:4]
            svg_bars += f'<rect x="{x}" y="{y_all}" width="{bar_w//2-2}" height="{h_all}" fill="#334155" rx="3"/>\n'
            svg_bars += f'<rect x="{x+bar_w//2}" y="{y_scc}" width="{bar_w//2-2}" height="{h_scc}" fill="#3B82F6" rx="3"/>\n'
            svg_bars += f'<text x="{x+bar_w//2}" y="{chart_h-10}" text-anchor="middle" fill="#94A3B8" font-size="11">{label}</text>\n'
            svg_bars += f'<text x="{x+bar_w//4-1}" y="{y_all-4}" text-anchor="middle" fill="#94A3B8" font-size="10">{d["all"]}</text>\n'
            if d["scc"] > 0:
                svg_bars += f'<text x="{x+3*bar_w//4-1}" y="{y_scc-4}" text-anchor="middle" fill="#60A5FA" font-size="10">{d["scc"]}</text>\n'
        trend_svg = f'<svg viewBox="0 0 {chart_w} {chart_h}" style="width:100%;max-height:220px">{svg_bars}</svg>'
        trend_legend = '<div class="chart-legend"><span class="leg-dot" style="background:#334155"></span>All Tenders <span class="leg-dot" style="background:#3B82F6;margin-left:12px"></span>SCC-Relevant</div>'
    else:
        trend_svg = "<p class='muted'>No historical data available.</p>"
        trend_legend = ""

    # Category bars
    cat_max = cat_breakdown[0]["count"] if cat_breakdown else 1
    cat_html = ""
    for c in cat_breakdown[:10]:
        pct_w = max(int(c["count"] / cat_max * 100), 2)
        color = "#3B82F6" if c["scc"] else "#334155"
        cat_html += f'''<div class="bar-row"><span class="bar-label">{esc(c["name"][:40])}</span>
<div class="bar-track"><div class="bar-fill" style="width:{pct_w}%;background:{color}"><span>{c["count"]}</span></div></div>
<span class="bar-pct">{c["pct"]}%</span></div>\n'''

    # Entity list
    ent_max = top_entities[0][1] if top_entities else 1
    ent_html = ""
    for name, count in top_entities:
        pct_w = max(int(count / ent_max * 100), 5)
        ent_html += f'''<div class="bar-row"><span class="bar-label">{esc(name[:40])}</span>
<div class="bar-track"><div class="bar-fill" style="width:{pct_w}%;background:#3B82F6"><span>{count}</span></div></div></div>\n'''

    # --- Competitive Intelligence HTML ---
    ci_html = ""
    if major_projects or head_to_head or live_comp or activity_list:
        def comp_pill(name, role):
            colour = COMP_COLOURS.get(name, "#6B7280")
            if role == "BID":
                return f'<span class="comp-pill" style="background:{colour}">{esc(name)} · BID</span>'
            else:
                return f'<span class="comp-pill comp-pill-outline" style="border-color:{colour};color:{colour}">{esc(name)} · DOCS</span>'

        def fmt_omr(v):
            if v >= 1_000_000:
                return f"{v/1_000_000:.2f}M"
            if v >= 1_000:
                return f"{v/1_000:.0f}K"
            return f"{v:.0f}"

        # Sub-section 1: Major Project Tracker
        mp_cards = ""
        for p in major_projects:
            pills = " ".join(comp_pill(c["name"], c["role"]) for c in p["competitors"])
            highlight = ' style="background:rgba(37,99,235,.08)"' if p["sarooj_present"] else ""
            mp_cards += f'''<div class="proj-card" {highlight}>
<div class="proj-border" style="background:{p["border_colour"]}"></div>
<div class="proj-body">
<div class="proj-head-row"><h4 class="proj-name">{esc(p["name"][:90])}</h4><span class="proj-fee">{p["fee"]:.0f} OMR</span></div>
<div class="proj-meta"><span>{esc(p["entity"][:60])}</span></div>
<div class="proj-meta"><span class="proj-tag">{esc(p["category"][:50])}</span></div>
<div class="proj-meta"><strong>{p["num_purchasers"]}</strong> doc purchasers · <strong>{p["num_bidders"]}</strong> bidders</div>
<div class="proj-pills">{pills if pills else "<span class='muted'>No tracked competitors</span>"}</div>
</div></div>\n'''

        # Sub-section 2: Head-to-Head
        h2h_html = ""
        for h in head_to_head:
            h2h_html += f'<div class="h2h-block"><h4>{esc(h["project"][:80])}</h4><div class="table-wrap"><table class="h2h-table"><thead><tr><th>Company</th><th>Bid Value (OMR)</th><th>Difference from SCC</th></tr></thead><tbody>'
            for r in h["rows"]:
                cls = ' class="h2h-scc"' if r["is_scc"] else ""
                if r["is_scc"]:
                    diff_str = '<span style="color:#94A3B8">Baseline</span>'
                elif r["diff_pct"] >= 0:
                    diff_str = f'<span class="diff-lose">+{fmt_omr(r["diff"])} (+{r["diff_pct"]}%)</span>'
                else:
                    diff_str = f'<span class="diff-win">{fmt_omr(r["diff"])} ({r["diff_pct"]}%)</span>'
                h2h_html += f'<tr{cls}><td>{esc(r["name"])}</td><td class="val-cell">{fmt_omr(r["value"])} OMR</td><td>{diff_str}</td></tr>'
            h2h_html += '</tbody></table></div></div>\n'

        # Sub-section 3: Live Competitive Tenders
        live_html = ""
        for lc in live_comp[:10]:
            tracked_pills = " ".join(
                f'<span class="comp-pill" style="background:{COMP_COLOURS.get(c["name"], "#6B7280")}">{esc(c["name"])}</span>'
                for c in lc["tracked"]
            )
            tracked_dates = "".join(
                f'<div class="live-date"><span class="comp-dot" style="background:{COMP_COLOURS.get(c["name"], "#6B7280")}"></span>{esc(c["name"])}: {esc(c["date"])}</div>'
                for c in lc["tracked"]
            )
            status = "Bids received" if lc["has_bids"] else f'Closing: {lc["dates"]}' if lc["dates"] else "Open"
            live_html += f'''<div class="live-card"><div class="live-head-row"><h4>{esc(lc["project"][:80])}</h4><span class="live-pulse"><span class="pulse-dot"></span>LIVE</span></div>
<div class="live-meta"><span class="live-stat">{lc["tracked_count"]} of {len(COMPETITORS)+1} tracked competitors active</span> · {lc["total_purchasers"]} total purchasers · {status}</div>
<div class="proj-pills">{tracked_pills}</div>
<div class="live-dates">{tracked_dates}</div></div>\n'''

        # Sub-section 4: Competitor Activity Summary
        act_html = '<div class="table-wrap"><table class="act-table"><thead><tr><th>Competitor</th><th>Docs Purchased</th><th>Tenders Bid</th><th>Conversion</th><th>Largest Bid</th></tr></thead><tbody>'
        for a in activity_list:
            cls = ' class="h2h-scc"' if a["name"] == "Sarooj" else ""
            max_str = f'{fmt_omr(a["max_bid"])} OMR' if a["max_bid"] > 0 else '<span style="color:#64748B">--</span>'
            conv_color = "#10B981" if a["conv"] >= 50 else "#F59E0B" if a["conv"] >= 25 else "#64748B"
            act_html += f'<tr{cls}><td><span class="comp-dot" style="background:{COMP_COLOURS.get(a["name"], "#6B7280")}"></span>{esc(a["name"])}</td><td>{a["docs"]}</td><td>{a["bids"]}</td><td><span style="color:{conv_color};font-weight:600">{a["conv"]}%</span></td><td class="val-cell">{max_str}</td></tr>'
        act_html += '</tbody></table></div>'

        ci_html = f'''
<!-- Competitive Intelligence -->
<div class="card ci-section section-gap">
  <div class="card-head"><h3>Competitive Intelligence</h3><span class="badge-live"><span class="pulse-dot"></span>LIVE</span></div>

  <div class="ci-sub"><h4 class="ci-sub-head">Major Project Tracker</h4>
  <div class="proj-grid">{mp_cards}</div></div>

  <div class="ci-sub"><h4 class="ci-sub-head">Head-to-Head: SCC vs Competitors</h4>
  {h2h_html if h2h_html else "<p class='muted'>No head-to-head data available yet.</p>"}</div>

  <div class="ci-sub"><h4 class="ci-sub-head">Live Competitive Tenders</h4>
  {live_html if live_html else "<p class='muted'>No live competitive tenders.</p>"}</div>

  <div class="ci-sub"><h4 class="ci-sub-head">Competitor Activity Summary</h4>
  {act_html}</div>
</div>
'''

    # News cards
    news_html = ""
    for a in all_news[:50]:
        src = esc(a.get("source", ""))
        title = esc(a.get("title", ""))
        link = a.get("link", "#")
        pub = esc(a.get("published", "")[:10])
        summary = esc(a.get("summary", ""))[:160]
        colour = get_source_colour(src)
        is_comp = any(c.lower() in src.lower() for c in COMPETITORS)
        short_src = src
        for pfx in ["Oman Observer — ", "Google News — "]:
            if short_src.startswith(esc(pfx)): short_src = short_src[len(esc(pfx)):]; break
        if is_comp: short_src = "COMPETITOR · " + short_src
        news_html += f'''<div class="news-card"><div class="news-head"><span class="src-tag" style="background:{colour}">{short_src}</span><span class="news-date">{pub}</span></div>
<h4 class="news-title">{title}</h4><p class="news-sum">{summary}</p>
<a href="{esc(link)}" target="_blank" rel="noopener" class="news-link">Read &rarr;</a></div>\n'''

    # Tab buttons
    tab_btns = ""
    for i, vn in enumerate(all_views):
        act = " active" if i == 0 else ""
        tab_btns += f'<button class="tab-btn{act}" onclick="switchTab(\'{esc(vn)}\')">{esc(vn)} ({len(all_views[vn])})</button>'

    # Pipeline change arrow
    if len(chart_data) >= 2:
        prev, curr = chart_data[-2]["scc"], chart_data[-1]["scc"]
        if curr > prev: arrow_html = f'<span class="trend-up">↑ {curr-prev}</span>'
        elif curr < prev: arrow_html = f'<span class="trend-down">↓ {prev-curr}</span>'
        else: arrow_html = '<span class="trend-flat">→</span>'
    else:
        arrow_html = ""

    briefing_html = md_to_html(briefing_md)
    scc_json = json.dumps(scc_rows, ensure_ascii=False)
    all_json = json.dumps(all_views, ensure_ascii=False)
    first_view = list(all_views.keys())[0] if all_views else ""

    return f'''<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SCC Tender Intelligence</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
:root{{--bg:#0F172A;--surface:#1E293B;--surface-hover:#253348;--header:#020617;--text:#F8FAFC;--body:#E2E8F0;--secondary:#CBD5E1;--muted:#94A3B8;--dim:#64748B;--border:#334155;--blue:#3B82F6;--green:#10B981;--amber:#F59E0B;--red:#EF4444;--cyan:#06B6D4;--purple:#8B5CF6;--shadow:0 2px 8px rgba(0,0,0,.3),0 1px 3px rgba(0,0,0,.2);--shadow-lg:0 8px 24px rgba(0,0,0,.4);--r:12px}}
*{{margin:0;padding:0;box-sizing:border-box}}
html{{scroll-behavior:smooth}}
body{{font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif;background:var(--bg);color:var(--body);line-height:1.6;font-size:14px;-webkit-font-smoothing:antialiased;-moz-osx-font-smoothing:grayscale}}
a{{color:var(--blue);text-decoration:none}}a:hover{{text-decoration:underline;color:#60A5FA}}

/* Header */
.nav{{position:sticky;top:0;z-index:100;background:var(--header);border-bottom:1px solid var(--border);padding:14px 32px;display:flex;justify-content:space-between;align-items:center}}
.nav-brand{{display:flex;align-items:center;gap:10px}}
.nav-brand svg{{width:28px;height:28px}}
.nav-title{{font-size:18px;font-weight:700;color:var(--text);letter-spacing:-.3px}}
.nav-sub{{font-size:11px;color:var(--dim);margin-left:4px;font-weight:400}}
.nav-right{{font-size:12px;color:var(--dim)}}

.container{{max-width:1400px;margin:0 auto;padding:24px 32px}}
@media(max-width:768px){{.container{{padding:16px}}}}

/* Metric cards */
.metrics{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:24px}}
.metric{{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:20px 24px;transition:all .2s ease;position:relative;overflow:hidden}}
.metric::before{{content:'';position:absolute;left:0;top:0;bottom:0;width:4px}}
.metric:nth-child(1)::before{{background:var(--blue)}}
.metric:nth-child(2)::before{{background:var(--green)}}
.metric:nth-child(3)::before{{background:var(--amber)}}
.metric:nth-child(4)::before{{background:var(--purple)}}
.metric:hover{{background:var(--surface-hover);box-shadow:var(--shadow-lg)}}
.metric-val{{font-size:2.5rem;font-weight:800;color:var(--text);line-height:1.1;font-feature-settings:'tnum'}}
.metric-label{{font-size:11px;color:var(--muted);margin-top:6px;text-transform:uppercase;letter-spacing:.05em;font-weight:600}}
.metric-sub{{font-size:12px;color:var(--dim);margin-top:2px}}
.trend-up{{color:var(--green);font-weight:600;font-size:13px;margin-left:6px}}
.trend-down{{color:var(--red);font-weight:600;font-size:13px;margin-left:6px}}
.trend-flat{{color:var(--dim);font-size:13px;margin-left:6px}}
@media(max-width:900px){{.metrics{{grid-template-columns:repeat(2,1fr)}}}}
@media(max-width:500px){{.metrics{{grid-template-columns:1fr}}}}

/* Two-col */
.row2{{display:grid;grid-template-columns:3fr 2fr;gap:20px;margin-bottom:24px}}
.row2b{{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:24px}}
@media(max-width:900px){{.row2,.row2b{{grid-template-columns:1fr}}}}

/* Card */
.card{{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:24px;box-shadow:var(--shadow);transition:all .2s ease}}
.card:hover{{box-shadow:var(--shadow-lg)}}
.card-head{{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}}
.card h3{{font-size:13px;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}}
.badge{{font-size:10px;font-weight:600;background:rgba(6,182,212,.15);color:var(--cyan);padding:3px 10px;border-radius:20px;text-transform:uppercase;letter-spacing:.04em}}
.badge-count{{font-size:11px;font-weight:700;background:var(--blue);color:#fff;padding:3px 12px;border-radius:20px}}
.badge-live{{font-size:10px;font-weight:600;background:rgba(239,68,68,.15);color:var(--red);padding:3px 10px;border-radius:20px;text-transform:uppercase;letter-spacing:.04em;display:inline-flex;align-items:center;gap:6px}}

/* Briefing */
.briefing{{border-top:3px solid;border-image:linear-gradient(90deg,var(--blue),var(--purple)) 1}}
.briefing h2{{font-size:15px;color:var(--text);margin:14px 0 4px}}
.briefing h3{{font-size:14px;color:var(--blue);margin:10px 0 4px}}
.briefing p{{margin:5px 0;font-size:14px;line-height:1.7;color:var(--secondary)}}
.briefing ul,.briefing ol{{margin:5px 0 5px 20px;font-size:14px;color:var(--secondary)}}
.briefing li{{margin:3px 0}}
.briefing strong{{color:var(--text)}}
.gen-date{{font-size:11px;color:var(--dim);margin-top:12px}}

/* Chart */
.chart-legend{{display:flex;align-items:center;gap:4px;font-size:11px;color:var(--muted);margin-top:8px}}
.leg-dot{{display:inline-block;width:10px;height:10px;border-radius:2px}}

/* Bar rows */
.bar-row{{display:flex;align-items:center;gap:8px;margin:6px 0;font-size:12px}}
.bar-label{{min-width:140px;max-width:180px;color:var(--muted);text-align:right;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.bar-track{{flex:1;background:rgba(51,65,85,.5);border-radius:4px;height:22px;overflow:hidden}}
.bar-fill{{height:100%;border-radius:4px;display:flex;align-items:center;justify-content:flex-end;padding:0 8px;font-size:10px;font-weight:600;color:#fff;min-width:20px;transition:width .3s}}
.bar-pct{{font-size:11px;color:var(--muted);min-width:36px;text-align:right}}

/* Table */
.filter-bar{{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;gap:10px;flex-wrap:wrap}}
.search-wrap{{position:relative}}
.search-wrap svg{{position:absolute;left:10px;top:50%;transform:translateY(-50%);width:16px;height:16px;color:var(--dim)}}
.filter-input{{padding:8px 12px 8px 34px;border:1px solid var(--border);border-radius:8px;font-size:13px;width:300px;font-family:inherit;background:var(--bg);color:var(--body);transition:border .15s,box-shadow .15s}}
.filter-input:focus{{outline:none;border-color:var(--blue);box-shadow:0 0 0 3px rgba(59,130,246,.2)}}
.filter-input::placeholder{{color:var(--dim)}}
.pill-toggle{{display:inline-flex;border:1px solid var(--border);border-radius:20px;overflow:hidden;font-size:12px;font-weight:600}}
.pill-toggle button{{border:none;background:none;padding:5px 14px;cursor:pointer;font-family:inherit;font-size:12px;font-weight:600;color:var(--dim);transition:all .15s}}
.pill-toggle button.active{{background:var(--blue);color:#fff}}
.count-label{{font-size:12px;color:var(--muted)}}

.table-wrap{{overflow-x:auto;border-radius:var(--r);border:1px solid var(--border)}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th{{background:var(--bg);color:var(--muted);padding:10px 12px;text-align:left;font-weight:600;white-space:nowrap;cursor:pointer;user-select:none;position:sticky;top:0;font-size:11px;text-transform:uppercase;letter-spacing:.04em;border-bottom:1px solid var(--border)}}
th:hover{{color:var(--text)}}
th .sort-arrow{{font-size:10px;margin-left:4px;opacity:.4}}
td{{padding:9px 12px;border-bottom:1px solid rgba(51,65,85,.5);vertical-align:top;color:var(--body)}}
tr:nth-child(even) td{{background:rgba(15,23,42,.3)}}
tr:hover td{{background:rgba(59,130,246,.08)}}
tr.rt td{{background:rgba(245,158,11,.08);border-left:3px solid var(--amber)}}
.td-name{{max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.date-urgent{{color:var(--red);font-weight:600}}
.val-cell{{font-feature-settings:'tnum';text-align:right;font-weight:500}}
.pag{{display:flex;justify-content:center;gap:8px;padding:12px;font-size:13px}}
.pag button{{border:1px solid var(--border);background:var(--surface);color:var(--muted);border-radius:6px;padding:5px 14px;cursor:pointer;font-family:inherit;transition:all .15s}}
.pag button:hover{{background:var(--surface-hover);color:var(--text)}}
.pag button.active{{background:var(--blue);color:#fff;border-color:var(--blue)}}

/* Tabs */
.tabs{{display:flex;gap:4px;margin-bottom:12px;flex-wrap:wrap}}
.tab-btn{{padding:6px 16px;border:1px solid var(--border);border-radius:8px 8px 0 0;background:var(--surface);cursor:pointer;font-size:12px;font-weight:500;color:var(--dim);font-family:inherit;transition:all .15s}}
.tab-btn:hover{{background:var(--surface-hover);color:var(--muted)}}
.tab-btn.active{{background:var(--blue);color:#fff;border-color:var(--blue)}}

/* Collapsible */
.coll-head{{display:flex;align-items:center;gap:10px;cursor:pointer;padding:16px 24px;background:var(--surface);border:1px solid var(--border);border-radius:var(--r);box-shadow:var(--shadow);user-select:none;margin-bottom:16px;transition:all .2s ease}}
.coll-head:hover{{background:var(--surface-hover);box-shadow:var(--shadow-lg)}}
.coll-head h3{{font-size:13px;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}}
.coll-arrow{{font-size:11px;color:var(--dim);transition:transform .2s}}
.coll-head.open .coll-arrow{{transform:rotate(90deg)}}
.coll-body{{max-height:0;overflow:hidden;transition:max-height .3s ease}}
.coll-body.open{{max-height:none}}
.coll-inner{{padding:0 0 20px}}

/* News */
.news-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:14px}}
.news-card{{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:16px;display:flex;flex-direction:column;transition:all .2s ease}}
.news-card:hover{{background:var(--surface-hover);box-shadow:var(--shadow-lg);transform:translateY(-1px)}}
.news-head{{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px}}
.src-tag{{font-size:9px;font-weight:600;color:#fff;padding:2px 8px;border-radius:10px;text-transform:uppercase;letter-spacing:.03em}}
.news-date{{font-size:10px;color:var(--dim)}}
.news-title{{font-size:13px;font-weight:600;color:var(--text);margin-bottom:4px;line-height:1.4}}
.news-sum{{font-size:12px;color:var(--dim);flex:1;margin-bottom:6px;line-height:1.5}}
.news-link{{font-size:11px;font-weight:600;color:var(--blue)}}

.footer{{border-top:1px solid var(--border);padding:24px 32px;text-align:center;font-size:11px;color:var(--dim);margin-top:32px}}
.footer strong{{color:var(--muted)}}
.section-gap{{margin-bottom:24px}}

/* Competitive Intelligence */
.ci-section{{border-top:3px solid;border-image:linear-gradient(90deg,var(--red),var(--amber),var(--green)) 1}}
.ci-sub{{margin-bottom:28px}}
.ci-sub-head{{font-size:12px;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;margin-bottom:14px;padding-bottom:8px;border-bottom:1px solid var(--border)}}
.comp-pill{{display:inline-block;font-size:10px;font-weight:600;color:#fff;padding:2px 8px;border-radius:10px;margin:2px 3px 2px 0;white-space:nowrap;text-shadow:0 1px 2px rgba(0,0,0,.3)}}
.comp-pill-outline{{background:transparent !important;border:1.5px solid;text-shadow:none}}
.comp-dot{{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px;vertical-align:middle}}
.proj-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(400px,1fr));gap:14px}}
@media(max-width:768px){{.proj-grid{{grid-template-columns:1fr}}}}
.proj-card{{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);display:flex;overflow:hidden;transition:all .2s ease}}
.proj-card:hover{{transform:translateY(-2px);box-shadow:var(--shadow-lg);background:var(--surface-hover)}}
.proj-border{{width:4px;flex-shrink:0}}
.proj-body{{padding:14px 16px;flex:1}}
.proj-head-row{{display:flex;justify-content:space-between;align-items:flex-start;gap:8px;margin-bottom:4px}}
.proj-name{{font-size:13px;font-weight:600;color:var(--text);line-height:1.4;flex:1}}
.proj-fee{{font-size:13px;font-weight:700;color:var(--amber);white-space:nowrap}}
.proj-meta{{font-size:12px;color:var(--dim);margin-bottom:4px}}
.proj-meta strong{{color:var(--body)}}
.proj-tag{{background:rgba(51,65,85,.6);padding:1px 6px;border-radius:4px;font-size:11px;margin-right:4px;color:var(--muted)}}
.proj-pills{{margin-top:8px}}
.h2h-block{{margin-bottom:18px}}
.h2h-block h4{{font-size:13px;font-weight:600;color:var(--text);margin-bottom:8px}}
.h2h-table,.act-table{{width:100%;border-collapse:collapse;font-size:13px}}
.h2h-table td,.act-table td{{padding:10px 14px;border-bottom:1px solid rgba(51,65,85,.5);color:var(--body)}}
.h2h-scc td{{background:rgba(59,130,246,.1);font-weight:600;color:var(--text)}}
.diff-win{{color:var(--green);font-weight:600}}
.diff-lose{{color:var(--red);font-weight:500}}
.live-card{{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:16px 18px;margin-bottom:12px;transition:all .2s ease}}
.live-card:hover{{background:var(--surface-hover);box-shadow:var(--shadow-lg)}}
.live-head-row{{display:flex;justify-content:space-between;align-items:center;margin-bottom:4px}}
.live-card h4{{font-size:13px;font-weight:600;color:var(--text)}}
.live-meta{{font-size:12px;color:var(--dim);margin-bottom:8px}}
.live-stat{{color:var(--amber);font-weight:600}}
.live-dates{{display:flex;flex-wrap:wrap;gap:6px 16px;margin-top:8px;font-size:11px;color:var(--muted)}}
.live-date{{display:flex;align-items:center;gap:4px}}
.live-pulse{{display:inline-flex;align-items:center;gap:5px;font-size:10px;font-weight:700;color:var(--red);text-transform:uppercase;letter-spacing:.05em}}
.muted{{color:var(--dim);font-style:italic}}

/* Pulse animation */
@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.3}}}}
.pulse-dot{{width:7px;height:7px;border-radius:50%;background:var(--red);display:inline-block;animation:pulse 1.5s ease-in-out infinite}}
</style></head>
<body>

<div class="nav">
  <div class="nav-brand">
    <svg viewBox="0 0 28 28" fill="none"><rect width="28" height="28" rx="6" fill="#3B82F6"/><path d="M7 14h4l3-6 3 10 3-4h4" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
    <span class="nav-title">SCC Tender Intelligence</span>
  </div>
  <div class="nav-right">Last updated: {now_str}</div>
</div>

<div class="container">

<!-- Metrics -->
<div class="metrics">
  <div class="metric"><div class="metric-val">{len(tenders)}</div><div class="metric-label">Active Pipeline</div><div class="metric-sub">Floated + In-Process{arrow_html}</div></div>
  <div class="metric"><div class="metric-val">{len(scc_tenders)}</div><div class="metric-label">SCC Addressable</div><div class="metric-sub">{round(len(scc_tenders)/max(len(tenders),1)*100,1)}% of pipeline</div></div>
  <div class="metric"><div class="metric-val">{rt_count}</div><div class="metric-label">Re-Tenders</div><div class="metric-sub">In current dataset</div></div>
  <div class="metric"><div class="metric-val">{len(all_news)}</div><div class="metric-label">News Signals</div><div class="metric-sub">{len(comp_news)} competitor mentions</div></div>
</div>

<!-- Briefing + Trend -->
<div class="row2 section-gap">
  <div class="card briefing">
    <div class="card-head"><h3>AI Executive Briefing</h3><span class="badge">AI Generated</span></div>
    {briefing_html}
    <div class="gen-date">Generated {today_str}</div>
  </div>
  <div class="card">
    <div class="card-head"><h3>Tender Volume Trend</h3></div>
    {trend_svg}
    {trend_legend}
  </div>
</div>

{ci_html}

<!-- SCC-Relevant Tenders -->
<div class="card section-gap">
  <div class="card-head"><h3>SCC-Relevant Opportunities</h3><span class="badge-count">{len(scc_rows)}</span></div>
  <div class="filter-bar">
    <div class="search-wrap">
      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
      <input type="text" class="filter-input" id="sccFilter" placeholder="Search tenders..." oninput="renderSCC()">
    </div>
    <div style="display:flex;align-items:center;gap:10px">
      <span class="count-label" id="sccCount"></span>
      <div class="pill-toggle" id="sccLang"><button class="active" onclick="setLang('scc','en')">EN</button><button onclick="setLang('scc','ar')">AR</button></div>
    </div>
  </div>
  <div class="table-wrap"><table><thead><tr>
    <th onclick="sortSCC(0)">Tender No<span class="sort-arrow">⇅</span></th>
    <th onclick="sortSCC(1)">Name<span class="sort-arrow">⇅</span></th>
    <th onclick="sortSCC(2)">Entity<span class="sort-arrow">⇅</span></th>
    <th onclick="sortSCC(3)">Category<span class="sort-arrow">⇅</span></th>
    <th onclick="sortSCC(4)">Grade<span class="sort-arrow">⇅</span></th>
    <th onclick="sortSCC(5)">Type<span class="sort-arrow">⇅</span></th>
    <th onclick="sortSCC(6)">Bid Closing<span class="sort-arrow">⇅</span></th>
  </tr></thead><tbody id="sccBody"></tbody></table></div>
  <div class="pag" id="sccPag"></div>
</div>

<!-- Category + Entities -->
<div class="row2b section-gap">
  <div class="card"><div class="card-head"><h3>Market Composition</h3></div>{cat_html}</div>
  <div class="card"><div class="card-head"><h3>Top Issuing Entities</h3><span class="badge">SCC Categories</span></div>{ent_html}</div>
</div>

<!-- All Tenders (collapsed) -->
<div class="section-gap">
  <div class="coll-head" onclick="toggle('pipe')"><span class="coll-arrow" id="pipeArrow">&#9654;</span><h3>All Tenders ({len(tenders)})</h3></div>
  <div class="coll-body" id="pipeBody"><div class="coll-inner">
    <div class="tabs">{tab_btns}</div>
    <div class="filter-bar">
      <div class="search-wrap">
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
        <input type="text" class="filter-input" id="allFilter" placeholder="Search all tenders..." oninput="renderAll()">
      </div>
      <div style="display:flex;align-items:center;gap:10px">
        <span class="count-label" id="allCount"></span>
        <div class="pill-toggle" id="allLang"><button class="active" onclick="setLang('all','en')">EN</button><button onclick="setLang('all','ar')">AR</button></div>
      </div>
    </div>
    <div class="table-wrap"><table><thead><tr>
      <th>Tender No</th><th>Name</th><th>Entity</th><th>Category</th><th>Grade</th><th>Type</th><th>Bid Closing</th>
    </tr></thead><tbody id="allBody"></tbody></table></div>
    <div class="pag" id="allPag"></div>
  </div></div>
</div>

<!-- News (collapsed) -->
<div class="section-gap">
  <div class="coll-head" onclick="toggle('news')"><span class="coll-arrow" id="newsArrow">&#9654;</span><h3>Market &amp; Infrastructure News ({len(all_news)})</h3></div>
  <div class="coll-body" id="newsBody"><div class="coll-inner"><div class="news-grid">{news_html}</div></div></div>
</div>

</div>

<div class="footer">Data sourced from etendering.tenderboard.gov.om · Oman news RSS · Google News<br>Powered by <strong>Zavia-ai</strong> · Intelligence refresh: daily</div>

<script>
const SCC={scc_json};
const VIEWS={all_json};
let curView="{esc(first_view)}";
const lang={{scc:"en",all:"en"}};
const PAGE_SIZE=50;
const page={{scc:0,all:0}};
let sccSort={{col:-1,asc:true}};

function esc(s){{const d=document.createElement('div');d.textContent=s||'';return d.innerHTML}}
function escA(s){{return(s||'').replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;')}}

function isUrgent(d){{
  if(!d)return false;
  const m=d.match(/(\\d{{2}})-(\\d{{2}})-(\\d{{4}})/);
  if(!m)return false;
  const dt=new Date(+m[3],+m[2]-1,+m[1]);
  return(dt-new Date())<7*86400000&&(dt-new Date())>=0;
}}

function renderTable(rows,filter,tbody,countEl,pagEl,langKey,pageKey){{
  const f=filter.toLowerCase();
  const L=lang[langKey];
  const filtered=[];
  for(const r of rows){{
    const s=[r.n,r.na,r.ne,r.ea,r.ee,r.ca,r.ce,r.ga,r.ge,r.ta,r.te,r.close].join(' ').toLowerCase();
    if(!f||s.indexOf(f)!==-1)filtered.push(r);
  }}
  const total=filtered.length;
  const pages=Math.ceil(total/PAGE_SIZE);
  if(page[pageKey]>=pages)page[pageKey]=Math.max(0,pages-1);
  const start=page[pageKey]*PAGE_SIZE;
  const slice=filtered.slice(start,start+PAGE_SIZE);
  tbody.innerHTML='';
  for(const r of slice){{
    const nm=L==='en'?r.ne:r.na;
    const en=L==='en'?r.ee:r.ea;
    const ct=L==='en'?r.ce:r.ca;
    const gr=L==='en'?r.ge:r.ga;
    const tp=L==='en'?r.te:r.ta;
    const short=nm.length>70?nm.substring(0,70)+'...':nm;
    const tr=document.createElement('tr');
    if(r.rt)tr.classList.add('rt');
    const urgCls=isUrgent(r.close)?' date-urgent':'';
    tr.innerHTML='<td>'+esc(r.n)+'</td><td class="td-name" title="'+escA(nm)+'">'+esc(short)+'</td><td>'+esc(en)+'</td><td>'+esc(ct)+'</td><td>'+esc(gr)+'</td><td>'+esc(tp)+'</td><td class="'+urgCls+'">'+esc(r.close)+'</td>';
    tbody.appendChild(tr);
  }}
  countEl.textContent=total+' tenders'+(pages>1?' · page '+(page[pageKey]+1)+'/'+pages:'');
  pagEl.innerHTML='';
  if(pages>1){{
    const prev=document.createElement('button');prev.textContent='← Prev';prev.onclick=()=>{{if(page[pageKey]>0){{page[pageKey]--;if(pageKey==='scc')renderSCC();else renderAll();}}}};
    pagEl.appendChild(prev);
    for(let i=0;i<Math.min(pages,7);i++){{
      const b=document.createElement('button');b.textContent=i+1;if(i===page[pageKey])b.classList.add('active');
      b.onclick=(()=>{{const p=i;return()=>{{page[pageKey]=p;if(pageKey==='scc')renderSCC();else renderAll();}}}})();
      pagEl.appendChild(b);
    }}
    if(pages>7){{const sp=document.createElement('span');sp.textContent='...';pagEl.appendChild(sp)}}
    const next=document.createElement('button');next.textContent='Next →';next.onclick=()=>{{if(page[pageKey]<pages-1){{page[pageKey]++;if(pageKey==='scc')renderSCC();else renderAll();}}}};
    pagEl.appendChild(next);
  }}
}}

function renderSCC(){{page.scc=0;renderTable(SCC,document.getElementById('sccFilter').value,document.getElementById('sccBody'),document.getElementById('sccCount'),document.getElementById('sccPag'),'scc','scc')}}
function renderAll(){{page.all=0;const rows=VIEWS[curView]||[];renderTable(rows,document.getElementById('allFilter').value,document.getElementById('allBody'),document.getElementById('allCount'),document.getElementById('allPag'),'all','all')}}

function switchTab(v){{
  curView=v;
  document.querySelectorAll('.tab-btn').forEach(b=>{{const bv=b.getAttribute('onclick').match(/'([^']+)'/)[1];b.classList.toggle('active',bv===v)}});
  renderAll();
}}

function setLang(key,l){{
  lang[key]=l;
  const el=document.getElementById(key+'Lang');
  el.querySelectorAll('button').forEach(b=>b.classList.toggle('active',b.textContent.toLowerCase()===l));
  if(key==='scc')renderSCC();else renderAll();
}}

function sortSCC(col){{
  if(sccSort.col===col)sccSort.asc=!sccSort.asc;else{{sccSort.col=col;sccSort.asc=true}}
  const keys=['n','ne','ee','ce','ge','te','close'];
  const k=keys[col];
  SCC.sort((a,b)=>{{
    let va=a[k]||'',vb=b[k]||'';
    if(col===6){{const ma=va.match(/(\\d{{2}})-(\\d{{2}})-(\\d{{4}})/),mb=vb.match(/(\\d{{2}})-(\\d{{2}})-(\\d{{4}})/);if(ma)va=ma[3]+ma[2]+ma[1];if(mb)vb=mb[3]+mb[2]+mb[1]}}
    return sccSort.asc?va.localeCompare(vb):vb.localeCompare(va);
  }});
  renderSCC();
}}

function toggle(id){{
  const b=document.getElementById(id+'Body');
  const a=document.getElementById(id+'Arrow');
  b.classList.toggle('open');a.parentElement.classList.toggle('open');
  if(id==='pipe'&&b.classList.contains('open')&&!document.getElementById('allBody').children.length)renderAll();
}}

renderSCC();
</script></body></html>'''


class DashboardHandler(http.server.BaseHTTPRequestHandler):
    html_content = b""
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(self.html_content)))
        self.end_headers()
        self.wfile.write(self.html_content)
    def log_message(self, fmt, *args): pass

def main():
    print("Loading data...")
    tenders_raw = load_json_file("tenders.json")
    news_raw = load_json_file("news.json")
    hist_raw = load_json_file("historical_tenders.json")
    intel_raw = load_json_file("major_project_intelligence.json")
    briefing_md = load_file("briefing_output.md")
    tenders = extract_tenders(tenders_raw) if tenders_raw else []
    articles = extract_articles(news_raw) if news_raw else []
    hist = extract_tenders(hist_raw) if hist_raw else []
    print(f"  Tenders: {len(tenders)}, Historical: {len(hist)}, Articles: {len(articles)}, Briefing: {'yes' if briefing_md else 'no'}")
    print(f"  Intel projects: {len(intel_raw.get('tenders', [])) if intel_raw else 0}")

    html_str = build_html(tenders, articles, briefing_md, tenders_raw, hist, intel_data=intel_raw)
    DashboardHandler.html_content = html_str.encode("utf-8")
    print(f"  HTML: {len(DashboardHandler.html_content):,} bytes")

    server = http.server.HTTPServer(("", PORT), DashboardHandler)
    print(f"\nDashboard at http://localhost:{PORT} — Ctrl+C to stop")
    try: server.serve_forever()
    except KeyboardInterrupt: print("\nDone."); server.server_close()

if __name__ == "__main__": main()
