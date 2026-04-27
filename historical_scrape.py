"""
Historical tender scrape — deep bilingual scrape for trend analysis.

NewTenders: ALL pages (currently ~42)
InProcessTenders: capped at 50 pages (~2,500 tenders)
SubContractTenders: ALL pages (currently 1)

Saves to historical_tenders.json (does NOT overwrite tenders.json).
Includes post-scrape trend analysis.
"""

import json
import os
import re
import sys
import time
import traceback
from collections import defaultdict
from datetime import datetime

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://etendering.tenderboard.gov.om"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
}

HEADER_MAP_AR = {
    "رقم التسلسل": "serial", "رقم المناقصة": "tender_number",
    "إسم المناقصة": "tender_name", "الجهة/الوحدة الحكومية": "entity",
    "[  الدرجة]فئة المشتريات": "category_grade",
    "نوع المناقصه[نوع الشركة]": "tender_type",
    "التاريخ": "dates", "تاريخ الفتح الفعلي": "dates",
    "رسوم المناقصة": "fee", "الضمان البنكي(%/value)": "bank_guarantee",
    "إجْراء": "action",
    "رقم المناقصة الأساسية [ أسم المناقصة الأساسية ]": "parent_tender",
}

HEADER_MAP_EN = {
    "S.No.": "serial", "Tender No": "tender_number",
    "Tender Title": "tender_name", "Entity": "entity",
    "Category [ Grade ]": "category_grade",
    "Tender Type[Vendor Type]": "tender_type",
    "Date": "dates", "Actual Opening Date": "dates",
    "Tender Fee": "fee", "Tender Bond(%/value)": "bank_guarantee",
    "Action": "action",
    "Parent Tender Number [ Parent Tender Title ]": "parent_tender",
}

BILINGUAL_FIELDS = {"tender_name", "entity", "category_grade", "tender_type", "parent_tender"}
SHARED_FIELDS = {"tender_number", "dates", "fee", "bank_guarantee"}
SKIP_FIELDS = {"serial", "action"}

PAGE_DELAY = 2.0
VIEW_DELAY = 5.0
MAX_RETRIES = 3

VIEWS = [
    {"label": "New/Floated Tenders", "params": {"viewFlag": "NewTenders"}, "max_pages": None},
    {"label": "In-Process Tenders", "params": {"viewFlag": "InProcessTenders"}, "max_pages": 50},
    {"label": "Sub-Contract Tenders", "params": {"viewFlag": "SubContractTenders", "statusFlag": "NewTenders"}, "max_pages": None},
]


# ---------------------------------------------------------------------------
# Parsing (same as tender_scraper.py)
# ---------------------------------------------------------------------------

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


def fetch_with_retry(session, params, page=1):
    qp = dict(params)
    if page > 1:
        qp["pageNo"] = str(page)
    for attempt in range(MAX_RETRIES + 1):
        try:
            return session.get(f"{BASE_URL}/product/publicDash", params=qp, timeout=60)
        except requests.exceptions.RequestException as e:
            if attempt < MAX_RETRIES:
                wait = 5 * (attempt + 1)
                print(f"      Retry {attempt+1}/{MAX_RETRIES} in {wait}s: {e}")
                time.sleep(wait)
            else:
                print(f"      FAILED after {MAX_RETRIES} retries: {e}")
                return None


def fetch_page_bilingual(session, base_params, page=1):
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

    print(f"  Page 1/{max_pg} — {len(page1)} tenders (portal has {total_pages} pages)")
    all_tenders = list(page1)

    for pg in range(2, max_pg + 1):
        time.sleep(PAGE_DELAY)
        try:
            page_data, _ = fetch_page_bilingual(session, params, page=pg)
        except Exception as e:
            print(f"  Page {pg}/{max_pg} — FATAL: {e}")
            print(f"  Saving {len(all_tenders)} tenders, moving on.")
            break

        if page_data is None:
            print(f"  Page {pg}/{max_pg} — SKIPPED (error)")
            continue

        all_tenders.extend(page_data)

        if pg % 10 == 0 or pg == max_pg:
            print(f"  Page {pg}/{max_pg} — {len(all_tenders)} tenders so far")

    print(f"  Done: {len(all_tenders)} tenders")
    return all_tenders


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def extract_date(t):
    """Get the best date from a tender record as (year, month, dd-mm-yyyy)."""
    for field in ("bid_closing_date", "sales_end_date", "date"):
        d = t.get(field, "")
        m = re.match(r"(\d{2})-(\d{2})-(\d{4})", d)
        if m:
            dd, mm, yyyy = m.group(1), m.group(2), m.group(3)
            return int(yyyy), int(mm), d
    return None, None, None


def bi(t, field):
    return t.get(f"{field}_en") or t.get(f"{field}_ar") or t.get(field, "")


