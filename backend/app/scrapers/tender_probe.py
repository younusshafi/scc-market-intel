"""
Deep tender probe scraper.
Probes individual tender detail pages on the Tender Board portal to extract:
  - Bidder names and quoted values (Opening Report)
  - Document purchaser companies (Purchase Details)
  - NIT details (location, scope, title)

Ported from archive/major_project_probe.py and archive/competitor_probe.py.
Results stored in the TenderProbe database table.
"""

import hashlib
import re
import time
import logging
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Tender, TenderProbe, ScrapeLog

logger = logging.getLogger(__name__)
settings = get_settings()

BASE = settings.tender_board_base_url
DELAY = 2.0
MAX_LISTING_PAGES = 60
MAX_PROBES = 100

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
}

INFRA_KEYWORDS = [
    "Construction", "Ports", "Roads", "Bridges", "Pipeline",
    "Electromechanical", "Dams", "Marine",
    "مقاولات المواني", "مقاولات شبكات",
]


def _secure_url(path: str, params: dict) -> str:
    """Build a secure URL with hash validation (portal requirement)."""
    full = dict(params)
    full["CTRL_STRDIRECTION"] = "LTR"
    full["randomno"] = "fixedrandomno"
    names = ",".join(full.keys())
    vals = "".join(v for v in full.values() if v)
    hv = hashlib.sha256(vals.encode()).hexdigest()
    qs = "&".join(f"{k}={v}" for k, v in full.items())
    return f"{BASE}{path}?{qs}&encparam={names}&hashval={hv}"


def _get(session: requests.Session, url: str, label: str = "") -> requests.Response | None:
    """GET with retry logic."""
    for attempt in range(3):
        try:
            return session.get(url, timeout=60)
        except requests.RequestException as e:
            if attempt < 2:
                logger.warning(f"Retry {attempt + 1} for {label}: {e}")
                time.sleep(5)
    logger.error(f"Failed after 3 attempts: {label}")
    return None


def _is_blocked(soup: BeautifulSoup) -> bool:
    """Check if we hit a security wall."""
    title = soup.title.get_text(strip=True).lower() if soup.title else ""
    return "security" in title or "error" in title


def _normalize_tnum(tn: str) -> str:
    """Extract core numeric parts for fuzzy matching."""
    return re.sub(r'[^\d/]', '', tn)


# ---------------------------------------------------------------------------
# Step 1: Identify target tenders from DB
# ---------------------------------------------------------------------------

def _load_targets_from_db(db: Session) -> list[dict]:
    """Load probe targets from the tenders table.

    Targets: fee >= 200 OMR (all) or fee >= 50 OMR (infra categories).
    Also includes all SCC-relevant InProcess tenders.
    """
    tenders = db.query(Tender).all()
    print(f"  Total tenders in DB: {len(tenders)}")
    targets = []
    seen_numbers = set()

    for t in tenders:
        fee = t.fee or 0
        is_scc_inprocess = t.is_scc_relevant and t.view == "InProcessTenders"
        is_target = fee >= 200 or fee >= 50 or is_scc_inprocess

        if not is_target:
            continue

        tn = t.tender_number
        if tn in seen_numbers:
            continue
        seen_numbers.add(tn)

        targets.append({
            "tender_number": tn,
            "tender_number_en": t.tender_number_en or "",
            "name": (t.tender_name_en or t.tender_name_ar or "")[:80],
            "entity": (t.entity_en or t.entity_ar or "")[:60],
            "category": (t.category_en or t.category_ar or "")[:60],
            "fee": fee,
            "view": t.view or "",
            "internal_id": None,
            "bidders": [],
            "purchasers": [],
            "nit": {},
        })

    targets.sort(key=lambda x: -(x["fee"] or 0))
    capped = targets[:MAX_PROBES * 2]
    print(f"  Probe targets: {len(capped)} (from {len(targets)} eligible)")
    for t in capped[:5]:
        print(f"    Fee {t['fee']:>7.0f} | {t['tender_number'][:30]} | {t['name'][:45]}")
    if len(capped) > 5:
        print(f"    ... and {len(capped) - 5} more")
    logger.info(f"Probe targets from DB: {len(capped)}")
    return capped


