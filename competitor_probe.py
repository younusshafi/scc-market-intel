"""
Competitor Intelligence Probe — scans construction/infrastructure tenders
for bidder names, quoted values, and competitor participation.

Targets: SCC-relevant categories only (Construction, Roads, Bridges, Dams,
Pipelines, Electromechanical, Ports).
"""

import hashlib
import json
import os
import re
import sys
import time
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

CAT_KEYWORDS = ["Construction", "Electromechanical", "Ports", "Roads",
                "Bridges", "Pipeline", "Dams", "Marine"]

COMPETITORS = {
    "Sarooj":           ["sarooj", "سروج"],
    "Galfar":           ["galfar"],
    "Strabag":          ["strabag"],
    "Al Tasnim":        ["tasnim"],
    "L&T":              ["l&t", "larsen", "l & t"],
    "Towell":           ["towell"],
    "Hassan Allam":     ["hassan allam"],
    "Arab Contractors": ["arab contractor"],
    "Ozkar":            ["ozkar"],
}

MAX_LISTING_PAGES = 20
MAX_PROBES = 50
DELAY = 1.0


def secure_url(path, params):
    full = dict(params)
    full["CTRL_STRDIRECTION"] = "LTR"
    full["randomno"] = "fixedrandomno"
    names = ",".join(full.keys())
    vals = "".join(v for v in full.values() if v)
    hv = hashlib.sha256(vals.encode()).hexdigest()
    qs = "&".join(f"{k}={v}" for k, v in full.items())
    return f"{BASE}{path}?{qs}&encparam={names}&hashval={hv}"


def save_html(name, content):
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, name), "wb") as f:
        f.write(content if isinstance(content, bytes) else content.encode("utf-8"))


def get(session, url, label=""):
    for attempt in range(3):
        try:
            return session.get(url, timeout=45)
        except requests.RequestException as e:
            if attempt < 2:
                print(f"      Retry {attempt+1}: {e}")
                time.sleep(3)
    print(f"      FAILED: {label}")
    return None


def is_blocked(soup):
    t = soup.title.get_text(strip=True).lower() if soup.title else ""
    return "security" in t or "error" in t


def match_competitor(name):
    """Return competitor name if matched, else None."""
    low = name.lower()
    for comp, keywords in COMPETITORS.items():
        if any(kw in low for kw in keywords):
            return comp
    return None


# ---------------------------------------------------------------------------
# STEP 1: Find construction tenders with internal IDs
# ---------------------------------------------------------------------------

def scan_listings(session):
    print("=" * 70)
    print("STEP 1: Scanning InProcess listings for construction tenders")
    print("=" * 70)

    found = []
    for pg in range(1, MAX_LISTING_PAGES + 1):
        params = {"viewFlag": "InProcessTenders", "CTRL_STRDIRECTION": "LTR"}
        if pg > 1:
            params["pageNo"] = str(pg)
        r = get(session, f"{BASE}/product/publicDash?" + "&".join(f"{k}={v}" for k, v in params.items()),
                f"page {pg}")
        if not r or r.status_code != 200:
            continue

        soup = BeautifulSoup(r.content, "html.parser")
        tables = soup.find_all("table")
        if len(tables) < 2:
            continue
        dt = max(tables, key=lambda t: len(t.find_all("tr")))
        page_hits = 0

        for row in dt.find_all("tr")[1:]:
            cells = row.find_all("td")
            if len(cells) < 5:
                continue
            cat = cells[4].get_text(strip=True)
            if not any(kw in cat for kw in CAT_KEYWORDS):
                continue

            tid = None
            for a in row.find_all("a", onclick=True):
                m = re.search(r"getNit\('(\d+)'\)", a["onclick"])
                if m:
                    tid = m.group(1)
            if not tid:
                continue

            tender_no = re.sub(r"\s+", " ", cells[1].get_text(strip=True))
            tender_name = re.sub(r"\s+", " ", cells[2].get_text(strip=True))[:80]
            entity = re.sub(r"\s+", " ", cells[3].get_text(strip=True))[:60]

            found.append({
                "id": tid,
                "tender_number": tender_no,
                "tender_name": tender_name,
                "entity": entity,
                "category": cat[:60],
                "bidders": [],
                "purchasers": [],
                "nit": {},
            })
            page_hits += 1

        total_rows = len(dt.find_all("tr")) - 1
        if pg % 5 == 0 or pg == MAX_LISTING_PAGES:
            print(f"  Page {pg}/{MAX_LISTING_PAGES}: {page_hits} construction tenders (total found: {len(found)})")

        if len(found) >= MAX_PROBES:
            print(f"  Reached {MAX_PROBES} cap, stopping listing scan.")
            break

        time.sleep(DELAY)

    found = found[:MAX_PROBES]
    print(f"\n  Construction tenders found: {len(found)}")
    return found


