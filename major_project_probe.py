"""
Major Project Intelligence Probe — finds and analyses the biggest tenders
on the Oman Tender Board portal.

Targets: fee >= 200 OMR (all categories) + fee >= 50 in Ports/Roads/Bridges/Dams/Pipeline.
For each, fetches Opening Report (bidders + values), Purchase Details, and NIT.
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
DELAY = 2.0

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
}

COMPETITORS = {
    "Sarooj":           ["sarooj", "سروج", "saroj"],
    "Galfar":           ["galfar"],
    "Strabag":          ["strabag"],
    "Al Tasnim":        ["tasnim"],
    "L&T":              ["l&t", "larsen", "l & t", "l and t"],
    "Towell":           ["towell", "tawel"],
    "Hassan Allam":     ["hassan allam", "hassanallam"],
    "Arab Contractors": ["arab contractor"],
    "Ozkar":            ["ozkar"],
}

INFRA_CAT_KW = ["Ports", "Roads", "Bridges", "Dams", "Pipeline",
                "مقاولات المواني", "مقاولات شبكات"]


def bi(t, f):
    return t.get(f"{f}_en") or t.get(f"{f}_ar") or t.get(f, "")


def parse_fee(t):
    fee = t.get("fee", "")
    if not fee or fee in ("N/A", "-"):
        return None
    m = re.search(r'[\d,]+\.?\d*', fee.replace(",", ""))
    return float(m.group()) if m else None


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
            return session.get(url, timeout=60)
        except requests.RequestException as e:
            if attempt < 2:
                print(f"      Retry {attempt+1}: {e}")
                time.sleep(5)
    print(f"      FAILED: {label}")
    return None


def is_blocked(soup):
    t = soup.title.get_text(strip=True).lower() if soup.title else ""
    return "security" in t or "error" in t


def match_competitor(name):
    low = name.lower()
    for comp, keywords in COMPETITORS.items():
        if any(kw in low for kw in keywords):
            return comp
    return None


def normalize_tnum(tn):
    """Extract core numeric parts for fuzzy matching."""
    # Remove whitespace, special chars; keep digits and slashes
    return re.sub(r'[^\d/]', '', tn)


# ---------------------------------------------------------------------------
# STEP 1: Identify target tenders from historical data
# ---------------------------------------------------------------------------

def load_targets():
    print("Loading historical_tenders.json...")
    with open(os.path.join(SCRIPT_DIR, "historical_tenders.json"), "r", encoding="utf-8") as f:
        data = json.load(f)

    targets = []
    for t in data["tenders"]:
        fee = parse_fee(t)
        if fee is None:
            continue
        cg = bi(t, "category_grade")
        is_infra = any(kw in cg for kw in INFRA_CAT_KW)

        if fee >= 200 or (fee >= 50 and is_infra):
            targets.append({
                "tender_number": t.get("tender_number", ""),
                "tender_number_en": t.get("tender_number_en", ""),
                "name": bi(t, "tender_name")[:80],
                "entity": bi(t, "entity")[:60],
                "category": bi(t, "category_grade")[:60],
                "fee": fee,
                "view": t.get("_view", ""),
                "dates": t.get("bid_closing_date") or t.get("sales_end_date") or "",
                # To be filled:
                "internal_id": None,
                "bidders": [],
                "purchasers": [],
                "nit": {},
            })

    targets.sort(key=lambda t: -t["fee"])
    print(f"  Target tenders: {len(targets)} (fee >= 200 or infra >= 50)")
    for t in targets[:5]:
        print(f"    Fee {t['fee']:>6.0f} | {t['tender_number'][:30]} | {t['name'][:40]}")
    return targets


# ---------------------------------------------------------------------------
# STEP 2: Scan listing pages to find internal IDs
# ---------------------------------------------------------------------------

def find_internal_ids(session, targets):
    print(f"\n{'='*70}")
    print("STEP 2: Scanning listing pages to find internal tender IDs")
    print("=" * 70)

    # Build lookup by normalized tender number
    lookup = {}
    for t in targets:
        for tn_field in ("tender_number", "tender_number_en"):
            tn = t.get(tn_field, "")
            if tn:
                norm = normalize_tnum(tn)
                if norm:
                    lookup[norm] = t

    found = 0
    needed = len(targets)

    # Scan both NewTenders and InProcessTenders
    for view_label, view_flag in [("InProcess", "InProcessTenders"), ("New", "NewTenders")]:
        if found >= needed:
            break

        print(f"\n  Scanning {view_label} listings...")
        for pg in range(1, 60):  # up to 60 pages
            if found >= needed:
                break

            params = {"viewFlag": view_flag, "CTRL_STRDIRECTION": "LTR"}
            if pg > 1:
                params["pageNo"] = str(pg)
            r = get(session, f"{BASE}/product/publicDash?" + "&".join(f"{k}={v}" for k, v in params.items()),
                    f"{view_label} page {pg}")
            if not r or r.status_code != 200:
                continue

            soup = BeautifulSoup(r.content, "html.parser")
            tables = soup.find_all("table")
            if len(tables) < 2:
                continue
            dt = max(tables, key=lambda t: len(t.find_all("tr")))
            page_found = 0

            for row in dt.find_all("tr")[1:]:
                cells = row.find_all("td")
                if len(cells) < 3:
                    continue
                row_tn = re.sub(r"\s+", " ", cells[1].get_text(strip=True))
                row_norm = normalize_tnum(row_tn)

                if row_norm in lookup and lookup[row_norm]["internal_id"] is None:
                    # Extract internal ID
                    for a in row.find_all("a", onclick=True):
                        m = re.search(r"getNit\('(\d+)'\)", a["onclick"])
                        if m:
                            lookup[row_norm]["internal_id"] = m.group(1)
                            found += 1
                            page_found += 1
                            break

            if pg % 10 == 0 or page_found > 0:
                print(f"    Page {pg}: +{page_found} IDs (total found: {found}/{needed})")

            time.sleep(DELAY)

    print(f"\n  Internal IDs found: {found} / {needed}")
    return [t for t in targets if t["internal_id"]]


# ---------------------------------------------------------------------------
# STEP 3: Fetch Opening Reports, Purchase Details, NIT
# ---------------------------------------------------------------------------

def fetch_details(session, targets):
    print(f"\n{'='*70}")
    print(f"STEP 3: Fetching details for {len(targets)} tenders")
    print("=" * 70)

    for i, t in enumerate(targets):
        tid = t["internal_id"]
        print(f"\n  [{i+1}/{len(targets)}] Fee {t['fee']:.0f} | {t['tender_number'][:30]} | {t['name'][:40]}")

        # Opening Report
        url = secure_url("/product/tmsbidopen/TenderOpeningQCRStatusAction.action", {
            "callAction": "showOpeningStatus_public", "strTenderNo": tid, "PublicUrl": "1",
        })
        r = get(session, url, f"opening {tid}")
        if r:
            save_html(f"major_opening_{tid}.html", r.content)
            soup = BeautifulSoup(r.content, "html.parser")
            if not is_blocked(soup):
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
                            t["bidders"].append({
                                "company": cells[1],
                                "offer_type": cells[2] if len(cells) > 2 else "",
                                "quoted_value": cells[3] if len(cells) > 3 else "",
                                "status": cells[4] if len(cells) > 4 else "",
                            })
        time.sleep(DELAY)

        # Document Purchase Details
        url2 = secure_url("/product/publicDash", {
            "viewFlag": "showParticipatedVendors", "tenderNo": tid, "PublicUrl": "1",
        })
        r2 = get(session, url2, f"purchase {tid}")
        if r2:
            save_html(f"major_purchase_{tid}.html", r2.content)
            soup2 = BeautifulSoup(r2.content, "html.parser")
            if not is_blocked(soup2):
                for table in soup2.find_all("table"):
                    rows = table.find_all("tr")
                    if len(rows) < 2:
                        continue
                    hdr = " ".join(c.get_text(strip=True).lower() for c in rows[0].find_all(["th", "td"]))
                    if "company" not in hdr:
                        continue
                    for row in rows[1:]:
                        cells = [c.get_text(strip=True) for c in row.find_all("td")]
                        if len(cells) >= 3 and cells[2]:
                            t["purchasers"].append({
                                "reg_number": cells[1],
                                "company": cells[2],
                                "company_type": cells[3] if len(cells) > 3 else "",
                                "purchase_date": cells[4] if len(cells) > 4 else "",
                            })
        time.sleep(DELAY)

        # NIT
        url3 = secure_url("/product/nitParameterView", {
            "mode": "public", "tenderNo": tid, "PublicUrl": "1",
        })
        r3 = get(session, url3, f"NIT {tid}")
        if r3:
            save_html(f"major_nit_{tid}.html", r3.content)
            soup3 = BeautifulSoup(r3.content, "html.parser")
            if not is_blocked(soup3):
                text = soup3.get_text(separator="\n")
                for key, pat in {
                    "title": r"Tender Title\s*:\s*(.+)",
                    "governorate": r"Governorate\s*:\s*(.+)",
                    "wilayat": r"Wilayat\s*:\s*(.+)",
                    "sub_category": r"Sub.*?Category\s*:\s*(.+)",
                    "scope": r"Scope.*?[Ww]ork\s*:\s*(.+)",
                    "bid_bond": r"Bid Bond.*?:\s*(.+)",
                    "envelope": r"Envelope Type\s*:\s*(.+)",
                }.items():
                    m = re.search(pat, text)
                    if m:
                        t["nit"][key] = re.sub(r"\s+", " ", m.group(1).strip())[:120]
        time.sleep(DELAY)

        # Summary line
        b = len(t["bidders"])
        p = len(t["purchasers"])
        loc = t["nit"].get("governorate", "")
        print(f"    Bidders: {b} | Purchasers: {p} | Location: {loc}")
        if b > 0:
            top = ", ".join(bd["company"][:25] for bd in t["bidders"][:4])
            print(f"    Top bidders: {top}")


# ---------------------------------------------------------------------------
# STEP 4: Competitor Analysis
# ---------------------------------------------------------------------------

def analyse(targets):
    print(f"\n{'='*70}")
    print("MAJOR PROJECT INTELLIGENCE REPORT")
    print("=" * 70)

    comp_bids = defaultdict(list)
    comp_purchases = defaultdict(list)

    # Collect all competitor appearances
    for t in targets:
        for b in t["bidders"]:
            comp = match_competitor(b["company"])
            if comp:
                comp_bids[comp].append({**b, "tender": t["tender_number"], "name": t["name"],
                                        "fee": t["fee"], "entity": t["entity"]})
        for p in t["purchasers"]:
            comp = match_competitor(p["company"])
            if comp:
                comp_purchases[comp].append({**p, "tender": t["tender_number"], "name": t["name"],
                                             "fee": t["fee"], "entity": t["entity"]})

    # Per-project report
    print(f"\n{'='*70}")
    print("PER-PROJECT BREAKDOWN")
    print("=" * 70)

    for t in targets:
        if not t["internal_id"]:
            continue
        b_count = len(t["bidders"])
        p_count = len(t["purchasers"])

        # Find competitors in this tender
        comps_here = set()
        for b in t["bidders"]:
            c = match_competitor(b["company"])
            if c:
                comps_here.add(f"{c} (BID: {b['quoted_value'] or '?'})")
        for p in t["purchasers"]:
            c = match_competitor(p["company"])
            if c:
                comps_here.add(f"{c} (DOC)")

        print(f"\n  Fee: {t['fee']:.0f} OMR | {t['tender_number']}")
        print(f"  {t['name']}")
        print(f"  Entity: {t['entity']} | {t['category'][:50]}")
        if t["nit"].get("governorate"):
            print(f"  Location: {t['nit']['governorate']}, {t['nit'].get('wilayat', '')}")
        if t["nit"].get("scope"):
            print(f"  Scope: {t['nit']['scope'][:80]}")
        print(f"  Purchasers: {p_count} | Bidders: {b_count}")
        if comps_here:
            print(f"  *** COMPETITORS: {' | '.join(comps_here)} ***")
        if b_count > 0:
            print(f"  All bidders:")
            for b in t["bidders"]:
                val = f" — {b['quoted_value']}" if b["quoted_value"] else ""
                comp_tag = f" [{'*** ' + match_competitor(b['company']) + ' ***' if match_competitor(b['company']) else ''}]"
                print(f"    {b['company'][:40]}{val}{comp_tag}")

    # Per-competitor report
    print(f"\n{'='*70}")
    print("PER-COMPETITOR SUMMARY")
    print("=" * 70)

    for comp in sorted(COMPETITORS.keys()):
        bids = comp_bids.get(comp, [])
        purchases = comp_purchases.get(comp, [])
        if not bids and not purchases:
            print(f"\n  {comp}: NOT FOUND in major projects")
            continue

        bid_tenders = {b["tender"] for b in bids}
        purchase_tenders = {p["tender"] for p in purchases}
        missed = purchase_tenders - bid_tenders

        print(f"\n  *** {comp} ***")
        print(f"    Documents purchased: {len(purchases)} tender(s)")
        print(f"    Bids submitted: {len(bids)} tender(s)")
        if purchases:
            rate = round(len(bid_tenders) / max(len(purchase_tenders), 1) * 100)
            print(f"    Conversion rate: {rate}%")
        if missed:
            print(f"    WITHDREW from: {', '.join(missed)}")

        for b in bids:
            val = f" — Quoted: {b['quoted_value']}" if b["quoted_value"] else ""
            print(f"    BID: {b['tender'][:30]} | {b['name'][:35]} | Fee {b['fee']:.0f}{val}")
        for p in purchases:
            if p["tender"] not in bid_tenders:
                print(f"    DOC ONLY: {p['tender'][:30]} | {p['name'][:35]} | Fee {p['fee']:.0f}")

    # Sarooj specific
    sarooj_bids = comp_bids.get("Sarooj", [])
    sarooj_purchases = comp_purchases.get("Sarooj", [])
    if sarooj_bids or sarooj_purchases:
        print(f"\n{'='*70}")
        print("SAROOJ (SCC) DETAILED ANALYSIS")
        print("=" * 70)
        for b in sarooj_bids:
            t_match = next((t for t in targets if t["tender_number"] == b["tender"]), None)
            if t_match:
                print(f"\n  Tender: {b['tender']} — {b['name']}")
                print(f"  Sarooj bid: {b['quoted_value'] or 'value not shown'}")
                print(f"  Competing against {len(t_match['bidders'])-1} others:")
                for ob in t_match["bidders"]:
                    if match_competitor(ob["company"]) != "Sarooj":
                        val = f" — {ob['quoted_value']}" if ob["quoted_value"] else ""
                        comp = match_competitor(ob["company"])
                        tag = f" [{comp}]" if comp else ""
                        print(f"    {ob['company'][:40]}{val}{tag}")

    return {"bids": comp_bids, "purchases": comp_purchases}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    start = datetime.now()
    print("=" * 70)
    print("Major Project Intelligence Probe")
    print(f"Started: {start.strftime('%H:%M:%S')}")
    print("=" * 70)

    session = requests.Session()
    session.headers.update(HEADERS)
    session.get(BASE, timeout=30)

    targets = load_targets()
    targets_with_ids = find_internal_ids(session, targets)
    print(f"\n  Targets with internal IDs: {len(targets_with_ids)}")

    if targets_with_ids:
        fetch_details(session, targets_with_ids)
        intel = analyse(targets_with_ids)

    elapsed = (datetime.now() - start).total_seconds()

    # Save
    output = {
        "probe_at": datetime.now().isoformat(),
        "elapsed_seconds": round(elapsed),
        "targets_identified": len(targets),
        "targets_with_ids": len(targets_with_ids),
        "targets_with_bidders": sum(1 for t in targets_with_ids if t["bidders"]),
        "tenders": [{k: v for k, v in t.items()} for t in targets_with_ids],
    }
    out_path = os.path.join(SCRIPT_DIR, "major_project_intelligence.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*70}")
    print(f"COMPLETE — {elapsed:.0f}s")
    print(f"  Targets: {len(targets)} | IDs found: {len(targets_with_ids)} | With bidders: {sum(1 for t in targets_with_ids if t['bidders'])}")
    print(f"  Saved to: major_project_intelligence.json")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
