"""
Awarded Tender Scraper — SCC Market Intelligence
Scrapes ALL awarded tenders from the Oman Tender Board portal.

Stage 1: Listing pages → tender metadata (number, title, entity, category, grade, awarded date, internal ID)
Stage 2: Opening Report → all bidders, bid values, winner identification
Stage 3: Participation → doc purchase timestamps (construction tenders only)

Data is stored in JSON files, then seeded into the database separately.

Usage:
    python awarded_scraper.py                    # Full scrape (listing + details)
    python awarded_scraper.py --listing-only     # Just the listing pages
    python awarded_scraper.py --details-only     # Just Opening Reports (requires listing JSON)
    python awarded_scraper.py --from-page 100    # Resume listing from page 100
    python awarded_scraper.py --max-pages 10     # Limit listing pages (for testing)
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
import logging
from datetime import datetime

import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BASE = "https://etendering.tenderboard.gov.om"
DELAY = 1.5  # seconds between requests — be polite
DETAIL_DELAY = 2.0  # slightly longer for detail pages

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
}

# Construction/infra categories we want full details for
CONSTRUCTION_CATEGORIES = [
    "Construction of Ports Roads Bridges Railways Dams",
    "Construction and Maintenance",
    "Construction Works",
    "Pipeline Network Construction",
    "Electromechanical and Telecommunications Contracting",
]

OUTPUT_DIR = "scraped_data"
LISTING_FILE = os.path.join(OUTPUT_DIR, "awarded_tenders_listing.json")
DETAILS_FILE = os.path.join(OUTPUT_DIR, "awarded_tenders_details.json")
CHECKPOINT_FILE = os.path.join(OUTPUT_DIR, "awarded_scrape_checkpoint.json")


def _secure_url(path: str, params: dict) -> str:
    """Build a secure URL with SHA-256 hash validation."""
    full = dict(params)
    full["CTRL_STRDIRECTION"] = "LTR"
    full["randomno"] = "fixedrandomno"
    names = ",".join(full.keys())
    vals = "".join(v for v in full.values() if v)
    hv = hashlib.sha256(vals.encode()).hexdigest()
    qs = "&".join(f"{k}={v}" for k, v in full.items())
    return f"{BASE}{path}?{qs}&encparam={names}&hashval={hv}"


def _opening_report_url(tender_id: str) -> str:
    """Build URL for the Tender Opening Report (bidders + values)."""
    params = {
        "callAction": "showOpeningStatus_public",
        "strTenderNo": tender_id,
        "PublicUrl": "1",
    }
    full = dict(params)
    full["CTRL_STRDIRECTION"] = "LTR"
    full["randomno"] = "fixedrandomno"
    names = ",".join(full.keys())
    vals = "".join(v for v in full.values() if v)
    hv = hashlib.sha256(vals.encode()).hexdigest()
    qs = "&".join(f"{k}={v}" for k, v in full.items())
    return f"{BASE}/product/tmsbidopen/TenderOpeningQCRStatusAction.action?{qs}&encparam={names}&hashval={hv}"


def _participation_url(tender_id: str) -> str:
    """Build URL for doc purchase participation details."""
    params = {
        "tenderNo": tender_id,
        "CTRL_ROLEID": "99",
        "CTRL_USERID": "usr",
        "CTRL_SID": "abc",
        "callfrom": "public",
        "SCWF_envList": "PB",
        "PublicUrl": "1",
    }
    full = dict(params)
    full["CTRL_STRDIRECTION"] = "LTR"
    full["randomno"] = "fixedrandomno"
    names = ",".join(full.keys())
    vals = "".join(v for v in full.values() if v)
    hv = hashlib.sha256(vals.encode()).hexdigest()
    qs = "&".join(f"{k}={v}" for k, v in full.items())
    return f"{BASE}/product/AllVendorStatusReportPublic?{qs}&encparam={names}&hashval={hv}"


def _get(session: requests.Session, url: str, label: str = "") -> requests.Response | None:
    """GET with retry logic."""
    for attempt in range(3):
        try:
            r = session.get(url, timeout=60)
            if r.status_code == 200:
                return r
            logger.warning(f"HTTP {r.status_code} for {label} (attempt {attempt+1})")
        except requests.RequestException as e:
            logger.warning(f"Request failed for {label} (attempt {attempt+1}): {e}")
        if attempt < 2:
            time.sleep(5)
    logger.error(f"Failed after 3 attempts: {label}")
    return None


def _is_construction(category: str) -> bool:
    """Check if a category matches SCC's construction categories."""
    if not category:
        return False
    cat_lower = category.lower()
    return any(kw.lower() in cat_lower for kw in CONSTRUCTION_CATEGORIES)