# ---------------------------------------------------------------------------
# STEP 2: Fetch Opening Reports (bidder names + quoted values)
# ---------------------------------------------------------------------------

def fetch_opening_reports(session, tenders):
    print(f"\n{'='*70}")
    print("STEP 2: Fetching Opening Reports (bidders + quoted values)")
    print("=" * 70)

    total_bidders = 0
    for i, t in enumerate(tenders):
        url = secure_url("/product/tmsbidopen/TenderOpeningQCRStatusAction.action", {
            "callAction": "showOpeningStatus_public",
            "strTenderNo": t["id"],
            "PublicUrl": "1",
        })
        r = get(session, url, f"opening {t['id']}")
        if not r:
            continue

        save_html(f"opening_{t['id']}.html", r.content)
        soup = BeautifulSoup(r.content, "html.parser")
        if is_blocked(soup):
            continue

        for table in soup.find_all("table"):
            rows = table.find_all("tr")
            if len(rows) < 2:
                continue
            headers = [c.get_text(strip=True).lower() for c in rows[0].find_all(["th", "td"])]
            if "company name" not in " ".join(headers):
                continue

            for row in rows[1:]:
                cells = [c.get_text(strip=True) for c in row.find_all("td")]
                if len(cells) >= 3 and cells[1]:
                    bidder = {
                        "company": cells[1],
                        "offer_type": cells[2] if len(cells) > 2 else "",
                        "quoted_value": cells[3] if len(cells) > 3 else "",
                        "status": cells[4] if len(cells) > 4 else "",
                    }
                    t["bidders"].append(bidder)

        total_bidders += len(t["bidders"])
        n_bid = len(t["bidders"])
        top_names = ", ".join(b["company"][:20] for b in t["bidders"][:3])
        extra = f"+ {n_bid-3} more" if n_bid > 3 else ""

        if (i + 1) % 10 == 0 or i == len(tenders) - 1:
            print(f"  [{i+1}/{len(tenders)}] {total_bidders} total bidders so far")

        if n_bid > 0 and (i + 1) <= 5:
            print(f"    {t['id']}: {n_bid} bidders — {top_names} {extra}")

        time.sleep(DELAY)

    print(f"\n  Total bid appearances: {total_bidders}")


# ---------------------------------------------------------------------------
# STEP 3: Fetch Document Purchase Details
# ---------------------------------------------------------------------------

