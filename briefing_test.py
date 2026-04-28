"""
Weekly executive briefing generator for Sarooj Construction Company (SCC).

Reads tenders.json + news.json, builds a context payload, sends it to
Groq's LLM API, and prints + saves the resulting briefing.
"""

import json
import os
import re
import sys
from datetime import datetime, timedelta

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv
import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(SCRIPT_DIR, ".env"))

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.3-70b-versatile"

# SCC profile
SCC_COMPETITORS = [
    "Galfar", "Strabag", "Al Tasnim", "L&T", "Towell",
    "Hassan Allam", "Arab Contractors", "Ozkar",
]
SCC_CATEGORIES = [
    "roads", "bridges", "tunnels", "marine works",
    "civil infrastructure", "dams", "pipelines",
]
SCC_GRADES = ["Excellent (الممتازة)", "First (الأولى)", "Second (الثانية)"]

# Arabic category keywords that match SCC's scope
SCC_CATEGORY_KEYWORDS = [
    "المقاولات العمرانيه",  # Construction & Maintenance
    "مقاولات المواني",       # Ports
    "الطرق",                # Roads
    "الجسور",               # Bridges
    "السدود",               # Dams
    "الانابيب",             # Pipelines
    "مقاولات الكهروميكانيكية",  # Electromechanical
    "مقاولات شبكات",        # Pipeline networks
]

SCC_GRADE_KEYWORDS = ["الممتازة", "الأولى", "الثانية"]

MAX_CONTEXT_WORDS = 3200  # ~7-8K tokens with Arabic text, leaving room for system + response

SYSTEM_PROMPT = (
    "You are a senior market intelligence analyst embedded in Sarooj "
    "Construction Company's tendering department. SCC is a major Omani civil "
    "infrastructure contractor — core work: roads, bridges, tunnels, marine "
    "works, dams, pipelines. Grades: Excellent and First.\n\n"
    "Write a weekly briefing for the Head of Tendering and CEO. They are "
    "experienced executives who already monitor the portal daily. Do not "
    "tell them what they already know. Tell them what they cannot easily "
    "see themselves.\n\n"
    "MARKET COMPOSITION (1 paragraph):\n"
    "Analyse the tender mix by category. What percentage of active tenders "
    "fall in SCC's core categories vs other categories? What does the "
    "current composition tell us about where government spending is going "
    "right now? Is SCC's addressable market growing or shrinking relative "
    "to total tender volume? Use specific numbers and percentages.\n\n"
    "PIPELINE OUTLOOK (1 paragraph):\n"
    "What tenders in SCC's core categories are worth watching? Filter "
    "ruthlessly — school maintenance and health centre repairs are not "
    "SCC's business even if they technically match a grade. Only highlight "
    "tenders that involve roads, bridges, tunnels, marine, dams, pipelines, "
    "or major civil infrastructure at a scale SCC would realistically bid. "
    "If nothing qualifies, say so clearly in one sentence and pivot to "
    "forward-looking signals: what upcoming projects from news sources "
    "might generate tenders in the next 3-6 months?\n\n"
    "RE-TENDER PATTERNS (1 paragraph):\n"
    "How many re-tenders exist in the current data? What categories are "
    "they concentrated in? Re-tender frequency is a market health indicator. "
    "Analyse what the pattern suggests — specification problems, pricing "
    "pressure, contractor supply issues? Only mention specific re-tenders "
    "if they are in SCC's core categories.\n\n"
    "COMPETITIVE & STRATEGIC SIGNALS (1 paragraph):\n"
    "Use the COMPETITIVE INTELLIGENCE data. Reference SCC's actual bids and "
    "head-to-head positioning versus competitors. Mention specific bid values "
    "and percentage differences. Highlight multi-competitor tenders like "
    "Sultan Haitham City where many tracked firms are active. Note Galfar's "
    "large bids and what they signal about market positioning. "
    "Any government policy, investment, or infrastructure announcements that "
    "signal future spending in SCC's categories? Connect the dots to SCC's "
    "business specifically. "
    "If recommending action, be concrete — 'watch for X' or 'prepare for Y' "
    "not 'may present opportunities.'\n\n"
    "FORMAT RULES:\n"
    "- 4 paragraphs with bold headers\n"
    "- Every paragraph must contain at least 2 specific numbers or percentages\n"
    "- Total: 300-400 words\n"
    "- Never say 'it is essential to continue monitoring'\n"
    "- Never say 'may have indirect implications'\n"
    "- Never say 'could lead to increased opportunities'\n"
    "- If a data gap limits your analysis, name the gap and recommend "
    "how to close it\n"
    "- Write as a strategist, not a reporter"
)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_json(filename):
    """Load a JSON file from the script directory. Returns None on failure."""
    path = os.path.join(SCRIPT_DIR, filename)
    if not os.path.exists(path):
        print(f"  WARNING: {filename} not found at {path}")
        return None
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"  Loaded {filename}: type={type(data).__name__}", end="")
    if isinstance(data, dict):
        print(f", keys={list(data.keys())}")
    elif isinstance(data, list):
        print(f", {len(data)} items")
    else:
        print()
    return data


