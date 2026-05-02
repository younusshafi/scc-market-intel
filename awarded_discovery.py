"""Check awarded tender pagination depth and detail link patterns."""

import hashlib
import re
import requests
from bs4 import BeautifulSoup

BASE = "https://etendering.tenderboard.gov.om"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def secure_url(path, params):
    full = dict(params)
    full["CTRL_STRDIRECTION"] = "LTR"
    full["randomno"] = "fixedrandomno"
    names = ",".join(full.keys())
    vals = "".join(v for v in full.values() if v)
    hv = hashlib.sha256(vals.encode()).hexdigest()
    qs = "&".join(f"{k}={v}" for k, v in full.items())
    return f"{BASE}{path}?{qs}&encparam={names}&hashval={hv}"


def main():
    s = requests.Session()
    s.headers.update(HEADERS)

    # 1. Check total pages of awarded tenders
    print("=== AWARDED: Checking depth ===")
    for pg in [1, 2, 5, 10, 20, 50, 100]:
        url = secure_url("/product/CompletedTendersForPublic", {"pageNo": str(pg)})
        r = s.get(url, timeout=30)
        soup = BeautifulSoup(r.content, "html.parser")
        tables = soup.find_all("table")
        if tables:
            dt = max(tables, key=lambda t: len(t.find_all("tr")))
            rows = len(dt.find_all("tr")) - 1
            print(f"  Page {pg}: {rows} rows")
            if rows == 0:
                print(f"  -> Last page with data is before page {pg}")
                break
        else:
            print(f"  Page {pg}: no tables")
            break

    # 2. Get detail link pattern from first awarded tender
    print("\n=== AWARDED: Detail link discovery ===")
    url = secure_url("/product/CompletedTendersForPublic", {"pageNo": "1"})
    r = s.get(url, timeout=30)
    soup = BeautifulSoup(r.content, "html.parser")
    tables = soup.find_all("table")
    dt = max(tables, key=lambda t: len(t.find_all("tr")))
    rows = dt.find_all("tr")

    # Check first 3 data rows for onclick/href patterns
    for i, row in enumerate(rows[1:4], 1):
        print(f"\n  Row {i}:")
        cells = row.find_all("td")
        if cells:
            tender_no = cells[1].get_text(strip=True)[:50] if len(cells) > 1 else "?"
            title = cells[2].get_text(strip=True)[:50] if len(cells) > 2 else "?"
            print(f"    Tender: {tender_no}")
            print(f"    Title: {title}")

        for a in row.find_all("a"):
            onclick = a.get("onclick", "")
            href = a.get("href", "")
            text = a.get_text(strip=True)[:30]
            if onclick:
                print(f"    onclick: {onclick[:150]}")
            if href and href != "#" and "javascript" not in href.lower():
                print(f"    href: {href[:150]}")
            if text:
                print(f"    link text: {text}")

    # 3. All unique onclick functions on the page
    patterns = set()
    for a in soup.find_all("a", onclick=True):
        m = re.match(r"(\w+)\(", a["onclick"])
        if m:
            patterns.add(m.group(1))
    print(f"\n  All onclick functions: {patterns}")

    # 4. Also check cancelled depth
    print("\n=== CANCELLED: Checking depth ===")
    for pg in [1, 5, 10, 20]:
        url = secure_url("/product/CanceledTendersForPublic", {"pageNo": str(pg)})
        r = s.get(url, timeout=30)
        soup = BeautifulSoup(r.content, "html.parser")
        tables = soup.find_all("table")
        if tables:
            dt = max(tables, key=lambda t: len(t.find_all("tr")))
            rows = len(dt.find_all("tr")) - 1
            print(f"  Page {pg}: {rows} rows")
            if rows == 0:
                print(f"  -> Last page with data is before page {pg}")
                break
        else:
            print(f"  Page {pg}: no tables")
            break


if __name__ == "__main__":
    main()