def fetch_purchase_details(session, tenders):
    print(f"\n{'='*70}")
    print("STEP 3: Fetching Document Purchase Details")
    print("=" * 70)

    total_purchasers = 0
    for i, t in enumerate(tenders):
        url = secure_url("/product/publicDash", {
            "viewFlag": "showParticipatedVendors",
            "tenderNo": t["id"],
            "PublicUrl": "1",
        })
        r = get(session, url, f"purchase {t['id']}")
        if not r:
            continue

        soup = BeautifulSoup(r.content, "html.parser")
        if is_blocked(soup):
            continue

        for table in soup.find_all("table"):
            rows = table.find_all("tr")
            if len(rows) < 2:
                continue
            headers = [c.get_text(strip=True).lower() for c in rows[0].find_all(["th", "td"])]
            if "company name" not in " ".join(headers):
                continue

            for row in rows[1:]:
                cells = [c.get_text(strip=True) for c in row.find_all("td")]
                if len(cells) >= 3 and cells[2]:
                    purchaser = {
                        "reg_number": cells[1] if len(cells) > 1 else "",
                        "company": cells[2],
                        "company_type": cells[3] if len(cells) > 3 else "",
                        "purchase_date": cells[4] if len(cells) > 4 else "",
                    }
                    t["purchasers"].append(purchaser)

        total_purchasers += len(t["purchasers"])

        if (i + 1) % 10 == 0 or i == len(tenders) - 1:
            print(f"  [{i+1}/{len(tenders)}] {total_purchasers} total purchasers so far")

        time.sleep(DELAY)

    print(f"\n  Total document purchasers: {total_purchasers}")


# ---------------------------------------------------------------------------
# STEP 4: Fetch NIT details (sample)
# ---------------------------------------------------------------------------

def fetch_nit_sample(session, tenders):
    print(f"\n{'='*70}")
    print("STEP 4: Fetching NIT details (first 10)")
    print("=" * 70)

    for i, t in enumerate(tenders[:10]):
        url = secure_url("/product/nitParameterView", {
            "mode": "public", "tenderNo": t["id"], "PublicUrl": "1",
        })
        r = get(session, url, f"NIT {t['id']}")
        if not r:
            continue
        soup = BeautifulSoup(r.content, "html.parser")
        if is_blocked(soup):
            continue

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
                t["nit"][key] = re.sub(r"\s+", " ", m.group(1).strip())[:100]

        print(f"  [{i+1}] {t['tender_number']} — {t['nit'].get('title', t['tender_name'])[:50]}")
        if t["nit"].get("governorate"):
            print(f"      Location: {t['nit']['governorate']}, {t['nit'].get('wilayat', '')}")
        if t["nit"].get("scope"):
            print(f"      Scope: {t['nit']['scope'][:70]}")

        time.sleep(DELAY)


# ---------------------------------------------------------------------------
# STEP 5: Competitor analysis
# ---------------------------------------------------------------------------

