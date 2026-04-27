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
    "Construction Company's Tendering department. SCC is a major Omani civil "
    "infrastructure contractor — their core work is roads, bridges, tunnels, "
    "marine works, dams, and pipelines. They hold Excellent and First grade "
    "classifications.\n\n"
    "Write a weekly briefing for the Head of Tendering. He is experienced, "
    "sharp, and has no patience for filler. He wants to know:\n\n"
    "PIPELINE SIGNAL: Are there meaningful new tenders in SCC's core "
    "categories this week? Do not list every grade match — filter for "
    "relevance. Maintenance contracts for health centre toilets are not "
    "SCC's business even if they technically match a grade. Focus on civil "
    "infrastructure scale work. If there is nothing significant, say so "
    "plainly and explain what the current tender mix looks like.\n\n"
    "RE-TENDER INTELLIGENCE: Any re-tenders? A re-tender means something "
    "went wrong the first time — that is a signal. Speculate briefly on "
    "what it might mean (too few bidders? pricing issues? scope changes?).\n\n"
    "COMPETITOR WATCH: Any news mentions of Galfar, Strabag, Al Tasnim, "
    "L&T, Towell, Hassan Allam, Arab Contractors, or Ozkar? If nothing, "
    "say so in one line and move on. Do not pad.\n\n"
    "MARKET CONTEXT: Any government spending signals, ministry "
    "announcements, or policy news that could affect SCC's pipeline in "
    "the next 3-6 months? Connect the dots — do not just restate "
    "headlines.\n\n"
    "Format: 4 short paragraphs with bold headers, no bullet point lists. "
    "Write like a trusted advisor speaking to a peer, not like a report "
    "generator. Total length: 250-350 words maximum."
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


def build_tender_summary(tenders):
    """Build a statistical summary of tenders by category and grade."""
    by_category = {}
    by_grade = {}
    by_type = {}
    retenders = []

    for t in tenders:
        cat_grade = t.get("category_grade", "")
        tender_type = t.get("tender_type", "")
        name = t.get("tender_name", "")
        view = t.get("_view", "")

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

        # Flag re-tenders
        if "اعادة طرح" in name or "إعادة طرح" in name or "re-tender" in name.lower():
            retenders.append(t)

    lines = []
    lines.append(f"TOTAL TENDERS LOADED: {len(tenders)}")

    lines.append("\nBy Procurement Category:")
    for cat, count in sorted(by_category.items(), key=lambda x: -x[1]):
        lines.append(f"  {cat}: {count}")

    lines.append("\nBy Grade:")
    for grade, count in sorted(by_grade.items(), key=lambda x: -x[1]):
        lines.append(f"  {grade}: {count}")

    lines.append("\nBy Tender Type:")
    for ttype, count in sorted(by_type.items(), key=lambda x: -x[1]):
        lines.append(f"  {ttype}: {count}")

    if retenders:
        lines.append(f"\nRE-TENDERS DETECTED ({len(retenders)}):")
        for t in retenders[:10]:
            lines.append(f"  {t.get('tender_number', '?')} — {t.get('tender_name', '?')[:60]}")

    return "\n".join(lines)


def format_tender_row(t):
    """Format a single tender as a compact text block."""
    parts = [
        t.get("tender_number", "?"),
        t.get("tender_name", "?"),
        t.get("entity", ""),
        t.get("category_grade", ""),
        t.get("tender_type", ""),
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


def build_context(tenders, articles):
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

    # Section 2: Tender statistics
    sections.append("=== TENDER STATISTICS ===\n" + build_tender_summary(tenders))

    # Section 3: SCC-relevant tenders (matching categories/grades)
    relevant = []
    for t in tenders:
        cg = t.get("category_grade", "")
        if any(kw in cg for kw in SCC_CATEGORY_KEYWORDS):
            if any(g in cg for g in SCC_GRADE_KEYWORDS):
                relevant.append(t)

    if relevant:
        lines = [f"=== SCC-RELEVANT TENDERS ({len(relevant)} matching category + grade) ==="]
        for t in relevant[:15]:
            lines.append(format_tender_row(t))
        if len(relevant) > 15:
            lines.append(f"... and {len(relevant) - 15} more matching tenders")
        sections.append("\n".join(lines))

    # Section 4: 20 most recent tenders (by view order — NewTenders come first)
    new_tenders = [t for t in tenders if t.get("_view") == "New/Floated Tenders"]
    recent_20 = new_tenders[:15] if new_tenders else tenders[:15]
    lines = ["=== 15 MOST RECENT NEW TENDERS ==="]
    for t in recent_20:
        lines.append(format_tender_row(t))
    sections.append("\n".join(lines))

    # Section 5: Recent news — add articles until we approach the word limit
    recent_articles = filter_recent_articles(articles, days=7)
    news_lines = [f"=== NEWS (last 7 days, {len(recent_articles)} articles) ==="]

    # Estimate current word count
    current_text = "\n\n".join(sections) + "\n\n" + news_lines[0]
    budget_remaining = MAX_CONTEXT_WORDS - count_words(current_text) - 100  # safety margin

    for a in recent_articles:
        line = format_article(a)
        line_words = count_words(line)
        if budget_remaining - line_words < 0:
            news_lines.append(f"... truncated ({len(recent_articles)} total articles)")
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

    if tenders_raw is None and news_raw is None:
        print("\n  ERROR: Neither tenders.json nor news.json found. Nothing to brief on.")
        sys.exit(1)

    # Extract records
    tenders = extract_tenders(tenders_raw) if tenders_raw else []
    articles = extract_articles(news_raw) if news_raw else []
    print(f"\n  Tenders extracted: {len(tenders)}")
    print(f"  Articles extracted: {len(articles)}")

    if not tenders and not articles:
        print("\n  ERROR: No data extracted from either file.")
        sys.exit(1)

    # Build context
    print("\nBuilding context...")
    context = build_context(tenders, articles)

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
