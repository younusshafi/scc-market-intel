"""
Deep Tender Probe — fetches NIT details, opening status (bidder names),
and document purchase details for in-process tenders.

Searches for Sarooj (SCC) and tracked competitor participation.
"""

import hashlib
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

BASE = "https://etendering.tenderboard.gov.om"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(SCRIPT_DIR, "probe_deep")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
}

COMPETITORS = ["Sarooj", "سروج", "Galfar", "Strabag", "Al Tasnim", "Tasnim",
               "L&T", "Larsen", "Towell", "Hassan Allam", "Arab Contractors", "Ozkar"]

MAX_LISTING_PAGES = 5
MAX_DETAIL_FETCHES = 30
PAGE_DELAY = 1.0


def secure_url(path, params):
    """Build URL with encparam + hashval matching the portal's JS security."""
    full = dict(params)
    full["CTRL_STRDIRECTION"] = "LTR"
    full["randomno"] = "fixedrandomno"
    names = ",".join(full.keys())
    vals = "".join(v for v in full.values() if v)
    hashval = hashlib.sha256(vals.encode()).hexdigest()
    qs = "&".join(f"{k}={v}" for k, v in full.items())
    return f"{BASE}{path}?{qs}&encparam={names}&hashval={hashval}"


def save_html(name, content):
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, name)
    with open(path, "wb") as f:
        f.write(content if isinstance(content, bytes) else content.encode("utf-8"))


def fetch(session, url, label=""):
    """GET with retry."""
    for attempt in range(3):
        try:
            r = session.get(url, timeout=45)
            return r
        except requests.RequestException as e:
            if attempt < 2:
                print(f"    Retry {attempt+1}/2 for {label}: {e}")
                time.sleep(3)
            else:
                print(f"    FAILED {label}: {e}")
                return None


def is_blocked(soup):
    title = soup.title.get_text(strip=True).lower() if soup.title else ""
    return "security" in title or "error" in title


# ---------------------------------------------------------------------------
# STEP 1: Extract tender IDs from listing pages
# ---------------------------------------------------------------------------

def scrape_listing(session):
    print("=" * 70)
    print("STEP 1: Extracting tender IDs from InProcess listings")
    print("=" * 70)

    tenders = []
    for pg in range(1, MAX_LISTING_PAGES + 1):
        params = {"viewFlag": "InProcessTenders", "CTRL_STRDIRECTION": "LTR"}
        if pg > 1:
            params["pageNo"] = str(pg)

        r = fetch(session, f"{BASE}/product/publicDash?" + "&".join(f"{k}={v}" for k, v in params.items()),
                  f"listing page {pg}")
        if not r or r.status_code != 200:
            continue

        save_html(f"listing_p{pg}.html", r.content)
        soup = BeautifulSoup(r.content, "html.parser")
        tables = soup.find_all("table")
        dt = max(tables, key=lambda t: len(t.find_all("tr")))
        rows = dt.find_all("tr")

        for row in rows[1:]:
            cells = row.find_all("td")
            if len(cells) < 7:
                continue

            tender_no = re.sub(r"\s+", " ", cells[1].get_text(strip=True))
            tender_name = re.sub(r"\s+", " ", cells[2].get_text(strip=True))
            entity = re.sub(r"\s+", " ", cells[3].get_text(strip=True))
            category = re.sub(r"\s+", " ", cells[4].get_text(strip=True))

            # Extract internal IDs from onclick handlers
            internal_id = None
            has_opening = False
            has_nit = False

            for a in row.find_all("a", onclick=True):
                onclick = a["onclick"]
                m = re.search(r"getNit\('(\d+)'\)", onclick)
                if m:
                    internal_id = m.group(1)
                    has_nit = True
                m = re.search(r"showOpeningStatus_Report\('(\d+)'\)", onclick)
                if m:
                    internal_id = internal_id or m.group(1)
                    has_opening = True

            if internal_id:
                tenders.append({
                    "tender_number": tender_no,
                    "tender_name": tender_name[:80],
                    "entity": entity[:60],
                    "category": category[:60],
                    "internal_id": internal_id,
                    "has_nit": has_nit,
                    "has_opening": has_opening,
                })

        print(f"  Page {pg}: {len(rows)-1} rows, {len(tenders)} tenders so far")
        time.sleep(PAGE_DELAY)

    print(f"\n  Total tenders with IDs: {len(tenders)}")
    with_opening = sum(1 for t in tenders if t["has_opening"])
    print(f"  With opening status: {with_opening}")
    return tenders