def analyse_competitors(tenders):
    print(f"\n{'='*70}")
    print("STEP 5: Competitor Intelligence Report")
    print("=" * 70)

    comp_bids = defaultdict(list)       # comp -> [{tender, value, ...}]
    comp_purchases = defaultdict(list)   # comp -> [{tender, ...}]
    tender_competition = []              # (tender, bidder_count)
    all_companies = set()

    for t in tenders:
        bid_count = len(t["bidders"])
        if bid_count > 0:
            tender_competition.append((t, bid_count))

        for b in t["bidders"]:
            all_companies.add(b["company"])
            comp = match_competitor(b["company"])
            if comp:
                comp_bids[comp].append({
                    "tender_number": t["tender_number"],
                    "tender_name": t["tender_name"],
                    "entity": t["entity"],
                    "company_full": b["company"],
                    "quoted_value": b["quoted_value"],
                    "status": b["status"],
                    "role": "bidder",
                })

        for p in t["purchasers"]:
            all_companies.add(p["company"])
            comp = match_competitor(p["company"])
            if comp:
                comp_purchases[comp].append({
                    "tender_number": t["tender_number"],
                    "tender_name": t["tender_name"],
                    "company_full": p["company"],
                    "purchase_date": p["purchase_date"],
                    "role": "document_purchaser",
                })

    # Report
    print(f"\n  Unique companies across all probed tenders: {len(all_companies)}")
    print(f"  Tenders with bidder data: {len(tender_competition)}")

    # Competition intensity
    tender_competition.sort(key=lambda x: -x[1])
    print(f"\n  --- Most Competitive Tenders (by bidder count) ---")
    for t, count in tender_competition[:10]:
        print(f"    {count:>3} bidders | {t['tender_number']} — {t['tender_name'][:45]} [{t['entity'][:25]}]")

    # Competitor details
    print(f"\n  --- Competitor Participation Summary ---")
    all_comps = set(list(comp_bids.keys()) + list(comp_purchases.keys()))
    for comp in sorted(COMPETITORS.keys()):
        bids = comp_bids.get(comp, [])
        purchases = comp_purchases.get(comp, [])

        if not bids and not purchases:
            print(f"    {comp}: NOT FOUND in {len(tenders)} construction tenders")
            continue

        print(f"\n  *** {comp} ***")
        if bids:
            print(f"    Bid on {len(bids)} tender(s):")
            for b in bids:
                val = f" — Quoted: {b['quoted_value']}" if b["quoted_value"] else ""
                print(f"      {b['tender_number']} | {b['tender_name'][:40]} | {b['entity'][:25]}{val}")

        if purchases:
            print(f"    Purchased documents for {len(purchases)} tender(s):")
            for p in purchases:
                print(f"      {p['tender_number']} | {p['tender_name'][:40]} | Date: {p['purchase_date']}")

        # Check for doc-purchase-but-no-bid (missed opportunity)
        bid_tenders = {b["tender_number"] for b in bids}
        purchase_tenders = {p["tender_number"] for p in purchases}
        missed = purchase_tenders - bid_tenders
        if missed:
            print(f"    ⚠ Purchased docs but DID NOT BID on {len(missed)} tender(s): {missed}")

    return {
        "competitor_bids": {k: v for k, v in comp_bids.items()},
        "competitor_purchases": {k: v for k, v in comp_purchases.items()},
        "competition_ranking": [(t["tender_number"], c) for t, c in tender_competition[:20]],
        "unique_companies": len(all_companies),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    start = datetime.now()
    print("=" * 70)
    print("Competitor Intelligence Probe — Construction Tenders")
    print(f"Started: {start.strftime('%H:%M:%S')}")
    print("=" * 70)

    session = requests.Session()
    session.headers.update(HEADERS)
    session.get(BASE, timeout=30)

    tenders = scan_listings(session)
    if not tenders:
        print("No construction tenders found.")
        return

    fetch_opening_reports(session, tenders)
    fetch_purchase_details(session, tenders)
    fetch_nit_sample(session, tenders)
    intel = analyse_competitors(tenders)

    elapsed = (datetime.now() - start).total_seconds()

    output = {
        "probe_at": datetime.now().isoformat(),
        "elapsed_seconds": round(elapsed),
        "construction_tenders_probed": len(tenders),
        "tenders_with_bidders": sum(1 for t in tenders if t["bidders"]),
        "tenders_with_purchasers": sum(1 for t in tenders if t["purchasers"]),
        "unique_companies": intel["unique_companies"],
        "competitor_summary": {k: len(v) for k, v in intel["competitor_bids"].items()},
        "competitor_bids": intel["competitor_bids"],
        "competitor_purchases": intel["competitor_purchases"],
        "competition_ranking": intel["competition_ranking"],
        "tenders": tenders,
    }

    out_path = os.path.join(SCRIPT_DIR, "competitor_intelligence.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*70}")
    print(f"COMPLETE — {elapsed:.0f}s")
    print(f"{'='*70}")
    print(f"  Construction tenders probed: {len(tenders)}")
    print(f"  With bidder data: {sum(1 for t in tenders if t['bidders'])}")
    print(f"  With purchaser data: {sum(1 for t in tenders if t['purchasers'])}")
    print(f"  Unique companies found: {intel['unique_companies']}")
    print(f"  Saved to: competitor_intelligence.json")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