# ===========================================================================
# STAGE 1: Scrape awarded tender listing pages
# ===========================================================================

def scrape_listing(session: requests.Session, from_page: int = 1, max_pages: int = 300) -> list[dict]:
    """Scrape all pages of awarded tender listings."""
    logger.info(f"STAGE 1: Scraping awarded tender listings from page {from_page}")

    # Load existing data if resuming
    all_tenders = []
    if from_page > 1 and os.path.exists(LISTING_FILE):
        with open(LISTING_FILE, encoding='utf-8') as f:
            all_tenders = json.load(f)
        logger.info(f"Loaded {len(all_tenders)} existing tenders from checkpoint")

    empty_pages = 0
    page = from_page

    while page <= max_pages and empty_pages < 3:
        # Page 1 without pageNo returns "Logged Out" — always include pageNo
        url = _secure_url("/product/CompletedTendersForPublic", {"pageNo": str(page)})
        r = _get(session, url, f"Awarded listing page {page}")

        if not r:
            empty_pages += 1
            page += 1
            continue

        soup = BeautifulSoup(r.content, "html.parser")
        title = soup.title.get_text(strip=True) if soup.title else ""

        if "logged out" in title.lower() or "security" in title.lower():
            logger.warning(f"Page {page}: blocked ({title})")
            empty_pages += 1
            page += 1
            time.sleep(5)
            continue

        tables = soup.find_all("table")
        if not tables:
            empty_pages += 1
            page += 1
            continue

        # Find the data table
        data_table = None
        for t in tables:
            rows = t.find_all("tr")
            if len(rows) > 2:
                # Check if it has tender-like content
                first_data = rows[1] if len(rows) > 1 else None
                if first_data and len(first_data.find_all("td")) >= 6:
                    data_table = t
                    break

        if not data_table:
            # Try the largest table
            data_table = max(tables, key=lambda t: len(t.find_all("tr")))

        rows = data_table.find_all("tr")
        data_rows = rows[1:]  # skip header

        if not data_rows:
            empty_pages += 1
            page += 1
            continue

        empty_pages = 0  # reset
        page_count = 0

        for row in data_rows:
            cells = row.find_all("td")
            if len(cells) < 6:
                continue

            # Skip pagination rows and non-tender rows
            first_cell = cells[0].get_text(strip=True)
            if not first_cell or not first_cell[0].isdigit():
                continue
            second_cell = cells[1].get_text(strip=True)
            if not second_cell or "/" not in second_cell:
                # Tender numbers always contain "/"
                continue
            # Skip rows that are navigation elements
            row_text = row.get_text(strip=True).lower()
            if "next" in row_text and len(row_text) < 30:
                continue
            if "page" in row_text and len(row_text) < 30:
                continue

            # Extract internal ID from onclick
            internal_id = None
            for a in row.find_all("a", onclick=True):
                m = re.search(r"showOpeningStatus_Report\('(\d+)'", a["onclick"])
                if m:
                    internal_id = m.group(1)
                    break

            tender = {
                "serial": first_cell,
                "tender_number": second_cell,
                "tender_title": cells[2].get_text(strip=True),
                "entity": cells[3].get_text(strip=True),
                "category_grade": cells[4].get_text(strip=True),
                "tender_type": cells[5].get_text(strip=True) if len(cells) > 5 else "",
                "awarded_date": cells[6].get_text(strip=True) if len(cells) > 6 else "",
                "internal_id": internal_id,
                "page": page,
                "scraped_at": datetime.now().isoformat(),
            }

            # Parse category and grade
            cg = tender["category_grade"]
            if "[" in cg:
                tender["category"] = cg.split("[")[0].strip()
                tender["grade"] = cg.split("[")[1].replace("]", "").strip()
            else:
                tender["category"] = cg
                tender["grade"] = ""

            tender["is_construction"] = _is_construction(tender["category"])
            all_tenders.append(tender)
            page_count += 1

        # Progress
        construction_count = sum(1 for t in all_tenders if t["is_construction"])
        logger.info(
            f"Page {page}: {page_count} tenders | "
            f"Total: {len(all_tenders)} | "
            f"Construction: {construction_count} | "
            f"Last date: {all_tenders[-1]['awarded_date'] if all_tenders else '?'}"
        )

        # Save checkpoint every 10 pages
        if page % 10 == 0:
            _save_json(all_tenders, LISTING_FILE)
            _save_checkpoint({"last_listing_page": page, "total_tenders": len(all_tenders)})

        page += 1
        time.sleep(DELAY)

    # Final save
    _save_json(all_tenders, LISTING_FILE)
    construction_count = sum(1 for t in all_tenders if t["is_construction"])
    logger.info(
        f"\nSTAGE 1 COMPLETE: {len(all_tenders)} total awarded tenders, "
        f"{construction_count} construction/infra"
    )
    return all_tenders