# ---------------------------------------------------------------------------
# STEP 2: Fetch Opening Status (bidder names)
# ---------------------------------------------------------------------------

def fetch_opening_status(session, tenders):
    print(f"\n{'='*70}")
    print("STEP 2: Fetching Tender Opening Reports (bidder names)")
    print("=" * 70)

    candidates = [t for t in tenders if t["has_opening"]][:MAX_DETAIL_FETCHES]
    print(f"  Fetching {len(candidates)} opening reports...")

    all_bidders = []
    for i, t in enumerate(candidates):
        tid = t["internal_id"]
        url = secure_url("/product/tmsbidopen/TenderOpeningQCRStatusAction.action", {
            "callAction": "showOpeningStatus_public",
            "strTenderNo": tid,
            "PublicUrl": "1",
        })

        r = fetch(session, url, f"opening {tid}")
        if not r:
            continue

        save_html(f"opening_{tid}.html", r.content)
        soup = BeautifulSoup(r.content, "html.parser")

        if is_blocked(soup):
            print(f"  [{i+1}/{len(candidates)}] {tid} — BLOCKED")
            continue

        # Parse bidder table
        bidders = []
        for table in soup.find_all("table"):
            rows = table.find_all("tr")
            if len(rows) < 2:
                continue
            headers = [c.get_text(strip=True).lower() for c in rows[0].find_all(["th", "td"])]
            if "company name" not in " ".join(headers) and "company" not in " ".join(headers):
                continue

            for row in rows[1:]:
                cells = [c.get_text(strip=True) for c in row.find_all("td")]
                if len(cells) >= 3:
                    bidder = {
                        "company": cells[1] if len(cells) > 1 else "",
                        "offer_type": cells[2] if len(cells) > 2 else "",
                        "status": cells[3] if len(cells) > 3 else "",
                    }
                    if bidder["company"]:
                        bidders.append(bidder)

        t["bidders"] = bidders
        all_bidders.extend([(b["company"], t["tender_number"], t["tender_name"]) for b in bidders])

        if bidders:
            print(f"  [{i+1}/{len(candidates)}] {tid} — {len(bidders)} bidders: {', '.join(b['company'][:25] for b in bidders[:4])}")
        else:
            print(f"  [{i+1}/{len(candidates)}] {tid} — no bidders found")

        time.sleep(PAGE_DELAY)

    return all_bidders


# ---------------------------------------------------------------------------
# STEP 3: Fetch NIT details (for a sample)
# ---------------------------------------------------------------------------

def fetch_nit_details(session, tenders):
    print(f"\n{'='*70}")
    print("STEP 3: Fetching NIT details (sample of 5)")
    print("=" * 70)

    sample = [t for t in tenders if t["has_nit"]][:5]

    for i, t in enumerate(sample):
        tid = t["internal_id"]
        url = secure_url("/product/nitParameterView", {
            "mode": "public",
            "tenderNo": tid,
            "PublicUrl": "1",
        })

        r = fetch(session, url, f"NIT {tid}")
        if not r:
            continue

        save_html(f"nit_{tid}.html", r.content)
        soup = BeautifulSoup(r.content, "html.parser")

        if is_blocked(soup):
            print(f"  [{i+1}/5] {tid} — BLOCKED")
            continue

        # Extract key fields from NIT
        text = soup.get_text(separator="\n")
        nit_data = {}

        patterns = {
            "tender_title": r"Tender Title\s*:\s*(.+)",
            "evaluation_type": r"Evaluation Type\s*:\s*(.+)",
            "tender_type": r"Tender Type\s*:\s*(.+)",
            "category": r"Procurement Category\s*:\s*(.+)",
            "sub_category": r"Procurement Sub.*?Category\s*:\s*(.+)",
            "governorate": r"Governorate\s*:\s*(.+)",
            "wilayat": r"Wilayat\s*:\s*(.+)",
            "envelope_type": r"Envelope Type\s*:\s*(.+)",
            "scope_of_work": r"Scope.*?[Ww]ork\s*:\s*(.+)",
            "bid_bond": r"Bid Bond.*?:\s*(.+)",
        }

        for key, pat in patterns.items():
            m = re.search(pat, text)
            if m:
                val = re.sub(r"\s+", " ", m.group(1).strip())[:100]
                nit_data[key] = val

        t["nit_details"] = nit_data

        print(f"\n  [{i+1}/5] Tender {t['tender_number']} (ID: {tid})")
        for k, v in nit_data.items():
            print(f"    {k}: {v[:70]}")

        time.sleep(PAGE_DELAY)


