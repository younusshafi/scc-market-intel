"""
Tender scraper for Oman Tender Board (etendering.tenderboard.gov.om).
Adapted from the original tender_scraper.py — bilingual scraping preserved.
Now stores results in PostgreSQL instead of JSON files.
"""

import re
import time
import logging
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Tender, ScrapeLog

logger = logging.getLogger(__name__)
settings = get_settings()

BASE_URL = settings.tender_board_base_url

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
    {"label": "NewTenders", "params": {"viewFlag": "NewTenders"}, "max_pages": 10},
    {"label": "InProcessTenders", "params": {"viewFlag": "InProcessTenders"}, "max_pages": 10},
    {"label": "SubContractTenders", "params": {"viewFlag": "SubContractTenders", "statusFlag": "NewTenders"}, "max_pages": None},
]

SCC_CAT_KW = ["Construction", "Ports", "Roads", "Bridges", "Pipeline",
              "Electromechanical", "Dams", "Marine", "مقاولات"]
SCC_GRADE_KW = ["Excellent", "First", "Second", "الممتازة", "الأولى", "الثانية"]
PAGINATION_PW = ["الأولى", "السابقة", "التالية", "الأخيرة", "Previous", "Next", "Last"]


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


def parse_date_str(d: str):
    """Convert dd-mm-yyyy to a date object."""
    if not d:
        return None
    m = re.match(r"(\d{2})-(\d{2})-(\d{4})", d)
    if m:
        try:
            from datetime import date
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            return None
    return None


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


def is_pagination_row(t):
    for f in ("tender_number", "tender_name_ar", "tender_name_en", "tender_name"):
        if any(pw in t.get(f, "") for pw in PAGINATION_PW):
            return True
    return False


def is_retender(t):
    n = t.get("tender_name_ar", "") + " " + t.get("tender_name_en", "") + " " + t.get("tender_name", "")
    return "اعادة طرح" in n or "إعادة طرح" in n or "recall" in n.lower()


def is_scc_relevant(t):
    cg = (t.get("category_grade_ar", "") + " " + t.get("category_grade_en", "")
          + " " + t.get("category_grade", ""))
    return any(k in cg for k in SCC_CAT_KW) and any(k in cg for k in SCC_GRADE_KW)


def split_category_grade(cg: str):
    """Split 'Category [ Grade ]' into (category, grade)."""
    gm = re.search(r"\[([^\]]+)\]", cg)
    cm = re.match(r"^([^\[]+)", cg)
    category = cm.group(1).strip() if cm else cg
    grade = gm.group(1).strip() if gm else ""
    return category, grade


def split_type(tt: str):
    m = re.match(r"^([^\[]+)", tt)
    return m.group(1).strip() if m else tt


def raw_to_tender_model(raw: dict, view: str) -> dict:
    """Convert a raw scraped dict into kwargs for the Tender model."""
    cg_ar = raw.get("category_grade_ar", raw.get("category_grade", ""))
    cg_en = raw.get("category_grade_en", "")
    cat_ar, grade_ar = split_category_grade(cg_ar)
    cat_en, grade_en = split_category_grade(cg_en) if cg_en else ("", "")

    type_ar = split_type(raw.get("tender_type_ar", raw.get("tender_type", "")))
    type_en = split_type(raw.get("tender_type_en", "")) or type_ar

    # Parse fee
    fee = None
    fee_str = raw.get("fee", "")
    if fee_str:
        try:
            fee = float(re.sub(r"[^\d.]", "", fee_str))
        except (ValueError, TypeError):
            pass

    return {
        "tender_number": raw.get("tender_number", ""),
        "tender_number_en": raw.get("tender_number_en"),
        "tender_name_ar": raw.get("tender_name_ar", raw.get("tender_name")),
        "tender_name_en": raw.get("tender_name_en"),
        "entity_ar": raw.get("entity_ar", raw.get("entity")),
        "entity_en": raw.get("entity_en"),
        "category_ar": cat_ar,
        "category_en": cat_en or cat_ar,
        "grade_ar": grade_ar,
        "grade_en": grade_en or grade_ar,
        "tender_type_ar": type_ar,
        "tender_type_en": type_en,
        "sales_end_date": parse_date_str(raw.get("sales_end_date")),
        "bid_closing_date": parse_date_str(raw.get("bid_closing_date")),
        "fee": fee,
        "bank_guarantee": raw.get("bank_guarantee"),
        "view": view,
        "is_retender": is_retender(raw),
        "is_scc_relevant": is_scc_relevant(raw),
        "is_subcontract": view == "SubContractTenders",
        "raw_data": raw,
    }