def extract_tenders(raw):
    """Extract a flat list of tender dicts from whatever structure tenders.json has."""
    if isinstance(raw, list):
        return raw

    if isinstance(raw, dict):
        # Try known keys in priority order
        for key in ("tenders", "views", "data", "results", "items"):
            if key in raw and isinstance(raw[key], list):
                return raw[key]

        # Check for nested view dicts like {"New Tenders": [...], ...}
        merged = []
        for k, v in raw.items():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                for item in v:
                    item.setdefault("_view", k)
                merged.extend(v)
            elif isinstance(v, dict) and "tenders" in v:
                for item in v["tenders"]:
                    item.setdefault("_view", k)
                merged.extend(v["tenders"])
        if merged:
            return merged

    print("  WARNING: Could not find tender records in tenders.json")
    return []


def extract_articles(raw):
    """Extract a flat list of article dicts from whatever structure news.json has."""
    if isinstance(raw, list):
        return raw

    if isinstance(raw, dict):
        # Structure: {"sources": {"Source Name": {"articles": [...]}}}
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

        # Flat list under a key
        for key in ("articles", "items", "data", "results"):
            if key in raw and isinstance(raw[key], list):
                return raw[key]

    print("  WARNING: Could not find articles in news.json")
    return []


# ---------------------------------------------------------------------------
# Context building
# ---------------------------------------------------------------------------

def parse_date(date_str):
    """Try to parse various date formats into a datetime. Returns None on failure."""
    if not date_str:
        return None
    # Strip timezone info for simplicity
    date_str = re.sub(r"[+-]\d{2}:\d{2}$", "", date_str.strip())
    for fmt in (
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%a, %d %b %Y %H:%M:%S",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%a, %d %b %Y %H:%M:%S GMT",
    ):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def count_words(text):
    return len(text.split())


def bi(t, field):
    """Read a bilingual field: prefer English, fall back to Arabic, then unsuffixed."""
    return t.get(f"{field}_en") or t.get(f"{field}_ar") or t.get(field, "")


