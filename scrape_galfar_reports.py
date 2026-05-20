"""
Galfar MSX Financial Report Scraper
====================================
Stage 1 (this script): Download PDFs from MSX, extract raw text, save to disk.
Stage 2 (separate):    LLM extraction pass on saved raw text → structured JSON.

No API keys needed to run this script.

Usage:
    pip install pdfplumber requests
    python scrape_galfar_reports.py

Output:
    scraped_data/galfar_raw/           <- raw text files per report period
    scraped_data/galfar_reports.json   <- index of downloaded reports + metadata

Author: Zavia-ai for SCC Market Intelligence
"""

import io
import json
import zipfile
import logging
import requests
from datetime import datetime, date
from pathlib import Path

try:
    import pdfplumber
except ImportError:
    print("ERROR: pdfplumber not installed. Run: pip install pdfplumber")
    raise

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

MSX_BASE   = "https://www.msx.om/MSMDOCS/FinancialReports"
SYMBOL     = "GECS"

# Script lives in repo root; output goes to scraped_data/
SCRAPED_DATA = Path(__file__).resolve().parent / "scraped_data"
RAW_DIR      = SCRAPED_DATA / "galfar_raw"       # one .txt per report period
INDEX_PATH   = SCRAPED_DATA / "galfar_reports.json"  # index + metadata

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# ---------------------------------------------------------------------------
# URL Construction — deterministic, no listing page needed
# Publication calendar (approximate):
#   Q1:     ~May 13-15
#   Q2:     ~Aug 13-15
#   Q3:     ~Nov 12-17
#   Annual: ~Mar 11-15
# ---------------------------------------------------------------------------

def build_candidates(year: int) -> list[dict]:
    today = date.today()
    all_candidates = [
        {
            "period":         f"{year}_Q3",
            "label":          f"Q3 {year} (Un-Audited)",
            "url":            f"{MSX_BASE}/{SYMBOL}_{year}_Q3%20(Un-Audited)_e.zip",
            "expected_after": date(year, 11, 1),
        },
        {
            "period":         f"{year}_Q2",
            "label":          f"Q2 {year} (Un-Audited)",
            "url":            f"{MSX_BASE}/{SYMBOL}_{year}_Q2%20(Un-Audited)_e.zip",
            "expected_after": date(year, 8, 1),
        },
        {
            "period":         f"{year}_Q1",
            "label":          f"Q1 {year} (Un-Audited)",
            "url":            f"{MSX_BASE}/{SYMBOL}_{year}_Q1%20(Un-Audited)_e.zip",
            "expected_after": date(year, 5, 1),
        },
        {
            "period":         f"{year}_Annual",
            "label":          f"Annual {year} (Audited)",
            "url":            f"{MSX_BASE}/{SYMBOL}_{year}_Yearly%20(Audited)_e.zip",
            # Annual for year Y is published in Mar Y+1, so only include prior years
            "expected_after": date(year + 1, 3, 1),
        },
    ]
    return [c for c in all_candidates if today >= c["expected_after"]]


def get_all_candidates() -> list[dict]:
    """Current year + previous 2 years for backfill on first run."""
    year = date.today().year
    return (
        build_candidates(year) +
        build_candidates(year - 1) +
        build_candidates(year - 2)
    )


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------

def url_exists(url: str) -> bool:
    try:
        r = requests.head(url, headers=HEADERS, timeout=15, allow_redirects=True)
        log.info("HEAD %s → %s", url.split("/")[-1], r.status_code)
        return r.status_code == 200
    except Exception as e:
        log.warning("HEAD failed: %s", e)
        return False