def scrape_all_tenders() -> list[dict]:
    """Run the full tender scrape across all views. Returns list of raw dicts."""
    session = requests.Session()
    session.headers.update(HEADERS)

    logger.info("Establishing session with Tender Board...")
    r = session.get(BASE_URL, timeout=30)
    logger.info(f"Session established: status={r.status_code}, cookies={len(session.cookies)}")

    all_tenders = []

    for view_cfg in TENDER_VIEWS:
        label = view_cfg["label"]
        params = view_cfg["params"]
        view_max = view_cfg.get("max_pages")

        logger.info(f"Scraping view: {label}")

        # Fetch page 1 (Arabic)
        try:
            ar_resp = session.get(f"{BASE_URL}/product/publicDash", params=params, timeout=45)
        except requests.RequestException as e:
            logger.error(f"Failed to fetch {label} page 1: {e}")
            continue

        if ar_resp.status_code != 200:
            logger.error(f"{label} page 1 returned status {ar_resp.status_code}")
            continue

        ar_soup = BeautifulSoup(ar_resp.content, "html.parser")
        title = ar_soup.title.get_text(strip=True) if ar_soup.title else ""
        if "security" in title.lower():
            logger.warning(f"{label}: blocked by security page")
            continue

        total_pages = parse_total_pages(ar_soup)
        ar_rows = parse_rows(ar_soup, HEADER_MAP_AR)

        time.sleep(settings.scrape_page_delay)

        # Fetch page 1 (English)
        en_params = {**params, "CTRL_STRDIRECTION": "LTR"}
        en_rows = []
        try:
            en_resp = session.get(f"{BASE_URL}/product/publicDash", params=en_params, timeout=45)
            if en_resp.status_code == 200:
                en_soup = BeautifulSoup(en_resp.content, "html.parser")
                en_title = en_soup.title.get_text(strip=True) if en_soup.title else ""
                if "security" not in en_title.lower():
                    en_rows = parse_rows(en_soup, HEADER_MAP_EN)
        except requests.RequestException:
            pass

        # Merge
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

        for t in merged:
            t["_view"] = label

        # Filter out pagination artifacts
        merged = [t for t in merged if not is_pagination_row(t)]
        all_tenders.extend(merged)

        logger.info(f"  {label} page 1: {len(merged)} tenders (portal has {total_pages} pages)")

        # Remaining pages
        max_pg = total_pages
        if view_max is not None:
            max_pg = min(max_pg, view_max)

        for pg in range(2, max_pg + 1):
            time.sleep(settings.scrape_page_delay)
            try:
                ar_resp = session.get(
                    f"{BASE_URL}/product/publicDash",
                    params={**params, "pageNo": str(pg)},
                    timeout=45,
                )
                if ar_resp.status_code != 200:
                    continue
                ar_soup = BeautifulSoup(ar_resp.content, "html.parser")
                ar_rows = parse_rows(ar_soup, HEADER_MAP_AR)

                time.sleep(settings.scrape_page_delay)

                en_resp = session.get(
                    f"{BASE_URL}/product/publicDash",
                    params={**en_params, "pageNo": str(pg)},
                    timeout=45,
                )
                en_rows = []
                if en_resp.status_code == 200:
                    en_soup = BeautifulSoup(en_resp.content, "html.parser")
                    en_rows = parse_rows(en_soup, HEADER_MAP_EN)

                if ar_rows and en_rows and len(ar_rows) == len(en_rows):
                    page_merged = merge_bilingual(ar_rows, en_rows)
                elif ar_rows:
                    page_merged = ar_rows
                else:
                    page_merged = []

                page_merged = [t for t in page_merged if not is_pagination_row(t)]
                for t in page_merged:
                    t["_view"] = label
                all_tenders.extend(page_merged)
                logger.info(f"  {label} page {pg}/{max_pg}: {len(all_tenders)} total")

            except Exception as e:
                logger.error(f"  {label} page {pg} failed: {e}")
                break

        time.sleep(3.0)  # pause between views

    logger.info(f"Scrape complete: {len(all_tenders)} tenders total")
    return all_tenders


def persist_tenders(db: Session, raw_tenders: list[dict]) -> dict:
    """Store scraped tenders in the database. Returns summary stats."""
    new_count = 0
    updated_count = 0

    for raw in raw_tenders:
        tender_num = raw.get("tender_number", "")
        view = raw.get("_view", "")

        if not tender_num:
            continue

        existing = db.query(Tender).filter_by(
            tender_number=tender_num, view=view
        ).first()

        kwargs = raw_to_tender_model(raw, view)

        if existing:
            for key, value in kwargs.items():
                setattr(existing, key, value)
            existing.last_seen = datetime.utcnow()
            updated_count += 1
        else:
            tender = Tender(**kwargs)
            db.add(tender)
            new_count += 1

    db.commit()
    return {"new": new_count, "updated": updated_count, "total": len(raw_tenders)}