def build_tender_summary(tenders):
    """Build a statistical summary of tenders by category and grade."""
    by_category = {}
    by_grade = {}
    by_type = {}
    retenders = []

    for t in tenders:
        cat_grade = bi(t, "category_grade")
        tender_type = bi(t, "tender_type")
        name_ar = t.get("tender_name_ar", t.get("tender_name", ""))
        name_en = t.get("tender_name_en", "")

        # Count by category (extract the part before the bracket)
        cat_match = re.match(r"^([^\[]+)", cat_grade)
        cat = cat_match.group(1).strip() if cat_match else cat_grade
        if cat:
            by_category[cat] = by_category.get(cat, 0) + 1

        # Count by grade (extract from brackets)
        grade_match = re.search(r"\[([^\]]+)\]", cat_grade)
        if grade_match:
            for g in grade_match.group(1).split(","):
                g = g.strip()
                if g:
                    by_grade[g] = by_grade.get(g, 0) + 1

        # Count by type
        type_match = re.match(r"^([^\[]+)", tender_type)
        ttype = type_match.group(1).strip() if type_match else tender_type
        if ttype:
            by_type[ttype] = by_type.get(ttype, 0) + 1

        # Flag re-tenders (check both languages)
        all_names = name_ar + " " + name_en
        if "اعادة طرح" in all_names or "إعادة طرح" in all_names or "recall" in name_en.lower() or "re-tender" in name_en.lower():
            retenders.append(t)

    # Filter out junk entries (pagination artefacts like "of", "1", "42")
    def is_valid_key(k):
        return len(k) >= 3 and not k.isdigit()

    by_category = {k: v for k, v in by_category.items() if is_valid_key(k)}
    by_grade = {k: v for k, v in by_grade.items() if is_valid_key(k)}
    by_type = {k: v for k, v in by_type.items() if is_valid_key(k)}

    total = len(tenders) or 1  # avoid division by zero
    lines = []
    lines.append(f"TOTAL TENDERS LOADED: {total}")

    # Category breakdown with percentages
    lines.append("\nBy Procurement Category (count / % of total):")
    scc_core_count = 0
    scc_core_cats = set()
    for cat, count in sorted(by_category.items(), key=lambda x: -x[1]):
        pct = round(count / total * 100, 1)
        lines.append(f"  {cat}: {count} ({pct}%)")
        # Track SCC-relevant categories
        if any(kw in cat for kw in ["Construction", "Ports", "Roads", "Bridges",
                "Pipeline", "Electromechanical", "Dams", "Marine", "مقاولات"]):
            scc_core_count += count
            scc_core_cats.add(cat)

    non_scc = total - scc_core_count
    lines.append(f"\n  SCC CORE CATEGORIES TOTAL: {scc_core_count} ({round(scc_core_count/total*100, 1)}%)")
    lines.append(f"  OTHER CATEGORIES: {non_scc} ({round(non_scc/total*100, 1)}%)")

    # Grade distribution with percentages
    lines.append("\nBy Grade (% of tenders listing that grade):")
    for grade, count in sorted(by_grade.items(), key=lambda x: -x[1]):
        pct = round(count / total * 100, 1)
        lines.append(f"  {grade}: {count} ({pct}%)")

    # Type breakdown
    lines.append("\nBy Tender Type:")
    for ttype, count in sorted(by_type.items(), key=lambda x: -x[1]):
        pct = round(count / total * 100, 1)
        lines.append(f"  {ttype}: {count} ({pct}%)")

    # Re-tender analysis
    lines.append(f"\n=== RE-TENDER ANALYSIS ===")
    lines.append(f"Total re-tenders: {len(retenders)} out of {total} ({round(len(retenders)/total*100, 1)}%)")
    if retenders:
        # Group re-tenders by category
        rt_by_cat = {}
        for t in retenders:
            cg = bi(t, "category_grade")
            cm = re.match(r"^([^\[]+)", cg)
            cat = cm.group(1).strip() if cm else "Unknown"
            rt_by_cat.setdefault(cat, []).append(t)
        lines.append("Re-tenders by category:")
        for cat, rts in sorted(rt_by_cat.items(), key=lambda x: -len(x[1])):
            lines.append(f"  {cat}: {len(rts)}")
        lines.append("Re-tender details:")
        for t in retenders[:15]:
            num = t.get("tender_number", "?")
            name = t.get("tender_name_en") or t.get("tender_name_ar", "?")
            entity = t.get("entity_en") or t.get("entity_ar", "")
            cat = bi(t, "category_grade")[:40]
            lines.append(f"  {num} — {name[:50]} [{entity[:30]}] ({cat})")
    else:
        lines.append("No re-tenders found in current dataset.")

    return "\n".join(lines)


def format_tender_row(t):
    """Format a single tender as a compact text block."""
    parts = [
        t.get("tender_number", "?"),
        bi(t, "tender_name") or "?",
        bi(t, "entity"),
        bi(t, "category_grade"),
        bi(t, "tender_type"),
    ]
    date_info = ""
    if t.get("sales_end_date"):
        date_info += f"Sales End: {t['sales_end_date']}"
    if t.get("bid_closing_date"):
        date_info += f"  Bid Close: {t['bid_closing_date']}"
    if t.get("actual_opening_date"):
        date_info += f"  Opened: {t['actual_opening_date']}"
    if not date_info and t.get("dates"):
        date_info = t["dates"]
    if date_info:
        parts.append(date_info)

    fee = t.get("fee", "")
    if fee and fee != "N/A":
        parts.append(f"Fee: {fee}")
    guarantee = t.get("bank_guarantee", "")
    if guarantee and guarantee != "N/A":
        parts.append(f"Guarantee: {guarantee}")

    return " | ".join(p for p in parts if p)


