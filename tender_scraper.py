"""
Tender scraper for Oman Tender Board (etendering.tenderboard.gov.om)
Bilingual edition — fetches both Arabic (RTL) and English (LTR) versions
and merges them by row position.

VALIDATED FINDINGS (session_probe.py, 2026-04-26):
  - GET with &CTRL_STRDIRECTION=LTR returns the English version of the same data
  - Arabic and English pages have identical row counts and ordering
  - Tender numbers differ in format (year position swaps) but rows align by index
  - Pagination via &pageNo=N works identically in both languages
"""

import json
import os
import re
import sys
import time
import traceback
from datetime import datetime

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://etendering.tenderboard.gov.om"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
}

# Header-to-key maps per language.  serial/action are skipped during storage.
HEADER_MAP_AR = {
    "رقم التسلسل": "serial",
    "رقم المناقصة": "tender_number",
    "إسم المناقصة": "tender_name",
    "الجهة/الوحدة الحكومية": "entity",
    "[  الدرجة]فئة المشتريات": "category_grade",
    "نوع المناقصه[نوع الشركة]": "tender_type",
    "التاريخ": "dates",
    "تاريخ الفتح الفعلي": "dates",
    "رسوم المناقصة": "fee",
    "الضمان البنكي(%/value)": "bank_guarantee",
    "إجْراء": "action",
    "رقم المناقصة الأساسية [ أسم المناقصة الأساسية ]": "parent_tender",
}

HEADER_MAP_EN = {
    "S.No.": "serial",
    "Tender No": "tender_number",
    "Tender Title": "tender_name",
    "Entity": "entity",
    "Category [ Grade ]": "category_grade",
    "Tender Type[Vendor Type]": "tender_type",
    "Date": "dates",
    "Actual Opening Date": "dates",
    "Tender Fee": "fee",
    "Tender Bond(%/value)": "bank_guarantee",
    "Action": "action",
    "Parent Tender Number [ Parent Tender Title ]": "parent_tender",
}

# Which fields are bilingual (get _ar / _en suffixes)
BILINGUAL_FIELDS = {"tender_name", "entity", "category_grade", "tender_type", "parent_tender"}
# Which fields are language-independent (stored once)
SHARED_FIELDS = {"tender_number", "dates", "fee", "bank_guarantee"}
SKIP_FIELDS = {"serial", "action"}

TENDER_VIEWS = [
    {"label": "New/Floated Tenders", "params": {"viewFlag": "NewTenders"}},
    {"label": "In-Process Tenders", "params": {"viewFlag": "InProcessTenders"}},
    {"label": "Sub-Contract Tenders", "params": {"viewFlag": "SubContractTenders", "statusFlag": "NewTenders"}},
]

# How many pages to fetch per view (None = all pages)
MAX_PAGES = None  # Set to e.g. 3 for testing, None for full scrape


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_total_pages(soup):
    tables = soup.find_all("table")
    if not tables:
        return 1
    text = tables[-1].get_text(separator=" ", strip=True)
    m = re.search(r"(?:من|of)\s+(\d+)", text, re.I)
    return int(m.group(1)) if m else 1


def parse_rows(soup, header_map):
    """Parse tender rows from one language version of a page.

    Returns a list of dicts keyed by the canonical field names from header_map.
    """
    tables = soup.find_all("table")
    if len(tables) < 2:
        return []

    data_table = max(tables, key=lambda t: len(t.find_all("tr")))
    rows = data_table.find_all("tr")
    if len(rows) < 2:
        return []

    header_cells = rows[0].find_all(["th", "td"])
    raw_headers = [cell.get_text(strip=True) for cell in header_cells]
    mapped = [header_map.get(h, h) for h in raw_headers]

    result = []
    for row in rows[1:]:
        cells = row.find_all("td")
        if not cells:
            continue
        record = {}
        for i, cell in enumerate(cells):
            if i >= len(mapped):
                break
            key = mapped[i]
            if key in SKIP_FIELDS:
                continue
            text = re.sub(r"\s+", " ", cell.get_text(separator=" ", strip=True)).strip()
            if text and text != "N/A":
                record[key] = text
        if record:
            result.append(record)
    return result