# ---------------------------------------------------------------------------
# Step 2: Scan listing pages to find internal IDs
# ---------------------------------------------------------------------------

def _find_internal_ids(session: requests.Session, targets: list[dict]) -> list[dict]:
    """Scan listing pages to match tender numbers to internal portal IDs."""
    print(f"\n{'='*70}")
    print("STEP 2: Scanning listing pages for internal tender IDs")
    print("=" * 70)

    lookup = {}
    for t in targets:
        for tn_field in ("tender_number", "tender_number_en"):
            tn = t.get(tn_field, "")
            if tn:
                norm = _normalize_tnum(tn)
                if norm:
                    lookup[norm] = t

    found = 0
    needed = len(targets)

    for view_flag in ("InProcessTenders", "NewTenders"):
        if found >= needed:
            break

        print(f"\n  Scanning {view_flag}...")
        for pg in range(1, MAX_LISTING_PAGES + 1):
            if found >= needed:
                break

            params = {"viewFlag": view_flag, "CTRL_STRDIRECTION": "LTR"}
            if pg > 1:
                params["pageNo"] = str(pg)

            url = f"{BASE}/product/publicDash?" + "&".join(f"{k}={v}" for k, v in params.items())
            r = _get(session, url, f"{view_flag} page {pg}")
            if not r or r.status_code != 200:
                print(f"    Page {pg}: failed (status={r.status_code if r else 'no response'})")
                continue

            soup = BeautifulSoup(r.content, "html.parser")
            tables = soup.find_all("table")
            if len(tables) < 2:
                continue

            dt = max(tables, key=lambda tbl: len(tbl.find_all("tr")))
            page_found = 0

            for row in dt.find_all("tr")[1:]:
                cells = row.find_all("td")
                if len(cells) < 3:
                    continue

                row_tn = re.sub(r"\s+", " ", cells[1].get_text(strip=True))
                row_norm = _normalize_tnum(row_tn)

                if row_norm in lookup and lookup[row_norm]["internal_id"] is None:
                    for a in row.find_all("a", onclick=True):
                        m = re.search(r"getNit\('(\d+)'\)", a["onclick"])
                        if m:
                            lookup[row_norm]["internal_id"] = m.group(1)
                            found += 1
                            page_found += 1
                            print(f"    Page {pg}: MATCHED {row_tn[:35]} -> ID {m.group(1)}")
                            break

            if pg % 5 == 0:
                print(f"    Page {pg}: scanned ({found}/{needed} IDs found so far)")

            time.sleep(DELAY)

    print(f"\n  Internal IDs found: {found} / {needed}")
    logger.info(f"Internal IDs found: {found} / {needed}")
    return [t for t in targets if t["internal_id"]]


# ---------------------------------------------------------------------------
# Step 3: Fetch Opening Report, Purchase Details, NIT
# ---------------------------------------------------------------------------

def _fetch_opening_report(session: requests.Session, tid: str) -> list[dict]:
    """Fetch bidder data from the Opening Report page."""
    url = _secure_url("/product/tmsbidopen/TenderOpeningQCRStatusAction.action", {
        "callAction": "showOpeningStatus_public",
        "strTenderNo": tid,
        "PublicUrl": "1",
    })
    r = _get(session, url, f"opening {tid}")
    if not r:
        return []

    soup = BeautifulSoup(r.content, "html.parser")
    if _is_blocked(soup):
        return []

    bidders = []
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue
        hdr = " ".join(c.get_text(strip=True).lower() for c in rows[0].find_all(["th", "td"]))
        if "company" not in hdr:
            continue

        for row in rows[1:]:
            cells = [c.get_text(strip=True) for c in row.find_all("td")]
            if len(cells) >= 2 and cells[1]:
                bidders.append({
                    "company": cells[1],
                    "offer_type": cells[2] if len(cells) > 2 else "",
                    "quoted_value": cells[3] if len(cells) > 3 else "",
                    "status": cells[4] if len(cells) > 4 else "",
                })

    return bidders