def filter_recent_articles(articles, days=7):
    """Return articles from the last N days, sorted newest-first."""
    cutoff = datetime.now() - timedelta(days=days)
    recent = []
    undated = []

    for a in articles:
        pub = a.get("published")
        dt = parse_date(pub) if pub else None
        if dt:
            if dt >= cutoff:
                recent.append((dt, a))
        else:
            undated.append(a)

    recent.sort(key=lambda x: x[0], reverse=True)
    result = [a for _, a in recent]

    # Include a few undated articles (they're probably recent)
    result.extend(undated[:5])
    return result


def format_article(a):
    """Format a single news article as a compact text block."""
    parts = [
        a.get("title", "?"),
        a.get("source", ""),
        a.get("published", ""),
    ]
    summary = a.get("summary", "")
    if summary:
        parts.append(summary[:200])
    return " | ".join(p for p in parts if p)


def extract_date_ym(t):
    """Extract (yyyy, mm) from a tender's date fields."""
    for field in ("bid_closing_date", "sales_end_date", "date"):
        d = t.get(field, "")
        m = re.match(r"(\d{2})-(\d{2})-(\d{4})", d)
        if m:
            return int(m.group(3)), int(m.group(2))
    return None, None


def is_scc_relevant(t):
    """Check if a tender matches SCC's category + grade."""
    EN_CAT_KW = ["Construction", "Ports", "Roads", "Bridges", "Dams",
                  "Pipeline", "Electromechanical", "Marine"]
    EN_GRADE_KW = ["Excellent", "First", "Second"]
    cg_ar = t.get("category_grade_ar", t.get("category_grade", ""))
    cg_en = t.get("category_grade_en", "")
    cg = cg_ar + " " + cg_en
    cat_match = any(kw in cg for kw in SCC_CATEGORY_KEYWORDS + EN_CAT_KW)
    grade_match = any(kw in cg for kw in SCC_GRADE_KEYWORDS + EN_GRADE_KW)
    return cat_match and grade_match


def build_historical_trends(hist_tenders):
    """Build trend statistics from historical data (4,700+ tenders)."""
    from collections import defaultdict

    by_month = defaultdict(int)
    scc_by_month = defaultdict(int)
    rt_by_month = defaultdict(int)
    entity_counts = defaultdict(int)
    retenders = []

    for t in hist_tenders:
        yyyy, mm = extract_date_ym(t)
        if yyyy is None:
            continue
        key = f"{yyyy}-{mm:02d}"
        by_month[key] += 1

        if is_scc_relevant(t):
            scc_by_month[key] += 1
            entity = bi(t, "entity") or "Unknown"
            entity_counts[entity] += 1

        names = (t.get("tender_name_ar", "") + " " + t.get("tender_name_en", ""))
        if "اعادة طرح" in names or "إعادة طرح" in names or "recall" in names.lower():
            retenders.append(t)
            rt_by_month[key] += 1

    # Last 6 months
    all_months = sorted(by_month.keys())
    recent_months = all_months[-6:] if len(all_months) >= 6 else all_months

    lines = []
    lines.append(f"HISTORICAL DATA: {len(hist_tenders)} tenders spanning {all_months[0] if all_months else '?'} to {all_months[-1] if all_months else '?'}")

    lines.append("\nMonthly tender volume (last 6 months):")
    for m in recent_months:
        scc = scc_by_month.get(m, 0)
        rt = rt_by_month.get(m, 0)
        pct_scc = round(scc / max(by_month[m], 1) * 100, 1)
        rt_str = f", re-tenders: {rt}" if rt else ""
        lines.append(f"  {m}: {by_month[m]:>5} total, {scc:>4} SCC-relevant ({pct_scc}%){rt_str}")

    # SCC-relevant trend direction
    if len(recent_months) >= 2:
        first_half = sum(scc_by_month.get(m, 0) for m in recent_months[:3])
        second_half = sum(scc_by_month.get(m, 0) for m in recent_months[3:])
        if second_half > first_half:
            lines.append(f"  Trend: SCC-relevant tenders INCREASING ({first_half} -> {second_half} in last 3 vs prior 3 months)")
        elif second_half < first_half:
            lines.append(f"  Trend: SCC-relevant tenders DECREASING ({first_half} -> {second_half} in last 3 vs prior 3 months)")
        else:
            lines.append(f"  Trend: SCC-relevant tenders FLAT ({first_half} = {second_half})")

    # Top issuing entities for SCC categories
    lines.append("\nTop entities issuing SCC-relevant tenders:")
    for entity, count in sorted(entity_counts.items(), key=lambda x: -x[1])[:10]:
        lines.append(f"  {entity[:50]}: {count}")

    # Re-tender summary
    lines.append(f"\nRe-tenders in historical data: {len(retenders)} total")
    for t in retenders[:5]:
        num = t.get("tender_number", "?")
        name = t.get("tender_name_en") or t.get("tender_name_ar", "?")
        cat = bi(t, "category_grade")[:40]
        lines.append(f"  {num} — {name[:50]} ({cat})")

    return "\n".join(lines)