def parse_dates(date_str):
    extra = {}
    for m in re.finditer(r"Sales\s*EndDate\s*:\s*(\d{2}-\d{2}-\d{4})", date_str):
        extra["sales_end_date"] = m.group(1)
    for m in re.finditer(r"Bid\s*Closing\s*Date\s*:\s*(\d{2}-\d{2}-\d{4})", date_str):
        extra["bid_closing_date"] = m.group(1)
    if not extra:
        m = re.match(r"(\d{2}-\d{2}-\d{4})", date_str.strip())
        if m:
            extra["date"] = m.group(1)
    return extra


def merge_bilingual(ar_rows, en_rows):
    """Merge Arabic and English row lists into bilingual records by position."""
    merged = []
    for i in range(len(ar_rows)):
        ar = ar_rows[i]
        en = en_rows[i] if i < len(en_rows) else {}

        record = {}
        # Shared fields — prefer Arabic tender_number (has ministry abbreviation)
        for field in SHARED_FIELDS:
            if field in ar:
                record[field] = ar[field]
            elif field in en:
                record[field] = en[field]

        # Also store the English tender number as an alternate
        if "tender_number" in en and "tender_number" in ar:
            record["tender_number_en"] = en["tender_number"]

        # Bilingual fields
        for field in BILINGUAL_FIELDS:
            if field in ar:
                record[f"{field}_ar"] = ar[field]
            if field in en:
                record[f"{field}_en"] = en[field]

        # Parse dates
        if "dates" in record:
            record.update(parse_dates(record["dates"]))

        if record:
            merged.append(record)

    return merged


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------

def create_session():
    session = requests.Session()
    session.headers.update(HEADERS)
    print("Establishing session...")
    r = session.get(BASE_URL, timeout=30)
    print(f"  Status: {r.status_code} | Cookies: {len(session.cookies)}")
    return session


def fetch_page(session, params, page=1):
    qp = dict(params)
    if page > 1:
        qp["pageNo"] = str(page)
    return session.get(f"{BASE_URL}/product/publicDash", params=qp, timeout=30)


def fetch_page_bilingual(session, base_params, page=1):
    """Fetch a single page in both Arabic and English, return merged rows.

    If the English fetch fails, returns Arabic-only rows.
    """
    # Arabic
    ar_resp = fetch_page(session, base_params, page)
    if ar_resp.status_code != 200:
        return None, 0  # total_pages unknown
    ar_soup = BeautifulSoup(ar_resp.content, "html.parser")

    title = ar_soup.title.get_text(strip=True) if ar_soup.title else ""
    if "security" in title.lower():
        return None, 0

    total_pages = parse_total_pages(ar_soup)
    ar_rows = parse_rows(ar_soup, HEADER_MAP_AR)

    # English
    en_params = {**base_params, "CTRL_STRDIRECTION": "LTR"}
    try:
        time.sleep(0.5)
        en_resp = fetch_page(session, en_params, page)
        if en_resp.status_code == 200:
            en_soup = BeautifulSoup(en_resp.content, "html.parser")
            en_title = en_soup.title.get_text(strip=True) if en_soup.title else ""
            if "security" not in en_title.lower():
                en_rows = parse_rows(en_soup, HEADER_MAP_EN)
            else:
                en_rows = []
        else:
            en_rows = []
    except Exception as e:
        print(f"    English fetch failed (page {page}): {e} — using Arabic only")
        en_rows = []

    if ar_rows and en_rows and len(ar_rows) == len(en_rows):
        merged = merge_bilingual(ar_rows, en_rows)
    elif ar_rows:
        # Fallback: Arabic only, put fields into _ar suffixed keys
        merged = []
        for ar in ar_rows:
            record = {}
            for field in SHARED_FIELDS:
                if field in ar:
                    record[field] = ar[field]
            for field in BILINGUAL_FIELDS:
                if field in ar:
                    record[f"{field}_ar"] = ar[field]
            if "dates" in record:
                record.update(parse_dates(record["dates"]))
            if record:
                merged.append(record)
    else:
        merged = []

    return merged, total_pages


