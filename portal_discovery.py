"""
SCC Portal Discovery Script
Tests all known viewFlag values on the Tender Board portal to see
what data is accessible. Run locally — this just reads, doesn't store anything.

Usage: python portal_discovery.py
"""

import hashlib
import re
import time
import requests
from bs4 import BeautifulSoup

BASE = "https://etendering.tenderboard.gov.om"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
}

# Known viewFlags from the portal tabs
VIEW_FLAGS = [
    "NewTenders",           # Floated
    "InProcessTenders",     # Opened (bids received, under evaluation)
    "AwardedTenders",       # Awarded
    "CancelledTenders",     # Cancelled
    "SubContractTenders",   # Sub Contract Tenders
    # Possible variations — the portal might use different naming
    "Awarded",
    "Cancelled",
    "OpenedTenders",
    "ClosedTenders",
    "CompletedTenders",
    "SubContract",
    "RegisteredCompanies",
    "registeredCompanies",
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


def test_view_flag(session: requests.Session, view_flag: str) -> dict:
    """Test a single viewFlag and report what we find."""
    
    # Try both URL patterns — direct params and secure URL
    urls_to_try = [
        # Pattern 1: Simple publicDash (what the existing scraper uses)
        f"{BASE}/product/publicDash?viewFlag={view_flag}&CTRL_STRDIRECTION=LTR",
        # Pattern 2: With hash
        _secure_url("/product/publicDash", {"viewFlag": view_flag}),
        # Pattern 3: Different paths the portal might use
        f"{BASE}/product/{view_flag}?CTRL_STRDIRECTION=LTR",
    ]
    
    result = {
        "view_flag": view_flag,
        "status": "not_found",
        "rows": 0,
        "columns": [],
        "sample_data": [],
        "url_used": "",
        "pages_available": False,
    }
    
    for url in urls_to_try:
        try:
            r = session.get(url, timeout=30)
        except requests.RequestException as e:
            continue
            
        if r.status_code != 200:
            continue
        
        soup = BeautifulSoup(r.content, "html.parser")
        
        # Check for security block
        title = soup.title.get_text(strip=True).lower() if soup.title else ""
        if "security" in title or "error" in title:
            result["status"] = "blocked"
            continue
        
        # Find the main data table
        tables = soup.find_all("table")
        if not tables:
            continue
        
        # Get the largest table (likely the data table)
        data_table = max(tables, key=lambda tbl: len(tbl.find_all("tr")))
        rows = data_table.find_all("tr")
        
        if len(rows) < 2:
            continue
        
        # Extract column headers from first row
        header_row = rows[0]
        headers = [th.get_text(strip=True) for th in header_row.find_all(["th", "td"])]
        headers = [h for h in headers if h]  # Remove empty
        
        # Extract first 3 data rows as samples
        sample_rows = []
        for row in rows[1:4]:
            cells = row.find_all("td")
            cell_texts = [c.get_text(strip=True)[:80] for c in cells]
            if any(cell_texts):
                sample_rows.append(cell_texts)
        
        # Count total data rows
        data_rows = len(rows) - 1
        
        # Check for pagination
        page_links = soup.find_all("a", href=True)
        has_pagination = any("pageNo" in str(a) or "page" in str(a.get("onclick", "")).lower() 
                           for a in page_links)
        
        # Check for any onclick handlers that reveal detail endpoints
        onclick_patterns = set()
        for a in soup.find_all("a", onclick=True):
            onclick = a["onclick"]
            # Extract function names
            func_match = re.match(r"(\w+)\(", onclick)
            if func_match:
                onclick_patterns.add(func_match.group(1))
        
        result = {
            "view_flag": view_flag,
            "status": "accessible",
            "rows": data_rows,
            "columns": headers[:15],  # Cap at 15 columns
            "sample_data": sample_rows,
            "url_used": url[:120],
            "pages_available": has_pagination,
            "onclick_functions": list(onclick_patterns),
            "total_tables": len(tables),
        }
        break  # Found working URL, stop trying others
    
    return result


def discover_detail_endpoints(session: requests.Session):
    """Try to discover tender detail page endpoints for awarded tenders."""
    
    # Common detail page patterns on government portals
    detail_paths = [
        "/product/getAwardDetails",
        "/product/getAwardedNit",
        "/product/awardDetails",
        "/product/getNit",          # Known to work for active tenders
        "/product/getBidDetails",
        "/product/getOpeningReport",  # Known to work for bid opening
        "/product/getPurchaseDetails",  # Known to work for doc purchases
        "/product/getCompanyDetails",
        "/product/getRegisteredCompanies",
        "/product/companyList",
    ]
    
    print("\n" + "=" * 70)
    print("DETAIL ENDPOINT DISCOVERY")
    print("=" * 70)
    
    for path in detail_paths:
        url = f"{BASE}{path}?CTRL_STRDIRECTION=LTR"
        try:
            r = session.get(url, timeout=15)
            status = r.status_code
            content_len = len(r.content)
            # Check if it returns something meaningful
            has_html = "<table" in r.text.lower() or "<div" in r.text.lower()
            title = ""
            if has_html:
                soup = BeautifulSoup(r.content, "html.parser")
                title = soup.title.get_text(strip=True)[:60] if soup.title else ""
            
            indicator = "✓" if status == 200 and content_len > 500 else "✗"
            print(f"  {indicator} {path}")
            print(f"    Status: {status} | Size: {content_len} bytes | Title: {title}")
        except requests.RequestException as e:
            print(f"  ✗ {path} — {e}")
        
        time.sleep(1)


def main():
    session = requests.Session()
    session.headers.update(HEADERS)
    
    print("=" * 70)
    print("SCC PORTAL DISCOVERY — Tender Board Data Access Audit")
    print("=" * 70)
    print(f"Base: {BASE}")
    print()
    
    results = []
    
    for vf in VIEW_FLAGS:
        print(f"\nTesting viewFlag: {vf}...")
        result = test_view_flag(session, vf)
        results.append(result)
        
        if result["status"] == "accessible":
            print(f"  ✓ ACCESSIBLE — {result['rows']} rows on page 1")
            print(f"    Pagination: {'Yes' if result['pages_available'] else 'No'}")
            print(f"    Columns: {result['columns'][:8]}")
            if result.get("onclick_functions"):
                print(f"    Detail functions: {result['onclick_functions']}")
            if result["sample_data"]:
                print(f"    Sample row 1: {result['sample_data'][0][:6]}")
        elif result["status"] == "blocked":
            print(f"  ✗ BLOCKED by security")
        else:
            print(f"  — Not found / empty")
        
        time.sleep(2)  # Be polite
    
    # Try detail endpoints
    discover_detail_endpoints(session)
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    accessible = [r for r in results if r["status"] == "accessible"]
    print(f"\nAccessible viewFlags: {len(accessible)} of {len(VIEW_FLAGS)} tested")
    for r in accessible:
        print(f"  ✓ {r['view_flag']}: {r['rows']} rows, {len(r['columns'])} columns")
        print(f"    Columns: {', '.join(r['columns'][:10])}")
    
    blocked = [r for r in results if r["status"] == "blocked"]
    if blocked:
        print(f"\nBlocked: {[r['view_flag'] for r in blocked]}")
    
    not_found = [r for r in results if r["status"] == "not_found"]
    if not_found:
        print(f"\nNot found: {[r['view_flag'] for r in not_found]}")


if __name__ == "__main__":
    main()