def analyse(tenders):
    print(f"\n{'='*70}")
    print("HISTORICAL ANALYSIS")
    print(f"{'='*70}")
    print(f"\nTotal tenders: {len(tenders)}")

    # Find date range
    earliest_date = None
    latest_date = None
    by_month = defaultdict(int)
    by_cat_month = defaultdict(lambda: defaultdict(int))
    retenders_by_month = defaultdict(int)
    retender_count = 0

    for t in tenders:
        yyyy, mm, raw = extract_date(t)
        if yyyy is None:
            continue

        key = f"{yyyy}-{mm:02d}"
        by_month[key] += 1

        if earliest_date is None or (yyyy, mm) < earliest_date:
            earliest_date = (yyyy, mm)
        if latest_date is None or (yyyy, mm) > latest_date:
            latest_date = (yyyy, mm)

        # Category
        cg = bi(t, "category_grade")
        cm = re.match(r"^([^\[]+)", cg)
        cat = cm.group(1).strip() if cm else "Unknown"
        by_cat_month[cat][key] += 1

        # Re-tenders
        names = (t.get("tender_name_ar", "") + " " + t.get("tender_name_en", ""))
        if "اعادة طرح" in names or "إعادة طرح" in names or "recall" in names.lower():
            retenders_by_month[key] += 1
            retender_count += 1

    if earliest_date:
        print(f"Earliest tender date: {earliest_date[0]}-{earliest_date[1]:02d}")
    if latest_date:
        print(f"Latest tender date:   {latest_date[0]}-{latest_date[1]:02d}")

    # Monthly counts
    print(f"\n--- Tenders by Month ---")
    for month in sorted(by_month.keys()):
        rt = retenders_by_month.get(month, 0)
        rt_str = f"  (re-tenders: {rt})" if rt else ""
        print(f"  {month}: {by_month[month]:>5} tenders{rt_str}")

    # Category by month (top 5 categories)
    cat_totals = {cat: sum(months.values()) for cat, months in by_cat_month.items()}
    top_cats = sorted(cat_totals.items(), key=lambda x: -x[1])[:5]

    print(f"\n--- Top 5 Categories by Month ---")
    months_sorted = sorted(by_month.keys())
    header = f"  {'Category':<45s}" + "".join(f" {m:>7}" for m in months_sorted)
    print(header)
    for cat, _ in top_cats:
        row = f"  {cat[:44]:<45s}"
        for m in months_sorted:
            row += f" {by_cat_month[cat].get(m, 0):>7}"
        print(row)

    # Re-tender summary
    print(f"\n--- Re-Tenders ---")
    print(f"  Total: {retender_count} out of {len(tenders)} ({round(retender_count/max(len(tenders),1)*100, 1)}%)")
    if retenders_by_month:
        for month in sorted(retenders_by_month.keys()):
            print(f"  {month}: {retenders_by_month[month]}")

    return {
        "total": len(tenders),
        "earliest": f"{earliest_date[0]}-{earliest_date[1]:02d}" if earliest_date else None,
        "latest": f"{latest_date[0]}-{latest_date[1]:02d}" if latest_date else None,
        "by_month": dict(by_month),
        "retenders_by_month": dict(retenders_by_month),
        "retender_total": retender_count,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    start = datetime.now()
    print("=" * 70)
    print("Historical Tender Scrape — Deep Bilingual")
    print(f"Started: {start.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    session = create_session()

    results = {}
    for i, view in enumerate(VIEWS):
        if i > 0:
            print(f"\n  Pausing {VIEW_DELAY}s before next view...")
            time.sleep(VIEW_DELAY)
        label = view["label"]
        tenders = scrape_view(session, view)
        for t in tenders:
            t["_view"] = label
        results[label] = tenders

    # Combine
    all_tenders = []
    for tenders in results.values():
        all_tenders.extend(tenders)

    elapsed = (datetime.now() - start).total_seconds()
    print(f"\n{'='*70}")
    print(f"Scrape complete: {len(all_tenders)} tenders in {elapsed:.0f}s")
    print(f"{'='*70}")

    for label, tenders in results.items():
        print(f"  {label}: {len(tenders)}")

    # Analyse
    analysis = analyse(all_tenders)

    # Save
    output = {
        "scraped_at": datetime.now().isoformat(),
        "source": "etendering.tenderboard.gov.om",
        "bilingual": True,
        "scrape_type": "historical_deep",
        "elapsed_seconds": round(elapsed),
        "total_tenders": len(all_tenders),
        "by_view": {label: len(t) for label, t in results.items()},
        "analysis": analysis,
        "tenders": all_tenders,
    }

    out_path = os.path.join(SCRIPT_DIR, "historical_tenders.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\nSaved {len(all_tenders)} tenders to historical_tenders.json")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        traceback.print_exc()
        sys.exit(1)