def scrape_view(session, view_cfg):
    label = view_cfg["label"]
    params = view_cfg["params"]

    print(f"\n{'='*70}")
    print(f"  {label}")
    print(f"{'='*70}")

    page1, total_pages = fetch_page_bilingual(session, params, page=1)
    if page1 is None:
        print(f"  BLOCKED or ERROR on page 1")
        return []

    print(f"  Page 1: {len(page1)} tenders | Total pages: {total_pages}")
    if page1:
        t = page1[0]
        tn = t.get("tender_number", "?")
        name_ar = t.get("tender_name_ar", "")[:30]
        name_en = t.get("tender_name_en", "")[:30]
        print(f"  Sample: {tn} — AR: {name_ar} / EN: {name_en}")

    all_tenders = list(page1)

    max_pg = total_pages
    if MAX_PAGES is not None:
        max_pg = min(total_pages, MAX_PAGES)

    for pg in range(2, max_pg + 1):
        time.sleep(0.5)

        page_data, _ = fetch_page_bilingual(session, params, page=pg)
        if page_data is None:
            print(f"  Page {pg}: ERROR")
            continue
        all_tenders.extend(page_data)

        if pg % 10 == 0 or pg == max_pg:
            print(f"  Page {pg}/{max_pg}: {len(page_data)} tenders (total so far: {len(all_tenders)})")

    print(f"  Done: {len(all_tenders)} tenders scraped")
    return all_tenders


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def print_bilingual_samples(tenders, count=5):
    """Print side-by-side Arabic/English samples for verification."""
    print(f"\n{'='*70}")
    print("BILINGUAL SAMPLES")
    print(f"{'='*70}")

    for i, t in enumerate(tenders[:count]):
        print(f"\n  --- Tender {i+1} ---")
        print(f"  Number (AR): {t.get('tender_number', '?')}")
        print(f"  Number (EN): {t.get('tender_number_en', '(same)')}")
        print(f"  Name   (AR): {t.get('tender_name_ar', '-')}")
        print(f"  Name   (EN): {t.get('tender_name_en', '-')}")
        print(f"  Entity (AR): {t.get('entity_ar', '-')}")
        print(f"  Entity (EN): {t.get('entity_en', '-')}")
        print(f"  Cat    (AR): {t.get('category_grade_ar', '-')}")
        print(f"  Cat    (EN): {t.get('category_grade_en', '-')}")
        print(f"  Type   (AR): {t.get('tender_type_ar', '-')}")
        print(f"  Type   (EN): {t.get('tender_type_en', '-')}")
        print(f"  Dates:       {t.get('dates', '-')}")
        print(f"  Close:       {t.get('bid_closing_date', t.get('sales_end_date', '-'))}")
        print(f"  Fee:         {t.get('fee', '-')}")


def print_summary(results):
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")

    grand_total = 0
    for label, tenders in results.items():
        count = len(tenders)
        grand_total += count
        print(f"\n  {label}: {count} tenders")
        if tenders:
            for t in tenders[:3]:
                num = t.get("tender_number", "?")
                name = t.get("tender_name_en") or t.get("tender_name_ar", "?")
                name = name[:50]
                entity = (t.get("entity_en") or t.get("entity_ar", "?"))[:30]
                print(f"    {num:35s} | {name:50s} | {entity}")
            if count > 3:
                print(f"    ... and {count - 3} more")

    print(f"\n  Grand total: {grand_total} tenders")


def main():
    print("=" * 70)
    print("Oman Tender Board — Bilingual Public Tender Scraper")
    print("=" * 70)

    session = create_session()

    r = session.get(f"{BASE_URL}/product/publicDash", timeout=30)
    with open("raw_response.html", "wb") as f:
        f.write(r.content)

    results = {}
    for view in TENDER_VIEWS:
        label = view["label"]
        tenders = scrape_view(session, view)
        for t in tenders:
            t["_view"] = label
        results[label] = tenders

    print_summary(results)

    # Print bilingual samples from NewTenders
    first_view = list(results.values())[0] if results else []
    print_bilingual_samples(first_view, count=8)

    # Save
    all_tenders = []
    for tenders in results.values():
        all_tenders.extend(tenders)

    output = {
        "scraped_at": datetime.now().isoformat(),
        "source": "etendering.tenderboard.gov.om",
        "bilingual": True,
        "total_tenders": len(all_tenders),
        "by_view": {label: len(t) for label, t in results.items()},
        "tenders": all_tenders,
    }

    with open("tenders.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\nSaved {len(all_tenders)} bilingual tenders to tenders.json")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        traceback.print_exc()
        sys.exit(1)