# ---------------------------------------------------------------------------
# STEP 4: Search for Sarooj and competitors
# ---------------------------------------------------------------------------

def search_competitors(tenders, all_bidders):
    print(f"\n{'='*70}")
    print("STEP 4: Competitor Search")
    print("=" * 70)

    # Search in bidder names
    comp_appearances = defaultdict(list)

    for company, tender_no, tender_name in all_bidders:
        company_lower = company.lower()
        for comp in COMPETITORS:
            if comp.lower() in company_lower:
                comp_appearances[comp].append({
                    "company_full": company,
                    "tender_number": tender_no,
                    "tender_name": tender_name,
                    "role": "bidder",
                })

    # Summary
    print(f"\n  Total unique bidders found: {len(set(b[0] for b in all_bidders))}")
    print(f"  Total bid appearances: {len(all_bidders)}")

    print(f"\n  --- Competitor Appearances ---")
    for comp in COMPETITORS:
        appearances = comp_appearances.get(comp, [])
        if appearances:
            print(f"\n  *** {comp}: {len(appearances)} tender(s) ***")
            for a in appearances[:5]:
                print(f"    {a['role'].upper()}: {a['tender_number']} — {a['tender_name'][:50]}")
                print(f"      Full name: {a['company_full']}")
        else:
            print(f"  {comp}: not found")

    return comp_appearances


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    start = datetime.now()
    print("=" * 70)
    print("Deep Tender Probe — Bidder Discovery")
    print(f"Started: {start.strftime('%H:%M:%S')}")
    print("=" * 70)

    session = requests.Session()
    session.headers.update(HEADERS)
    print("Establishing session...")
    session.get(BASE, timeout=30)

    # Step 1
    tenders = scrape_listing(session)

    # Step 2
    all_bidders = fetch_opening_status(session, tenders)

    # Step 3
    fetch_nit_details(session, tenders)

    # Step 4
    comp_appearances = search_competitors(tenders, all_bidders)

    # Save results
    elapsed = (datetime.now() - start).total_seconds()
    output = {
        "probe_at": datetime.now().isoformat(),
        "elapsed_seconds": round(elapsed),
        "tenders_scanned": len(tenders),
        "tenders_with_bidders": sum(1 for t in tenders if t.get("bidders")),
        "total_bid_appearances": len(all_bidders),
        "unique_bidders": len(set(b[0] for b in all_bidders)),
        "competitor_appearances": {k: len(v) for k, v in comp_appearances.items()},
        "competitor_details": {k: v for k, v in comp_appearances.items()},
        "tenders": tenders,
    }

    out_path = os.path.join(SCRIPT_DIR, "deep_probe_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*70}")
    print(f"PROBE COMPLETE — {elapsed:.0f}s")
    print(f"{'='*70}")
    print(f"  Tenders scanned: {len(tenders)}")
    print(f"  Opening reports fetched: {sum(1 for t in tenders if t.get('bidders'))}")
    print(f"  Total bid appearances: {len(all_bidders)}")
    print(f"  Unique companies: {len(set(b[0] for b in all_bidders))}")
    print(f"  Saved to: deep_probe_results.json + probe_deep/")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        traceback.print_exc()
        sys.exit(1)