def build_competitive_intel_context(intel_data):
    """Build competitive intelligence context from major_project_intelligence.json."""
    if not intel_data:
        return ""

    TRACKED_ALIASES = {
        "SAROOJ CONSTRUCTION COMPANY": "Sarooj",
        "Sarooj Construction Company": "Sarooj",
        "GALFAR ENGINEERING AND CONTRACTING": "Galfar",
        "STRABAG OMAN": "Strabag",
        "AL TASNIM ENTERPRISES": "Al Tasnim",
        "LARSEN AND TOUBRO (OMAN)": "L&T",
        "TOWELL CONSTRUCTION AND CO LLC": "Towell",
        "TOWELL INFRASTRUCTURE PROJECTS CO": "Towell",
        "HASSAN ALLAM CONSTRUCTION": "Hassan Allam",
        "Hassan Allam Construction": "Hassan Allam",
        "HASSAN ALLAM CONTRACTING AND CONSTRUCTION": "Hassan Allam",
        "THE ARAB CONTRACTORS OMAN LIMITED": "Arab Contractors",
        "The Arab Contractors Oman Limited": "Arab Contractors",
    }

    def resolve(name):
        if name in TRACKED_ALIASES:
            return TRACKED_ALIASES[name]
        low = name.lower()
        for comp in SCC_COMPETITORS:
            if comp.lower() in low:
                return comp
        return None

    tenders = intel_data.get("tenders", [])
    lines = ["=== COMPETITIVE INTELLIGENCE ==="]

    # Find Sarooj's bids and head-to-head
    for t in tenders:
        bidders = t.get("bidders", [])
        nit = t.get("nit", {})
        sarooj_val = None
        comp_vals = []
        for b in bidders:
            if b.get("offer_type") != "Main":
                continue
            rn = resolve(b.get("company", ""))
            val_str = b.get("quoted_value", "")
            try:
                val = float(val_str) if val_str else 0
            except (ValueError, TypeError):
                val = 0
            if rn == "Sarooj" and val > 0:
                sarooj_val = val
            elif rn and rn != "Sarooj" and val > 0:
                comp_vals.append((rn, val))

        if sarooj_val:
            title = nit.get("title", "") or t.get("name", "")
            lines.append(f"\nSCC BID: {title}")
            lines.append(f"  Sarooj bid: OMR {sarooj_val:,.3f}")
            for cn, cv in sorted(comp_vals, key=lambda x: x[1]):
                diff_pct = round((cv - sarooj_val) / sarooj_val * 100, 1)
                lines.append(f"  {cn}: OMR {cv:,.3f} ({'+' if diff_pct >= 0 else ''}{diff_pct}% vs SCC)")

    # Find tenders with many tracked competitors (like Sultan Haitham City)
    lines.append("\nMULTI-COMPETITOR TENDERS:")
    for t in tenders:
        purchasers = t.get("purchasers", [])
        nit = t.get("nit", {})
        tracked = set()
        for p in purchasers:
            rn = resolve(p.get("company", ""))
            if rn:
                tracked.add(rn)
        if len(tracked) >= 3:
            title = nit.get("title", "") or t.get("name", "")
            lines.append(f"  {title}: {len(tracked)} tracked competitors ({', '.join(sorted(tracked))}), {len(purchasers)} total purchasers")

    # Largest competitor bids
    lines.append("\nLARGEST COMPETITOR BIDS:")
    big_bids = []
    for t in tenders:
        for b in t.get("bidders", []):
            if b.get("offer_type") != "Main":
                continue
            rn = resolve(b.get("company", ""))
            val_str = b.get("quoted_value", "")
            try:
                val = float(val_str) if val_str else 0
            except (ValueError, TypeError):
                val = 0
            if rn and val > 5_000_000:
                nit = t.get("nit", {})
                big_bids.append((rn, val, nit.get("title", "") or t.get("name", "")))
    big_bids.sort(key=lambda x: -x[1])
    for cn, cv, title in big_bids[:8]:
        lines.append(f"  {cn}: OMR {cv:,.3f} on {title[:60]}")

    return "\n".join(lines)