def _fetch_purchase_details(session: requests.Session, tid: str) -> list[dict]:
    """Fetch document purchaser data."""
    url = _secure_url("/product/publicDash", {
        "viewFlag": "showParticipatedVendors",
        "tenderNo": tid,
        "PublicUrl": "1",
    })
    r = _get(session, url, f"purchase {tid}")
    if not r:
        return []

    soup = BeautifulSoup(r.content, "html.parser")
    if _is_blocked(soup):
        return []

    purchasers = []
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue
        hdr = " ".join(c.get_text(strip=True).lower() for c in rows[0].find_all(["th", "td"]))
        if "company" not in hdr:
            continue

        for row in rows[1:]:
            cells = [c.get_text(strip=True) for c in row.find_all("td")]
            if len(cells) >= 3 and cells[2]:
                purchasers.append({
                    "reg_number": cells[1] if len(cells) > 1 else "",
                    "company": cells[2],
                    "company_type": cells[3] if len(cells) > 3 else "",
                    "purchase_date": cells[4] if len(cells) > 4 else "",
                })

    return purchasers


def _fetch_nit(session: requests.Session, tid: str) -> dict:
    """Fetch NIT (Notice Inviting Tender) details."""
    url = _secure_url("/product/nitParameterView", {
        "mode": "public",
        "tenderNo": tid,
        "PublicUrl": "1",
    })
    r = _get(session, url, f"NIT {tid}")
    if not r:
        return {}

    soup = BeautifulSoup(r.content, "html.parser")
    if _is_blocked(soup):
        return {}

    nit = {}
    text = soup.get_text(separator="\n")
    for key, pat in {
        "title": r"Tender Title\s*:\s*(.+)",
        "governorate": r"Governorate\s*:\s*(.+)",
        "wilayat": r"Wilayat\s*:\s*(.+)",
        "sub_category": r"Procurement Sub.*?Category\s*:\s*(.+)",
        "scope": r"Scope.*?[Ww]ork\s*:\s*(.+)",
        "bid_bond": r"Bid Bond.*?:\s*(.+)",
        "envelope": r"Envelope Type\s*:\s*(.+)",
    }.items():
        m = re.search(pat, text)
        if m:
            nit[key] = re.sub(r"\s+", " ", m.group(1).strip())[:120]

    return nit


def _fetch_details(session: requests.Session, targets: list[dict]) -> None:
    """Fetch Opening Report, Purchase Details, and NIT for each target."""
    print(f"\n{'='*70}")
    print(f"STEP 3: Fetching details for {len(targets)} tenders")
    print("=" * 70)

    for i, t in enumerate(targets):
        tid = t["internal_id"]
        print(f"\n  [{i + 1}/{len(targets)}] {t['tender_number'][:35]}")
        print(f"           {t['name'][:55]}")
        print(f"           Fee: {t['fee']:.0f} OMR | Entity: {t['entity'][:35]}")
        logger.info(f"[{i + 1}/{len(targets)}] Probing {t['tender_number']} (fee={t['fee']}) ...")

        print(f"           Fetching Opening Report...", end="", flush=True)
        t["bidders"] = _fetch_opening_report(session, tid)
        print(f" {len(t['bidders'])} bidders")
        time.sleep(DELAY)

        print(f"           Fetching Purchase Details...", end="", flush=True)
        t["purchasers"] = _fetch_purchase_details(session, tid)
        print(f" {len(t['purchasers'])} purchasers")
        time.sleep(DELAY)

        print(f"           Fetching NIT...", end="", flush=True)
        t["nit"] = _fetch_nit(session, tid)
        loc = t["nit"].get("governorate", "N/A")
        print(f" location={loc}")
        time.sleep(DELAY)

        if t["bidders"]:
            top = ", ".join(b["company"][:25] for b in t["bidders"][:4])
            extra = f" +{len(t['bidders'])-4} more" if len(t["bidders"]) > 4 else ""
            print(f"           Bidders: {top}{extra}")
        if t["nit"].get("scope"):
            print(f"           Scope: {t['nit']['scope'][:65]}")

        logger.info(
            f"  -> bidders={len(t['bidders'])}, purchasers={len(t['purchasers'])}, "
            f"location={loc}"
        )


# ---------------------------------------------------------------------------
# Step 4: Persist to database
# ---------------------------------------------------------------------------

