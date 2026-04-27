"""
Tender scraper for Oman Tender Board (etendering.tenderboard.gov.om)
Bilingual edition — fetches both Arabic (RTL) and English (LTR) versions
and merges them by row position.

Capped to 10 pages per view (~500 tenders each) to avoid portal timeouts.
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

BILINGUAL_FIELDS = {"tender_name", "entity", "category_grade", "tender_type", "parent_tender"}
SHARED_FIELDS = {"tender_number", "dates", "fee", "bank_guarantee"}
SKIP_FIELDS = {"serial", "action"}

TENDER_VIEWS = [
    {"label": "New/Floated Tenders",  "params": {"viewFlag": "NewTenders"},                                        "max_pages": 10},
    {"label": "In-Process Tenders",   "params": {"viewFlag": "InProcessTenders"},                                  "max_pages": 10},
    {"label": "Sub-Contract Tenders", "params": {"viewFlag": "SubContractTenders", "statusFlag": "NewTenders"},     "max_pages": None},
]

PAGE_DELAY = 1.0       # seconds between page fetches
VIEW_DELAY = 3.0       # seconds between switching views
MAX_RETRIES = 2        # retries per page before giving up


def parse_total_pages(soup):
    tables = soup.find_all("table")
    if not tables:
        return 1
    text = tables[-1].get_text(separator=" ", strip=True)
    m = re.search(r"(?:من|of)\s+(\d+)", text, re.I)
    return int(m.group(1)) if m else 1


def parse_rows(soup, header_map):
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
    merged = []
    for i in range(len(ar_rows)):
        ar = ar_rows[i]
        en = en_rows[i] if i < len(en_rows) else {}
        record = {}
        for field in SHARED_FIELDS:
            if field in ar:
                record[field] = ar[field]
            elif field in en:
                record[field] = en[field]
        if "tender_number" in en and "tender_number" in ar:
            record["tender_number_en"] = en["tender_number"]
        for field in BILINGUAL_FIELDS:
            if field in ar:
                record[f"{field}_ar"] = ar[field]
            if field in en:
                record[f"{field}_en"] = en[field]
        if "dates" in record:
            record.update(parse_dates(record["dates"]))
        if record:
            merged.append(record)
    return merged


def create_session():
    session = requests.Session()
    session.headers.update(HEADERS)
    print("Establishing session...")
    r = session.get(BASE_URL, timeout=30)
    print(f"  Status: {r.status_code} | Cookies: {len(session.cookies)}")
    return session


def fetch_with_retry(session, params, page=1):
    """GET a page with retries. Returns response or None."""
    qp = dict(params)
    if page > 1:
        qp["pageNo"] = str(page)
    for attempt in range(MAX_RETRIES + 1):
        try:
            return session.get(f"{BASE_URL}/product/publicDash", params=qp, timeout=45)
        except requests.exceptions.RequestException as e:
            if attempt < MAX_RETRIES:
                wait = 5 * (attempt + 1)
                print(f"    Retry {attempt+1}/{MAX_RETRIES} in {wait}s: {e}")
                time.sleep(wait)
            else:
                print(f"    FAILED after {MAX_RETRIES} retries: {e}")
                return None


def fetch_page_bilingual(session, base_params, page=1):
    """Fetch one page in AR + EN, merge. Returns (rows, total_pages) or (None, 0)."""
    ar_resp = fetch_with_retry(session, base_params, page)
    if ar_resp is None or ar_resp.status_code != 200:
        return None, 0
    ar_soup = BeautifulSoup(ar_resp.content, "html.parser")
    title = ar_soup.title.get_text(strip=True) if ar_soup.title else ""
    if "security" in title.lower():
        return None, 0
    total_pages = parse_total_pages(ar_soup)
    ar_rows = parse_rows(ar_soup, HEADER_MAP_AR)

    time.sleep(PAGE_DELAY)

    en_params = {**base_params, "CTRL_STRDIRECTION": "LTR"}
    en_rows = []
    en_resp = fetch_with_retry(session, en_params, page)
    if en_resp and en_resp.status_code == 200:
        en_soup = BeautifulSoup(en_resp.content, "html.parser")
        en_title = en_soup.title.get_text(strip=True) if en_soup.title else ""
        if "security" not in en_title.lower():
            en_rows = parse_rows(en_soup, HEADER_MAP_EN)

    if ar_rows and en_rows and len(ar_rows) == len(en_rows):
        merged = merge_bilingual(ar_rows, en_rows)
    elif ar_rows:
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
    view_max = view_cfg.get("max_pages")

    print(f"\n{'='*70}")
    print(f"  {label}")
    print(f"{'='*70}")

    page1, total_pages = fetch_page_bilingual(session, params, page=1)
    if page1 is None:
        print(f"  BLOCKED or ERROR on page 1")
        return []

    max_pg = total_pages
    if view_max is not None:
        max_pg = min(max_pg, view_max)

    print(f"  Page 1/{max_pg} — {len(page1)} tenders so far (portal has {total_pages} pages)")
    if page1:
        t = page1[0]
        name_en = t.get("tender_name_en", "")[:40]
        print(f"  First: {t.get('tender_number', '?')} — {name_en}")

    all_tenders = list(page1)

    for pg in range(2, max_pg + 1):
        time.sleep(PAGE_DELAY)
        try:
            page_data, _ = fetch_page_bilingual(session, params, page=pg)
        except Exception as e:
            print(f"  Page {pg}/{max_pg} — FAILED: {e}")
            print(f"  Saving {len(all_tenders)} tenders collected so far, moving on.")
            break
        if page_data is None:
            print(f"  Page {pg}/{max_pg} — ERROR, skipping")
            continue
        all_tenders.extend(page_data)
        print(f"  Page {pg}/{max_pg} — {len(all_tenders)} tenders so far")

    print(f"  Done: {len(all_tenders)} tenders scraped")
    return all_tenders


def print_bilingual_samples(tenders, count=5):
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
        print(f"  Cat    (EN): {t.get('category_grade_en', '-')}")
        print(f"  Close:       {t.get('bid_closing_date', t.get('sales_end_date', '-'))}")


def main():
    print("=" * 70)
    print("Oman Tender Board — Bilingual Public Tender Scraper")
    print("=" * 70)

    session = create_session()

    r = session.get(f"{BASE_URL}/product/publicDash", timeout=30)
    with open("raw_response.html", "wb") as f:
        f.write(r.content)

    results = {}
    for i, view in enumerate(TENDER_VIEWS):
        if i > 0:
            print(f"\n  Pausing {VIEW_DELAY}s before next view...")
            time.sleep(VIEW_DELAY)
        label = view["label"]
        tenders = scrape_view(session, view)
        for t in tenders:
            t["_view"] = label
        results[label] = tenders

    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    grand_total = 0
    for label, tenders in results.items():
        count = len(tenders)
        grand_total += count
        print(f"  {label}: {count} tenders")
    print(f"  Grand total: {grand_total} tenders")

    first_view = list(results.values())[0] if results else []
    print_bilingual_samples(first_view, count=5)

    # Save (always, even if partial)
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