# ===========================================================================
# STAGE 2: Scrape Opening Reports (bidders + values + winner)
# ===========================================================================

def scrape_opening_reports(session: requests.Session, tenders: list[dict], construction_only: bool = False) -> list[dict]:
    """Scrape Opening Report for each tender to get bidders, values, winner."""
    logger.info("STAGE 2: Scraping Opening Reports")

    # Load existing details if any
    existing_details = {}
    if os.path.exists(DETAILS_FILE):
        with open(DETAILS_FILE, encoding='utf-8') as f:
            existing = json.load(f)
        existing_details = {d["internal_id"]: d for d in existing}
        logger.info(f"Loaded {len(existing_details)} existing details")

    # Filter targets
    if construction_only:
        targets = [t for t in tenders if t["is_construction"] and t.get("internal_id")]
    else:
        targets = [t for t in tenders if t.get("internal_id")]

    # Skip already scraped
    targets = [t for t in targets if t["internal_id"] not in existing_details]
    logger.info(f"Targets: {len(targets)} tenders to scrape ({len(existing_details)} already done)")

    details = list(existing_details.values())
    scraped = 0
    errors = 0

    for i, tender in enumerate(targets):
        tid = tender["internal_id"]
        url = _opening_report_url(tid)
        r = _get(session, url, f"Opening Report {tid}")

        if not r:
            errors += 1
            if errors > 20:
                logger.error("Too many errors, stopping")
                break
            continue

        soup = BeautifulSoup(r.content, "html.parser")
        title = soup.title.get_text(strip=True) if soup.title else ""

        if "security" in title.lower() or "logged out" in title.lower():
            logger.warning(f"Blocked on {tid}")
            errors += 1
            time.sleep(5)
            continue

        # Parse bidders table
        bidders = []
        winner = None
        tables = soup.find_all("table")

        for table in tables:
            rows = table.find_all("tr")
            for row in rows[1:]:  # skip header
                cells = row.find_all("td")
                if len(cells) < 4:
                    continue

                company = cells[1].get_text(strip=True)
                offer_type = cells[2].get_text(strip=True) if len(cells) > 2 else ""
                value_text = cells[3].get_text(strip=True) if len(cells) > 3 else ""
                status = cells[4].get_text(strip=True) if len(cells) > 4 else ""

                # Parse value
                try:
                    value = float(value_text.replace(",", "")) if value_text else 0
                except (ValueError, TypeError):
                    value = 0

                # Check if this bidder is marked as winner
                # The portal marks the winner with "Awarded" in the company name cell
                is_winner = "awarded" in cells[1].get_text().lower()
                if is_winner:
                    # Clean the company name (remove "Awarded" text)
                    company = re.sub(r'\s*Awarded\s*', '', company, flags=re.IGNORECASE).strip()

                bidder = {
                    "company": company,
                    "offer_type": offer_type,
                    "quoted_value": value,
                    "status": status,
                    "is_winner": is_winner,
                }
                bidders.append(bidder)

                if is_winner:
                    winner = {
                        "company": company,
                        "value": value,
                    }

        detail = {
            "internal_id": tid,
            "tender_number": tender["tender_number"],
            "tender_title": tender["tender_title"],
            "entity": tender["entity"],
            "category": tender.get("category", ""),
            "grade": tender.get("grade", ""),
            "awarded_date": tender.get("awarded_date", ""),
            "is_construction": tender.get("is_construction", False),
            "bidders": bidders,
            "num_bidders": len(bidders),
            "winner": winner,
            "winning_value": winner["value"] if winner else None,
            "lowest_bid": min((b["quoted_value"] for b in bidders if b["quoted_value"] > 0), default=None),
            "highest_bid": max((b["quoted_value"] for b in bidders if b["quoted_value"] > 0), default=None),
            "scraped_at": datetime.now().isoformat(),
        }

        # Calculate bid spread
        if detail["lowest_bid"] and detail["highest_bid"] and detail["lowest_bid"] > 0:
            detail["bid_spread_pct"] = round(
                (detail["highest_bid"] - detail["lowest_bid"]) / detail["lowest_bid"] * 100, 1
            )
        else:
            detail["bid_spread_pct"] = None

        details.append(detail)
        scraped += 1
        errors = 0  # reset on success

        # Progress
        if scraped % 25 == 0:
            _save_json(details, DETAILS_FILE)
            winners_found = sum(1 for d in details if d["winner"])
            logger.info(
                f"Progress: {scraped}/{len(targets)} scraped | "
                f"Total details: {len(details)} | "
                f"Winners identified: {winners_found}"
            )

        time.sleep(DETAIL_DELAY)

    # Final save
    _save_json(details, DETAILS_FILE)
    winners_found = sum(1 for d in details if d["winner"])
    construction_with_details = sum(1 for d in details if d["is_construction"])

    logger.info(
        f"\nSTAGE 2 COMPLETE: {len(details)} tenders with bid details | "
        f"Winners identified: {winners_found} | "
        f"Construction: {construction_with_details}"
    )

    # Print summary stats
    if details:
        construction_details = [d for d in details if d["is_construction"] and d["winner"]]
        if construction_details:
            values = [d["winning_value"] for d in construction_details if d["winning_value"]]
            if values:
                print(f"\n  Construction contract values:")
                print(f"    Count: {len(values)}")
                print(f"    Min: OMR {min(values):,.2f}")
                print(f"    Max: OMR {max(values):,.2f}")
                print(f"    Avg: OMR {sum(values)/len(values):,.2f}")
                print(f"    Total: OMR {sum(values):,.2f}")

    return details