def build_context(tenders, articles, hist_tenders=None, intel_data=None):
    """Build the combined context string for the LLM, respecting the word budget."""
    sections = []

    # Section 1: SCC profile
    scc_profile = (
        "=== SCC COMPANY PROFILE ===\n"
        f"Work categories: {', '.join(SCC_CATEGORIES)}\n"
        f"Eligible grades: {', '.join(SCC_GRADES)}\n"
        f"Tracked competitors: {', '.join(SCC_COMPETITORS)}"
    )
    sections.append(scc_profile)

    # Section 2: Current tender statistics (from tenders.json)
    sections.append("=== CURRENT TENDER STATISTICS ===\n" + build_tender_summary(tenders))

    # Section 2b: Historical trends (from historical_tenders.json)
    if hist_tenders:
        sections.append("=== HISTORICAL TRENDS ===\n" + build_historical_trends(hist_tenders))

    # Section 2c: Competitive intelligence
    if intel_data:
        ci_ctx = build_competitive_intel_context(intel_data)
        if ci_ctx:
            sections.append(ci_ctx)

    # Section 2d: Field definitions
    sections.append(
        "=== FIELD DEFINITIONS ===\n"
        "- Fee: Tender DOCUMENT PURCHASE fee, NOT project value. 25-50 OMR is standard.\n"
        "- Guarantee: Bank guarantee PERCENTAGE, not absolute amount. 1 means 1%.\n"
        "- Do not comment on fees or guarantees as indicators of project size."
    )

    # Section 3: SCC-relevant tenders (from recent tenders.json — actionable)
    relevant = [t for t in tenders if is_scc_relevant(t)]

    if relevant:
        lines = [f"=== SCC-RELEVANT TENDERS ({len(relevant)} matching category + grade) ==="]
        for t in relevant[:15]:
            lines.append(format_tender_row(t))
        if len(relevant) > 15:
            lines.append(f"... and {len(relevant) - 15} more matching tenders")
        sections.append("\n".join(lines))

    # Section 4: Recent news — competitor news first, then general
    recent_articles = filter_recent_articles(articles, days=7)

    # Split into competitor news and general news
    competitor_articles = []
    general_articles = []
    for a in recent_articles:
        title = a.get("title", "").lower()
        if any(comp.lower() in title for comp in SCC_COMPETITORS):
            competitor_articles.append(a)
        else:
            general_articles.append(a)

    # Build news section — competitors first
    news_lines = []
    if competitor_articles:
        news_lines.append(f"=== COMPETITOR NEWS ({len(competitor_articles)} articles) ===")
        for a in competitor_articles[:15]:
            news_lines.append(format_article(a))

    current_text = "\n\n".join(sections) + "\n\n" + "\n".join(news_lines)
    budget_remaining = MAX_CONTEXT_WORDS - count_words(current_text) - 100

    news_lines.append(f"\n=== GENERAL MARKET NEWS ({len(general_articles)} articles) ===")
    for a in general_articles:
        line = format_article(a)
        line_words = count_words(line)
        if budget_remaining - line_words < 0:
            news_lines.append(f"... truncated ({len(general_articles)} total)")
            break
        news_lines.append(line)
        budget_remaining -= line_words

    sections.append("\n".join(news_lines))

    context = "\n\n".join(sections)
    wc = count_words(context)
    print(f"  Context built: {wc:,} words, {len(context):,} chars")
    return context


# ---------------------------------------------------------------------------
# Groq API
# ---------------------------------------------------------------------------

