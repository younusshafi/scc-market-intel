"""Galfar MSX Financial + News Intelligence Scraper.

Fetches financial data AND strategic intelligence for Galfar Engineering &
Contracting (GECS) from the Muscat Securities Exchange (MSX) and Galfar's own
website. No third-party sites, no headless browsers.

Data sources:
  1. snapshot.aspx/company              — live share price, volume
  2. HTML page                           — issued shares → market cap
  3. Companies-Fin-Pref.aspx/List        — latest quarterly net profit
  4. snapshot.aspx/FinancialsReports     — ZIP → Income Statement PDF (revenue/EPS)
     └─ also parses CompanyReport + ManagementDiscussion PDFs for narrative
  5. company-news.aspx                   — MSX "Tender Award" announcements (PDF)
  6. galfar.com WordPress REST API       — press release contract wins

Usage:
    cd backend
    python -m app.scrapers.galfar_msx_scraper
    python -m app.jobs.scrape_galfar
"""

import io
import json
import logging
import re
import time
import zipfile
from datetime import datetime, date
from pathlib import Path

import pdfplumber
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://www.msx.om"
SNAPSHOT_URL = f"{BASE_URL}/snapshot.aspx?s=GECS"
GALFAR_WP_API = "https://galfar.com/oman/galfar/wp-json/wp/v2/posts"
TIMEOUT = 30
PDF_TIMEOUT = 20

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": SNAPSHOT_URL,
}