# ===========================================================================
# STAGE 3: Scrape Participation (doc purchases) for construction tenders
# ===========================================================================

def scrape_participation(session: requests.Session, tenders: list[dict]) -> list[dict]:
    """Scrape doc purchase details for construction tenders."""
    logger.info("STAGE 3: Scraping participation details (construction only)")

    targets = [t for t in tenders if t["is_construction"] and t.get("internal_id")]
    logger.info(f"Targets: {len(targets)} construction tenders")

    participation = []
    scraped = 0

    for tender in targets:
        tid = tender["internal_id"]
        url = _participation_url(tid)
        r = _get(session, url, f"Participation {tid}")

        if not r:
            continue

        soup = BeautifulSoup(r.content, "html.parser")

        purchasers = []
        tables = soup.find_all("table")

        for table in tables:
            rows = table.find_all("tr")
            for row in rows[1:]:
                cells = row.find_all("td")
                if len(cells) < 4:
                    continue

                purchaser = {
                    "reg_number": cells[1].get_text(strip=True) if len(cells) > 1 else "",
                    "company": cells[2].get_text(strip=True) if len(cells) > 2 else "",
                    "company_type": cells[3].get_text(strip=True) if len(cells) > 3 else "",
                    "purchase_datetime": cells[4].get_text(strip=True) if len(cells) > 4 else "",
                }
                if purchaser["company"]:
                    purchasers.append(purchaser)

        participation.append({
            "internal_id": tid,
            "tender_number": tender["tender_number"],
            "purchasers": purchasers,
            "num_purchasers": len(purchasers),
            "scraped_at": datetime.now().isoformat(),
        })

        scraped += 1
        if scraped % 25 == 0:
            logger.info(f"Participation progress: {scraped}/{len(targets)}")

        time.sleep(DELAY)

    output_file = os.path.join(OUTPUT_DIR, "awarded_participation.json")
    _save_json(participation, output_file)
    logger.info(f"STAGE 3 COMPLETE: {len(participation)} tenders with participation data")
    return participation


# ===========================================================================
# Helpers
# ===========================================================================