def call_groq(context):
    """Send the context to Groq's chat completions API and return the response text."""
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": context},
        ],
        "temperature": 0.4,
        "max_tokens": 2048,
    }

    print(f"\n  Calling Groq API ({MODEL})...")
    r = requests.post(GROQ_URL, headers=headers, json=payload, timeout=60)

    if r.status_code != 200:
        print(f"  ERROR: Groq API returned {r.status_code}")
        print(f"  Response: {r.text[:500]}")
        return None

    data = r.json()

    # Extract the assistant's message
    choices = data.get("choices", [])
    if not choices:
        print(f"  ERROR: No choices in response. Full response: {json.dumps(data)[:500]}")
        return None

    message = choices[0].get("message", {}).get("content", "")

    # Print usage stats
    usage = data.get("usage", {})
    if usage:
        print(f"  Tokens — prompt: {usage.get('prompt_tokens', '?')}, "
              f"completion: {usage.get('completion_tokens', '?')}, "
              f"total: {usage.get('total_tokens', '?')}")

    return message


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 70)
    print("SCC Weekly Briefing Generator")
    print("=" * 70)

    # Validate API key
    if not GROQ_API_KEY or GROQ_API_KEY in ("your_key_here", "YOUR_KEY_HERE", ""):
        print("\n  ERROR: Please add your Groq API key to .env file.")
        print("  Get one free at console.groq.com")
        sys.exit(1)

    print(f"  API key loaded: {GROQ_API_KEY[:8]}...{GROQ_API_KEY[-4:]}")

    # Load data
    print("\nLoading data...")
    tenders_raw = load_json("tenders.json")
    news_raw = load_json("news.json")
    hist_raw = load_json("historical_tenders.json")
    intel_raw = load_json("major_project_intelligence.json")

    if tenders_raw is None and news_raw is None:
        print("\n  ERROR: Neither tenders.json nor news.json found. Nothing to brief on.")
        sys.exit(1)

    # Extract records
    tenders = extract_tenders(tenders_raw) if tenders_raw else []
    hist_tenders = extract_tenders(hist_raw) if hist_raw else []
    articles_raw = extract_articles(news_raw) if news_raw else []
    total_articles = len(articles_raw)
    print(f"\n  Historical tenders: {len(hist_tenders)}")

    # Deduplicate articles by title
    seen_titles = set()
    articles_dedup = []
    for a in articles_raw:
        title = a.get("title", "").strip().lower()
        if title and title not in seen_titles:
            seen_titles.add(title)
            articles_dedup.append(a)
    dedup_count = len(articles_dedup)

    # Filter for relevance
    NEWS_KEYWORDS = [
        "construction", "infrastructure", "tender", "contract", "project",
        "investment", "industrial", "roads", "bridges", "pipeline", "ministry",
        "budget", "economic", "zone", "development", "port", "airport",
        "housing", "railway", "dam", "water", "sewage",
        "galfar", "strabag", "al tasnim", "l&t", "towell", "hassan allam",
        "arab contractors", "ozkar", "sarooj", "mtcit", "opaz", "riyada",
    ]
    articles = []
    for a in articles_dedup:
        text = (a.get("title", "") + " " + a.get("summary", "")).lower()
        if any(kw in text for kw in NEWS_KEYWORDS):
            articles.append(a)

    print(f"\n  Tenders extracted: {len(tenders)}")
    print(f"  News: {total_articles} total -> {dedup_count} after dedup -> {len(articles)} after relevance filter")

    if not tenders and not articles:
        print("\n  ERROR: No data extracted from either file.")
        sys.exit(1)

    # Build context
    print("\nBuilding context...")
    context = build_context(tenders, articles, hist_tenders=hist_tenders, intel_data=intel_raw)

    # Save context for inspection
    context_path = os.path.join(SCRIPT_DIR, "briefing_context.txt")
    with open(context_path, "w", encoding="utf-8") as f:
        f.write(context)
    print(f"  Saved context to briefing_context.txt")
    print(f"  Word count: {count_words(context):,}")
    print(f"  Char count: {len(context):,}")

    # Print first 200 lines
    print(f"\n{'='*70}")
    print("CONTEXT PREVIEW (first 200 lines)")
    print(f"{'='*70}")
    for i, line in enumerate(context.split("\n")[:200]):
        print(f"  {line}")
    print(f"  ... ({len(context.split(chr(10)))} total lines)")

    # Call Groq
    briefing = call_groq(context)
    if not briefing:
        print("\n  Failed to generate briefing.")
        sys.exit(1)

    # Print briefing
    print(f"\n{'='*70}")
    print("EXECUTIVE BRIEFING")
    print(f"{'='*70}\n")
    print(briefing)

    # Save to file
    output_path = os.path.join(SCRIPT_DIR, "briefing_output.md")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"# SCC Weekly Tendering Briefing\n\n")
        f.write(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n\n")
        f.write(briefing)
        f.write("\n")
    print(f"\n  Saved to {output_path}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