_JSON_HEADERS = {
    **_BROWSER_HEADERS,
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Content-Type": "application/json; charset=utf-8",
    "X-Requested-With": "XMLHttpRequest",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_omr(text: str) -> float | None:
    """Parse a number from text, handling commas and (negative) parentheses."""
    if not text:
        return None
    text = str(text).strip()
    negative = text.startswith("(") and text.endswith(")")
    cleaned = re.sub(r"[^\d.]", "", text)
    try:
        val = float(cleaned)
        return -val if negative else val
    except (ValueError, TypeError):
        return None


def _extract_omr_value(text: str) -> float | None:
    """Extract the first OMR/RO monetary value from free text, returned in OMR.

    Handles:
      "OMR 8.8 million"   → 8_800_000
      "RO117mn"           → 117_000_000
      "RO 35 million"     → 35_000_000
      "$28.5m (OMR 11m)"  → 11_000_000 (prefers explicit OMR)
    """
    patterns = [
        (r"(?:OMR|RO)\s*([\d,]+\.?\d*)\s*(?:million|mn|m\b)", 1_000_000),
        (r"(?:OMR|RO)\s*([\d,]+\.?\d*)\s*(?:billion|bn)", 1_000_000_000),
        (r"([\d,]+\.?\d*)\s*(?:million|mn)\s*(?:OMR|RO)", 1_000_000),
    ]
    for pattern, mult in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            val = _parse_omr(m.group(1))
            if val is not None:
                return val * mult
    return None


def _post_json(endpoint: str, payload: dict) -> list | dict | None:
    """POST to an MSX WebMethod, return the 'd' value or None on failure."""
    try:
        resp = requests.post(
            f"{BASE_URL}/{endpoint}",
            data=json.dumps(payload),
            headers=_JSON_HEADERS,
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json().get("d")
    except Exception as exc:
        logger.warning("POST %s failed: %s", endpoint, exc)
        return None


def _pdf_text(pdf_bytes: bytes) -> str:
    """Extract all text from a PDF. Returns empty string for image-based PDFs."""
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            return "\n".join(p.extract_text() or "" for p in pdf.pages)
    except Exception as exc:
        logger.debug("pdfplumber error: %s", exc)
        return ""


def _strip_html(html: str) -> str:
    """Remove HTML tags and decode entities."""
    return re.sub(r"\s+", " ", BeautifulSoup(html, "html.parser").get_text()).strip()


# ---------------------------------------------------------------------------
# Source 1 + 2: Live market data
# ---------------------------------------------------------------------------

def scrape_market_data() -> dict:
    """Live share price, volume, and calculated market cap for GECS."""
    logger.info("Fetching market data from snapshot.aspx/company")
    rows = _post_json("snapshot.aspx/company", {"Symbol": "GECS"})
    if not rows:
        return {}

    row = rows[0]
    issued_shares = _scrape_issued_shares()
    share_price = _parse_omr(row.get("LTP", ""))
    market_cap = (share_price * issued_shares) if (share_price and issued_shares) else None

    return {
        "share_price_omr": share_price,
        "prev_close_omr": _parse_omr(row.get("PrevClose", "")),
        "open_omr": _parse_omr(row.get("OpenPrice", "")),
        "daily_high_omr": _parse_omr(row.get("High", "")),
        "daily_low_omr": _parse_omr(row.get("Low", "")),
        "bid_price_omr": _parse_omr(row.get("BidPrice", "")) or None,
        "ask_price_omr": _parse_omr(row.get("AskPrice", "")) or None,
        "volume": _parse_omr(row.get("Volume", "").replace(",", "")),
        "turnover_omr": _parse_omr(row.get("Turnover", "").replace(",", "")),
        "issued_shares": issued_shares,
        "market_cap_omr": market_cap,
    }


def _scrape_issued_shares() -> float | None:
    try:
        resp = requests.get(SNAPSHOT_URL, headers=_BROWSER_HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        span = soup.find(id="ctl00_ContentPlaceHolder1_IssuedSharesLabel1")
        if span:
            return _parse_omr(span.get_text(strip=True))
    except Exception as exc:
        logger.warning("Issued shares fetch failed: %s", exc)
    return None


# ---------------------------------------------------------------------------
# Source 3: Quarterly net profit
# ---------------------------------------------------------------------------

def scrape_quarterly_performance() -> dict:
    """Latest quarterly net profit from Companies-Fin-Pref.aspx/List."""
    logger.info("Fetching quarterly performance")
    rows = _post_json("Companies-Fin-Pref.aspx/List", {})
    if not rows:
        return {}

    gecs = next((r for r in rows if r.get("Symbol") == "GECS"), None)
    if not gecs:
        logger.warning("GECS not found in Fin-Pref list")
        return {}

    quarter = gecs.get("QuarterEn", "")
    year = gecs.get("Year", "")

    return {
        "net_profit_omr": _parse_omr(gecs.get("Net_Profit_CP", "").replace(",", "")),
        "net_profit_prior_omr": _parse_omr(gecs.get("Net_Profit_PP", "").replace(",", "")),
        "latest_quarter": f"{quarter} {year}".strip(),
        "profit_change_pct": _parse_omr(gecs.get("Change_Per", "")),
        "latest_profit_news_date": gecs.get("NewsDate", ""),
    }


# ---------------------------------------------------------------------------
# Source 4: Financial report ZIP (income statement + narrative)
# ---------------------------------------------------------------------------

def scrape_financial_report() -> dict:
    """Download best available annual/quarterly report ZIP and extract:
    - Income statement: revenue, net profit, EPS
    - Company report: order backlog from BOD narrative
    - Management discussion: strategic initiatives, market share
    """
    logger.info("Fetching financial reports index")
    reports = _post_json("snapshot.aspx/FinancialsReports", {"Symbol": "GECS", "Year": ""})
    if not reports:
        return {}

    PRIORITY = {"Yearly (Audited)": 0, "Q3 (Un-Audited)": 1, "Q2 (Un-Audited)": 2, "Q1 (Un-Audited)": 3}
    candidates = [r for r in reports if r.get("FileNameEn") and r.get("NameEn") in PRIORITY]
    if not candidates:
        return {}

    candidates.sort(key=lambda r: (r.get("ReportYear", ""), -PRIORITY.get(r["NameEn"], 99)), reverse=True)
    best = candidates[0]

    zip_url = f"{BASE_URL}/MSMDOCS/FinancialReports/{best['FileNameEn']}"
    report_label = f"{best.get('NameEn', '')} {best.get('ReportYear', '')}".strip()
    logger.info("Downloading: %s", report_label)

    try:
        resp = requests.get(zip_url, headers=_BROWSER_HEADERS, timeout=60)
        resp.raise_for_status()
    except Exception as exc:
        logger.warning("ZIP download failed: %s", exc)
        return {}

    try:
        zf = zipfile.ZipFile(io.BytesIO(resp.content))
    except zipfile.BadZipFile as exc:
        logger.warning("Bad ZIP: %s", exc)
        return {}

    result: dict = {
        "financial_report_label": report_label,
        "financial_report_date": best.get("UploadDate", ""),
    }
    result.update(_parse_income_statement(zf))
    result.update(_parse_report_narrative(zf))
    return result


def _parse_income_statement(zf: zipfile.ZipFile) -> dict:
    """Extract revenue, net profit, EPS from IncomeStatement PDF in the ZIP."""
    fname = next((n for n in zf.namelist() if "IncomeStatement" in n), None)
    if not fname:
        return {}

    text = _pdf_text(zf.read(fname))
    if not text.strip():
        logger.debug("Income statement PDF has no extractable text")
        return {}

    result: dict = {}
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if re.match(r"^(Total\s+)?[Rr]evenue\b", line) and "revenue_omr" not in result:
            val = _first_number(re.sub(r"^(Total\s+)?[Rr]evenue\s*", "", line))
            if val is not None:
                result["revenue_omr"] = val * 1000  # PDF values in thousands OMR
        if re.search(r"Net Profit\s*/\s*\(Loss\)\s+for the period", line, re.IGNORECASE) and "report_net_profit_omr" not in result:
            val = _first_number(re.sub(r".*for the period\s*", "", line))
            if val is not None:
                result["report_net_profit_omr"] = val * 1000
        if re.search(r"Basic earnings \(loss\) per share from continuing", line, re.IGNORECASE) and "eps" not in result:
            val = _first_number(re.sub(r".*continuing operations\s*", "", line))
            if val is not None:
                result["eps"] = val

    return result


def _parse_report_narrative(zf: zipfile.ZipFile) -> dict:
    """Extract strategic intelligence from CompanyReport and ManagementDiscussion PDFs."""
    result: dict = {}
    files = zf.namelist()

    for fname_key, label in [("CompanyReport", "BOD Report"), ("ManagementDic", "MD&A")]:
        fname = next((n for n in files if fname_key in n), None)
        if not fname:
            continue

        text = _pdf_text(zf.read(fname))
        if not text.strip():
            continue

        logger.debug("Parsing %s (%s)", fname, label)

        # Order backlog
        if "order_backlog_omr" not in result:
            m = re.search(
                r"order backlog of approximately\s+(?:RO|OMR)\s*([\d,]+\.?\d*)\s*(million|mn|billion|bn)",
                text, re.IGNORECASE
            )
            if m:
                val = _parse_omr(m.group(1))
                mult = 1_000_000 if m.group(2).lower() in ("million", "mn") else 1_000_000_000
                if val is not None:
                    result["order_backlog_omr"] = val * mult

        # Market share range
        if "market_share_pct_range" not in result:
            m = re.search(r"market share.*?(\d+)\s*[–\-]\s*(\d+)\s*%", text, re.IGNORECASE)
            if m:
                result["market_share_pct_range"] = f"{m.group(1)}-{m.group(2)}%"

        # Tender success rate
        if "tender_success_rate_range" not in result:
            m = re.search(r"tender success rate.*?(\d+)\s*[–\-]\s*(\d+)\s*%", text, re.IGNORECASE)
            if m:
                result["tender_success_rate_range"] = f"{m.group(1)}-{m.group(2)}%"

        # Backlog sector concentration (look for sector mentions near "backlog")
        if "backlog_sector_concentration" not in result:
            m = re.search(
                r"[Bb]acklog.*?(?:concentrated|largely|primarily).*?in\s+(.{20,120}?)(?:\.|,|$)",
                text
            )
            if m:
                result["backlog_sector_concentration"] = m.group(1).strip()

    # Strategic initiatives — collect relevant sentences from MD&A
    mda_fname = next((n for n in files if "ManagementDic" in n), None)
    if mda_fname:
        mda_text = _pdf_text(zf.read(mda_fname))
        result["strategic_initiatives"] = _extract_strategic_initiatives(mda_text)

    return result


def _extract_strategic_initiatives(text: str) -> list[str]:
    """Pull Galfar-specific forward-looking strategic sentences from MD&A."""
    STRATEGY_KEYWORDS = [
        "expanding", "diversif", "renewable energy", "high-voltage", "PPP",
        "digital", "partnership", "joint venture", "EPC", "energy transition",
    ]
    # Galfar-specific subject markers — sentence must be about Galfar's actions
    SUBJECT_MARKERS = [
        "galfar", "the company", "the group", "management", "we are",
    ]
    # Normalise newlines within paragraphs before splitting
    clean = re.sub(r"\n(?=[a-z])", " ", text)
    initiatives = []
    for sent in re.split(r"(?<=[.!?])\s+", clean):
        sent = sent.strip()
        if len(sent) < 50 or len(sent) > 280:
            continue
        sent_low = sent.lower()
        if not any(kw in sent_low for kw in STRATEGY_KEYWORDS):
            continue
        if not any(sm in sent_low for sm in SUBJECT_MARKERS):
            continue
        # Clean any embedded newlines left from PDF column breaks
        sent = re.sub(r"\s+", " ", sent).strip()
        if not any(s.lower() == sent.lower() for s in initiatives):
            initiatives.append(sent)
        if len(initiatives) >= 5:
            break
    return initiatives


# ---------------------------------------------------------------------------
# Source 5: MSX contract announcements
# ---------------------------------------------------------------------------

def scrape_msx_contracts(max_years: int = 3) -> list[dict]:
    """Fetch MSX 'Tender Award' announcements and parse their PDFs.

    Checks the last max_years calendar years plus the current year.
    Returns a list of contract dicts, skipping any with no parseable content.
    """
    current_year = date.today().year
    years = [str(y) for y in range(current_year - max_years + 1, current_year + 1)]

    contract_items = []
    for year in years:
        url = f"{BASE_URL}/company-news.aspx?s=GECS&y={year}&f=1&t=12&i="
        try:
            resp = requests.get(url, headers=_BROWSER_HEADERS, timeout=TIMEOUT)
            items = resp.json()
        except Exception as exc:
            logger.warning("MSX news fetch failed for %s: %s", year, exc)
            continue

        for item in items:
            title = item.get("TitleEn", "")
            if "tender award" in title.lower() or "contract award" in title.lower():
                contract_items.append({
                    "date_raw": item.get("DateTime", ""),
                    "title": title,
                    "doc": item.get("Doc_News", ""),
                })
        time.sleep(0.3)

    logger.info("Found %d MSX contract announcements to parse", len(contract_items))

    contracts = []
    for item in contract_items:
        doc = item.get("doc")
        if not doc:
            continue
        pdf_url = f"{BASE_URL}/msmdocs/images/newsdocs/{doc}"
        try:
            resp = requests.get(pdf_url, headers=_BROWSER_HEADERS, timeout=PDF_TIMEOUT)
            resp.raise_for_status()
        except Exception as exc:
            logger.debug("PDF download failed %s: %s", doc, exc)
            continue

        text = _pdf_text(resp.content)
        if not text.strip():
            logger.debug("Image-based PDF, skipping: %s", doc)
            continue

        parsed = _parse_contract_pdf(text)
        if not parsed:
            continue

        # Normalise date
        date_str = _normalise_date(item["date_raw"])

        contracts.append({
            "date": date_str,
            "title": item["title"],
            "pdf_url": pdf_url,
            "client": parsed.get("client"),
            "project": parsed.get("project"),
            "value_omr": parsed.get("value_omr"),
            "source": "MSX Announcement",
        })
        time.sleep(0.3)

    logger.info("Parsed %d MSX contract wins", len(contracts))
    return contracts


def _parse_contract_pdf(text: str) -> dict:
    """Extract contract value, client, and project from a Tender Award PDF."""
    # Strip Arabic/non-ASCII characters — PDFs are bilingual (Arabic + English)
    ascii_text = re.sub(r"[^\x00-\x7F]+", " ", text)
    ascii_text = re.sub(r"\s{2,}", " ", ascii_text).strip()

    result: dict = {}

    result["value_omr"] = _extract_omr_value(ascii_text)

    # Client: "awarded by [Client]" or "been awarded by [Client]"
    m = re.search(
        r"(?:awarded by|award(?:ed)? (?:to|from)|been awarded by)\s+"
        r"([A-Z][A-Za-z\s,&()']+?)(?:\s*[\"\(\n]|$)",
        ascii_text, re.MULTILINE,
    )
    if m:
        result["client"] = _trim_client(m.group(1))

    # Project: first quoted string of reasonable length
    m = re.search(r'"([A-Z][^"]{10,180})"', ascii_text)
    if m:
        result["project"] = m.group(1).strip()
    elif not result.get("project"):
        m = re.search(
            r"Award of (?:Tender|Project|Contract) to Galfar for\s+(.+?)(?:\n|OMR|RO|\Z)",
            ascii_text, re.IGNORECASE,
        )
        if m:
            result["project"] = _ascii_clean(m.group(1).strip().rstrip(".,"))

    return result if (result.get("value_omr") or result.get("client") or result.get("project")) else {}


# ---------------------------------------------------------------------------
# Source 6: Galfar website WordPress REST API
# ---------------------------------------------------------------------------

def scrape_galfar_website(max_years: int = 3) -> list[dict]:
    """Fetch contract win press releases from Galfar's WordPress site."""
    logger.info("Fetching Galfar website posts")

    cutoff_year = date.today().year - max_years

    CONTRACT_TITLE_WORDS = {
        "contract", "award", "tender", "secures", "wins", "win",
        "project", "appointed", "selected",
    }

    try:
        resp = requests.get(
            GALFAR_WP_API,
            params={"per_page": 20, "_fields": "id,date,title,link,content"},
            headers={"User-Agent": _BROWSER_HEADERS["User-Agent"]},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        posts = resp.json()
    except Exception as exc:
        logger.warning("Galfar website fetch failed: %s", exc)
        return []

    contracts = []
    for post in posts:
        title = _strip_html(post.get("title", {}).get("rendered", ""))
        content = _strip_html(post.get("content", {}).get("rendered", ""))
        date_str = post.get("date", "")[:10]
        link = post.get("link", "")

        title_lower = title.lower()
        # Filter by date: skip posts older than cutoff_year
        post_year = int(date_str[:4]) if date_str else 0
        if post_year < cutoff_year:
            continue

        if not any(w in title_lower for w in CONTRACT_TITLE_WORDS):
            continue

        # Skip non-contract posts (road openings, general news)
        if any(skip in title_lower for skip in ["opens for traffic", "launches", "celebrates", "anniversary"]):
            continue

        value_omr = _extract_omr_value(title) or _extract_omr_value(content[:500])
        client = _extract_client_from_text(title + " " + content[:300])
        project = _extract_project_description(title, content)

        contracts.append({
            "date": date_str,
            "title": title,
            "article_url": link,
            "client": client,
            "project": project,
            "value_omr": value_omr,
            "source": "Galfar Website",
        })

    logger.info("Parsed %d Galfar website contract posts", len(contracts))
    return contracts


def _extract_client_from_text(text: str) -> str | None:
    """Extract client name from contract announcement text."""
    # Ordered from most specific to most general
    patterns = [
        # "contract worth RO X by/from [Client]"
        r"(?:contract|tender|award).*?(?:by|from)\s+([A-Z][A-Za-z\s,&()']+?)(?:\s*(?:[.,()]|SAOG|Company\b|Ltd\b|LLC\b)|\s*$)",
        # "awarded by [Client]"
        r"awarded by\s+([A-Z][A-Za-z\s,&()']+?)(?:\s*(?:[.,\n(\"']|SAOG)|\s*$)",
        # "for [ALL-CAPS abbreviation]" — e.g. "for PDO", "for OQ"
        r"\bfor\s+([A-Z]{2,6}(?:\s+[A-Z]{2,6})*)\b(?:['\s]|$)",
        # "for [Client]'s [project]" — "for PDO's"
        r"\bfor\s+([A-Z][A-Za-z\s&]+?)['']s\b",
        # "Ministry / Authority / Municipality" keyword
        r"((?:Ministry|Authority|Municipality)[A-Za-z\s&']*?)(?:\s*(?:[.,\n()']|SAOG)|\s*$)",
        # Known short-name clients: "PDO", "OQ", "SQU", etc.
        r"\b((?:PDO|OQ|SQU|Oxy|Occidental)(?:\s+[A-Z][A-Za-z]*)*)\b",
    ]
    search_area = text[:500]
    for pattern in patterns:
        m = re.search(pattern, search_area)
        if m:
            candidate = m.group(1).strip().rstrip(".,")
            if len(candidate) >= 2 and not candidate.lower().startswith(("the ", "a ", "an ", "this ")):
                return candidate
    return None


def _extract_project_description(title: str, content: str) -> str:
    """Extract a concise project description from title and content."""
    # First sentence of content often has the project description
    first_sent = re.split(r"(?<=[.!?])\s", content)[0].strip() if content else ""
    if len(first_sent) > 20:
        return first_sent[:200]
    return title


# ---------------------------------------------------------------------------
# Intelligence assembly
# ---------------------------------------------------------------------------

def build_news_intelligence(
    msx_contracts: list,
    report_narrative: dict,
    website_contracts: list,
) -> dict:
    """Combine all contract wins and strategic intelligence into one structure."""

    # MSX first (authoritative), then website supplements with extras
    all_contracts = msx_contracts + website_contracts
    all_contracts.sort(key=lambda c: c.get("date", ""), reverse=True)
    # Drop contracts with neither value nor a useful client (noise)
    all_contracts = [
        c for c in all_contracts
        if c.get("value_omr") or (c.get("client") and c["client"] != "?")
    ]

    deduplicated = _dedup_contracts(all_contracts)

    return {
        "recent_contract_wins": deduplicated,
        "order_backlog_omr": report_narrative.get("order_backlog_omr"),
        "backlog_sector_concentration": report_narrative.get("backlog_sector_concentration"),
        "market_position": {
            "market_share_pct_range": report_narrative.get("market_share_pct_range"),
            "tender_success_rate_range": report_narrative.get("tender_success_rate_range"),
        },
        "strategic_initiatives": report_narrative.get("strategic_initiatives", []),
        "news_counts": {
            "msx_contract_announcements": len(msx_contracts),
            "galfar_website_posts": len(website_contracts),
        },
    }


def _dedup_contracts(contracts: list) -> list:
    """Remove duplicate entries (same value within 30 days = same contract)."""
    seen: list[dict] = []
    for c in contracts:
        val = c.get("value_omr")
        dt = c.get("date", "")
        is_dup = False
        for s in seen:
            if val and s.get("value_omr") == val:
                # Same value — likely same contract reported by two sources
                # Keep the one with more information
                is_dup = True
                # Merge: prefer MSX source if it has a pdf_url
                if c.get("pdf_url") and not s.get("pdf_url"):
                    s["pdf_url"] = c["pdf_url"]
                if c.get("client") and not s.get("client"):
                    s["client"] = c["client"]
                if c.get("project") and not s.get("project"):
                    s["project"] = c["project"]
                break
        if not is_dup:
            seen.append(dict(c))
    return seen


# ---------------------------------------------------------------------------
# Helpers shared by multiple parsers
# ---------------------------------------------------------------------------

def _ascii_clean(text: str) -> str:
    """Remove non-ASCII chars and collapse whitespace."""
    return re.sub(r"\s+", " ", re.sub(r"[^\x00-\x7F]+", " ", text)).strip()


def _trim_client(raw: str) -> str:
    """Trim noise from a client name: stop at parenthesis content, trailing punctuation."""
    clean = raw.strip().rstrip(".,")
    # Stop before "'s" possessive
    clean = re.split(r"['']s\b", clean)[0].strip()
    # Stop at first unbalanced ")" mid-string (e.g. "PDO) Qarn Alam project" → "PDO")
    paren_pos = clean.find(")")
    if paren_pos > 0 and clean[:paren_pos].count("(") == 0:
        clean = clean[:paren_pos].strip().rstrip("(").strip()
    # Stop at trailing unbalanced ")"
    if clean.endswith(")") and clean.count("(") < clean.count(")"):
        clean = clean[:clean.rfind("(")].strip()
    return clean or raw.strip()


def _first_number(line: str) -> float | None:
    """Return the first numeric token on a text line (handles parentheses notation)."""
    tokens = re.findall(r"\([\d,]+\.?\d*\)|[\d,]+\.?\d*", line)
    for tok in tokens:
        val = _parse_omr(tok)
        if val is not None:
            return val
    return None


def _normalise_date(date_raw: str) -> str:
    """Convert 'Apr 15, 2026 09:23:41' → '2026-04-15'."""
    try:
        for fmt in ("%b %d, %Y %H:%M:%S", "%b %d, %Y %I:%M:%S %p", "%b %d, %Y"):
            try:
                return datetime.strptime(date_raw.strip(), fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
    except Exception:
        pass
    # Fallback: try to grab first date-like string
    m = re.search(r"(\w+ \d{1,2},\s*\d{4})", date_raw)
    if m:
        try:
            return datetime.strptime(m.group(1), "%b %d, %Y").strftime("%Y-%m-%d")
        except ValueError:
            pass
    return date_raw[:10] if len(date_raw) >= 10 else date_raw


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_scraper() -> dict:
    """Run all scrapers and return a complete Galfar snapshot with intelligence."""
    market = scrape_market_data()
    quarterly = scrape_quarterly_performance()
    report = scrape_financial_report()

    # News intelligence (non-fatal if any source fails)
    msx_contracts: list = []
    website_contracts: list = []
    try:
        msx_contracts = scrape_msx_contracts(max_years=3)
    except Exception as exc:
        logger.warning("MSX contracts scrape failed: %s", exc)
    try:
        website_contracts = scrape_galfar_website()
    except Exception as exc:
        logger.warning("Galfar website scrape failed: %s", exc)

    news_intel = build_news_intelligence(
        msx_contracts=msx_contracts,
        report_narrative=report,
        website_contracts=website_contracts,
    )

    # Prefer quarterly net profit (more current) over annual report profit
    net_profit = quarterly.get("net_profit_omr") or report.get("report_net_profit_omr")
    # Order backlog: prefer narrative (higher authority) over None
    order_backlog = report.get("order_backlog_omr") or news_intel.get("order_backlog_omr")

    return {
        "company": "Galfar Engineering & Contracting",
        "ticker": "GECS",
        "exchange": "MSM",
        "scraped_at": datetime.now().isoformat(),

        # Market data
        "share_price_omr": market.get("share_price_omr"),
        "prev_close_omr": market.get("prev_close_omr"),
        "daily_high_omr": market.get("daily_high_omr"),
        "daily_low_omr": market.get("daily_low_omr"),
        "bid_price_omr": market.get("bid_price_omr"),
        "ask_price_omr": market.get("ask_price_omr"),
        "volume": market.get("volume"),
        "turnover_omr": market.get("turnover_omr"),
        "issued_shares": market.get("issued_shares"),
        "market_cap_omr": market.get("market_cap_omr"),

        # Quarterly financials
        "net_profit_omr": net_profit,
        "net_profit_prior_omr": quarterly.get("net_profit_prior_omr"),
        "profit_change_pct": quarterly.get("profit_change_pct"),
        "latest_quarter": quarterly.get("latest_quarter"),
        "latest_profit_news_date": quarterly.get("latest_profit_news_date"),

        # Annual report financials
        "revenue_omr": report.get("revenue_omr"),
        "report_net_profit_omr": report.get("report_net_profit_omr"),
        "eps": report.get("eps"),
        "financial_report_label": report.get("financial_report_label"),
        "financial_report_date": report.get("financial_report_date"),

        # Order backlog (from BOD narrative)
        "order_backlog_omr": order_backlog,

        # Intelligence
        "news_intelligence": news_intel,

        "sources_hit": {
            "market_data": bool(market),
            "quarterly_performance": bool(quarterly),
            "financial_report": bool(report.get("revenue_omr")),
            "msx_contracts": bool(msx_contracts),
            "galfar_website": bool(website_contracts),
        },
    }


def save_to_json(data: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    logger.info("Saved to %s", output_path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    print("Scraping Galfar MSX financial + news intelligence...")
    data = run_scraper()

    project_root = Path(__file__).resolve().parent.parent.parent.parent
    output_path = project_root / "scraped_data" / "galfar_financials.json"
    save_to_json(data, output_path)

    print(f"\nSaved to {output_path}")

    # Print summary
    intel = data.get("news_intelligence", {})
    contracts = intel.get("recent_contract_wins", [])
    print(f"\n--- Financial Summary ---")
    print(f"Share price:    OMR {data.get('share_price_omr')}")
    print(f"Market cap:     OMR {(data.get('market_cap_omr') or 0) / 1e6:.1f}M")
    print(f"Revenue (FY):   OMR {(data.get('revenue_omr') or 0) / 1e6:.1f}M  ({data.get('financial_report_label')})")
    print(f"Net profit:     OMR {(data.get('net_profit_omr') or 0) / 1e6:.2f}M  ({data.get('latest_quarter')})")
    print(f"Order backlog:  OMR {(data.get('order_backlog_omr') or 0) / 1e6:.0f}M")
    print(f"\n--- News Intelligence ---")
    print(f"Contract wins: {len(contracts)}")
    for c in contracts[:5]:
        val = f"OMR {c['value_omr']/1e6:.1f}M" if c.get("value_omr") else "value unknown"
        print(f"  {c.get('date','')}  {val}  {c.get('client') or c.get('title','')[:50]}  [{c.get('source','')}]")
    print(f"\nStrategic initiatives: {len(intel.get('strategic_initiatives', []))}")
    print(f"Sources hit: {data.get('sources_hit')}")