def _save_json(data, filepath):
    """Save data to JSON file."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"Saved {len(data)} records to {filepath}")


def _save_checkpoint(data):
    """Save scrape progress checkpoint."""
    os.makedirs(os.path.dirname(CHECKPOINT_FILE), exist_ok=True)
    data["timestamp"] = datetime.now().isoformat()
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(data, f, indent=2)


def print_summary(listing_file=LISTING_FILE, details_file=DETAILS_FILE):
    """Print a summary of scraped data."""
    print("\n" + "=" * 70)
    print("SCRAPE SUMMARY")
    print("=" * 70)

    if os.path.exists(listing_file):
        with open(listing_file, encoding='utf-8') as f:
            listing = json.load(f)
        total = len(listing)
        construction = sum(1 for t in listing if t.get("is_construction"))
        with_ids = sum(1 for t in listing if t.get("internal_id"))

        # Date range
        dates = [t["awarded_date"] for t in listing if t.get("awarded_date")]
        date_range = f"{dates[-1] if dates else '?'} to {dates[0] if dates else '?'}"

        print(f"\nListing: {total} awarded tenders")
        print(f"  Construction/infra: {construction}")
        print(f"  With internal IDs: {with_ids}")
        print(f"  Date range: {date_range}")

        # By category
        cats = {}
        for t in listing:
            cat = t.get("category", "Unknown")
            cats[cat] = cats.get(cat, 0) + 1
        print(f"\n  Top categories:")
        for cat, count in sorted(cats.items(), key=lambda x: -x[1])[:10]:
            print(f"    {cat[:50]}: {count}")

        # By entity
        entities = {}
        for t in listing:
            ent = t.get("entity", "Unknown")
            entities[ent] = entities.get(ent, 0) + 1
        print(f"\n  Top entities:")
        for ent, count in sorted(entities.items(), key=lambda x: -x[1])[:10]:
            print(f"    {ent[:50]}: {count}")

    if os.path.exists(details_file):
        with open(details_file, encoding='utf-8') as f:
            details = json.load(f)
        total = len(details)
        with_winners = sum(1 for d in details if d.get("winner"))
        construction = sum(1 for d in details if d.get("is_construction"))

        print(f"\nDetails: {total} tenders with bid data")
        print(f"  Winners identified: {with_winners}")
        print(f"  Construction: {construction}")

        # Competitor presence
        tracked = ["Galfar", "Strabag", "Al Tasnim", "Sarooj", "L&T",
                   "Towell", "Hassan Allam", "Arab Contractors", "Ozkar"]
        comp_wins = {c: 0 for c in tracked}
        comp_bids = {c: 0 for c in tracked}

        for d in details:
            for b in d.get("bidders", []):
                company = b.get("company", "").upper()
                for comp in tracked:
                    if comp.upper() in company:
                        comp_bids[comp] += 1
                        if b.get("is_winner"):
                            comp_wins[comp] += 1

        active_comps = {c: (comp_bids[c], comp_wins[c])
                       for c in tracked if comp_bids[c] > 0}
        if active_comps:
            print(f"\n  Tracked competitors in awarded data:")
            for comp, (bids, wins) in sorted(active_comps.items(), key=lambda x: -x[1][0]):
                win_rate = round(wins / bids * 100) if bids else 0
                print(f"    {comp}: {bids} bids, {wins} wins ({win_rate}% win rate)")


# ===========================================================================
# Main
# ===========================================================================

def main():
    parser = argparse.ArgumentParser(description="Scrape awarded tenders from Oman Tender Board")
    parser.add_argument("--listing-only", action="store_true", help="Only scrape listing pages")
    parser.add_argument("--details-only", action="store_true", help="Only scrape Opening Reports")
    parser.add_argument("--construction-only", action="store_true", help="Only scrape construction tenders")
    parser.add_argument("--from-page", type=int, default=1, help="Start listing from this page")
    parser.add_argument("--max-pages", type=int, default=300, help="Max listing pages to scrape")
    parser.add_argument("--summary", action="store_true", help="Just print summary of existing data")
    args = parser.parse_args()

    if args.summary:
        print_summary()
        return

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    session = requests.Session()
    session.headers.update(HEADERS)

    print("=" * 70)
    print("SCC AWARDED TENDER SCRAPER")
    print(f"Started: {datetime.now().isoformat()}")
    print("=" * 70)

    if args.details_only:
        # Load listing from file
        if not os.path.exists(LISTING_FILE):
            print(f"ERROR: {LISTING_FILE} not found. Run listing first.")
            sys.exit(1)
        with open(LISTING_FILE, encoding='utf-8') as f:
            tenders = json.load(f)
        scrape_opening_reports(session, tenders, construction_only=args.construction_only)
    else:
        # Stage 1: Listing
        tenders = scrape_listing(session, from_page=args.from_page, max_pages=args.max_pages)

        if not args.listing_only:
            # Stage 2: Opening Reports
            scrape_opening_reports(session, tenders, construction_only=args.construction_only)

            # Stage 3: Participation (construction only)
            if not args.construction_only:
                construction = [t for t in tenders if t["is_construction"]]
                if construction:
                    scrape_participation(session, construction)

    # Print summary
    print_summary()
    print(f"\nCompleted: {datetime.now().isoformat()}")


if __name__ == "__main__":
    main()