def download_pdf_bytes(url: str) -> list[tuple[str, bytes]] | None:
    log.info("Downloading %s ...", url.split("/")[-1])
    try:
        r = requests.get(url, headers=HEADERS, timeout=60)
        r.raise_for_status()
    except Exception as e:
        log.error("Download failed: %s", e)
        return None

    try:
        with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
            all_files = zf.namelist()
            log.info("Zip contents: %s", all_files)

            # MSX zip structure (confirmed from Q1 2026):
            #   1_GECS_CompanyReport_*    — Directors report, MD&A, backlog, new awards
            #   2_GECS_BalanceSheet_*     — Assets, equity
            #   3_GECS_IncomeStatement_*  — Revenue, profit
            #   4_GECS_CashFlowStatements_*
            #   5_GECS_StockHolderEquity_*
            #   6_GECS_Notes_*            — 900KB+ footnotes, low signal, skip
            #   10_GECS_AuditorsReport_*  — Annual only
            #   11_GECS_FilingInformation_* — Cover sheet, skip
            # Strategy: extract files prefixed 1_, 2_, 3_ — high signal, manageable size

            TARGET_PREFIXES = ("1_", "2_", "3_", "9_", "10_")  # 9_ = MD&A (annual only), 10_ = auditors report

            selected = [
                n for n in all_files
                if n.lower().endswith(".pdf")
                and any(n.split("/")[-1].startswith(p) for p in TARGET_PREFIXES)
                and "filinginformation" not in n.lower()
            ]

            if not selected:
                # Fallback: anything except filing info and notes
                selected = [
                    n for n in all_files
                    if n.lower().endswith(".pdf")
                    and "filinginformation" not in n.lower()
                    and not n.split("/")[-1].startswith("6_")
                ]

            selected = sorted(selected)  # process in order: 1_, 2_, 3_
            log.info("Selected PDFs: %s", selected)
            return [(name, zf.read(name)) for name in selected]
    except zipfile.BadZipFile as e:
        log.error("Bad zip: %s", e)
        return None


# ---------------------------------------------------------------------------
# PDF Text Extraction
# ---------------------------------------------------------------------------

def extract_text(pdf_files: list[tuple[str, bytes]]) -> str:
    parts = []
    for name, pdf_bytes in pdf_files:
        log.info("Extracting: %s", name)
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            log.info("  Pages: %d", len(pdf.pages))
            file_parts = []
            for i, page in enumerate(pdf.pages):
                text = page.extract_text()
                if text:
                    file_parts.append(f"=== {name} | Page {i+1} ===\n{text}")
            parts.extend(file_parts)
    full = "\n\n".join(parts)
    log.info("Total extracted: %d characters", len(full))
    return full


# ---------------------------------------------------------------------------
# Index (tracks what's been downloaded, ready for LLM extraction pass)
# ---------------------------------------------------------------------------

def load_index() -> dict:
    if INDEX_PATH.exists():
        with open(INDEX_PATH) as f:
            return json.load(f)
    return {"reports": {}, "last_scrape": None}


def save_index(index: dict):
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    index["last_scrape"] = datetime.utcnow().isoformat() + "Z"
    with open(INDEX_PATH, "w") as f:
        json.dump(index, f, indent=2)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    log.info("=== Galfar MSX Report Scraper — Stage 1: Download & Extract Text ===")
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    index    = load_index()
    stored   = set(index.get("reports", {}).keys())
    log.info("Already stored: %s", sorted(stored))

    candidates = get_all_candidates()
    log.info("Candidates: %s", [c["period"] for c in candidates])

    new_count = 0

    for c in candidates:
        period = c["period"]
        label  = c["label"]
        url    = c["url"]

        if period in stored:
            log.info("SKIP %s — already downloaded", period)
            continue

        log.info("--- %s ---", label)

        if not url_exists(url):
            log.info("NOT FOUND — %s not published yet or URL mismatch", label)
            continue

        pdf_bytes = download_pdf_bytes(url)
        if not pdf_bytes:
            continue

        text = extract_text(pdf_bytes)
        if not text.strip():
            log.error("Empty text extraction for %s — PDF may be image-based", label)
            continue

        # Save raw text
        raw_path = RAW_DIR / f"{period}.txt"
        raw_path.write_text(text, encoding="utf-8")
        log.info("Raw text saved: %s", raw_path)

        # Update index
        index["reports"][period] = {
            "period":       period,
            "label":        label,
            "source_url":   url,
            "raw_text_path": str(raw_path),
            "char_count":   len(text),
            "downloaded_at": datetime.utcnow().isoformat() + "Z",
            "extracted":    False,   # LLM extraction not yet done
        }
        save_index(index)
        log.info("✓ %s saved (%d chars)", label, len(text))
        new_count += 1

    log.info("=== Done. %d new reports downloaded ===", new_count)
    log.info("Next step: run extract_galfar_financials.py to run LLM extraction pass")
    log.info("Raw text files: %s", RAW_DIR)
    log.info("Index: %s", INDEX_PATH)


if __name__ == "__main__":
    main()