def _persist_probes(db: Session, targets: list[dict]) -> dict:
    """Store/update probe results in the TenderProbe table."""
    new_count = 0
    updated_count = 0

    for t in targets:
        existing = db.query(TenderProbe).filter_by(tender_number=t["tender_number"]).first()

        if existing:
            existing.bidders = t["bidders"]
            existing.purchasers = t["purchasers"]
            existing.nit = t["nit"]
            existing.updated_at = datetime.utcnow()
            if t.get("name"):
                existing.tender_name = t["name"]
            if t.get("entity"):
                existing.entity = t["entity"]
            if t.get("category"):
                existing.category = t["category"]
            if t.get("fee"):
                existing.fee = t["fee"]
            updated_count += 1
        else:
            probe = TenderProbe(
                tender_number=t["tender_number"],
                tender_name=t.get("name"),
                entity=t.get("entity"),
                category=t.get("category"),
                fee=t.get("fee"),
                view=t.get("view"),
                bidders=t["bidders"],
                purchasers=t["purchasers"],
                nit=t["nit"],
            )
            db.add(probe)
            new_count += 1

    db.commit()
    return {"new": new_count, "updated": updated_count}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_tender_probe(db: Session) -> dict:
    """Run the full tender probe pipeline.

    1. Load targets from DB (high-fee + SCC-relevant InProcess tenders)
    2. Establish session with Tender Board portal
    3. Scan listings to find internal IDs
    4. Fetch bidder, purchaser, and NIT data
    5. Store results in TenderProbe table
    """
    started_at = datetime.utcnow()
    log = ScrapeLog(scrape_type="tender_probe", started_at=started_at, status="running")
    db.add(log)
    db.commit()

    try:
        # 1. Load targets
        print(f"\n{'='*70}")
        print("STEP 1: Loading probe targets from database")
        print("=" * 70)
        targets = _load_targets_from_db(db)
        if not targets:
            print("  No targets found — nothing to probe.")
            log.status = "success"
            log.completed_at = datetime.utcnow()
            log.details = {"message": "No targets found"}
            db.commit()
            return {"status": "no_targets", "probed": 0}

        # 2. Establish session
        print(f"\n  Establishing session with {BASE}...", end="", flush=True)
        session = requests.Session()
        session.headers.update(HEADERS)
        session.get(BASE, timeout=30)  # establish cookies
        print(" OK")

        # 3. Find internal IDs
        targets_with_ids = _find_internal_ids(session, targets)
        logger.info(f"Targets with internal IDs: {len(targets_with_ids)}")

        if not targets_with_ids:
            print("  Could not find any internal IDs — portal may be blocking.")
            log.status = "partial"
            log.completed_at = datetime.utcnow()
            log.records_found = len(targets)
            log.details = {"message": "Could not find internal IDs", "targets": len(targets)}
            db.commit()
            return {"status": "no_ids_found", "targets": len(targets), "probed": 0}

        # Cap to MAX_PROBES
        targets_with_ids = targets_with_ids[:MAX_PROBES]
        print(f"  Will probe {len(targets_with_ids)} tenders")

        # 4. Fetch details
        _fetch_details(session, targets_with_ids)

        # 5. Persist
        print(f"\n{'='*70}")
        print("STEP 4: Saving results to database")
        print("=" * 70)
        result = _persist_probes(db, targets_with_ids)
        print(f"  New: {result['new']} | Updated: {result['updated']}")

        with_bidders = sum(1 for t in targets_with_ids if t["bidders"])
        with_purchasers = sum(1 for t in targets_with_ids if t["purchasers"])

        log.status = "success"
        log.completed_at = datetime.utcnow()
        log.records_found = len(targets_with_ids)
        log.records_new = result["new"]
        log.records_updated = result["updated"]
        log.details = {
            "total_targets": len(targets),
            "ids_found": len(targets_with_ids),
            "with_bidders": with_bidders,
            "with_purchasers": with_purchasers,
        }
        db.commit()

        return {
            "status": "success",
            "targets": len(targets),
            "probed": len(targets_with_ids),
            "with_bidders": with_bidders,
            "with_purchasers": with_purchasers,
            **result,
        }

    except Exception as e:
        logger.error(f"Tender probe failed: {e}")
        log.status = "failed"
        log.completed_at = datetime.utcnow()
        log.error_message = str(e)[:500]
        db.commit()
        raise
