import json

with open('scraped_data/awarded_tenders_details.json', encoding='utf-8') as f:
    data = json.load(f)

print(f"Total records: {len(data)}")
print(f"Winners found: {sum(1 for d in data if d.get('winner'))}")
print()

# Show first 5 tenders with bidders
for d in data[:5]:
    tn = d.get('tender_number', '?')
    bidders = d.get('bidders', [])
    winner = d.get('winner')
    print(f"Tender: {tn}")
    print(f"  Bidders: {len(bidders)} | Winner: {winner}")
    for b in bidders[:3]:
        company = b.get('company', '')[:60]
        value = b.get('quoted_value', 0)
        is_w = b.get('is_winner', False)
        print(f"    {company} | {value} | is_winner: {is_w}")
    print()

# Check if any company name contains "awarded" (case-insensitive)
awarded_found = 0
for d in data:
    for b in d.get('bidders', []):
        if 'awarded' in b.get('company', '').lower():
            awarded_found += 1
            if awarded_found <= 3:
                print(f"FOUND 'Awarded' in company: {b['company'][:80]}")
                print(f"  Tender: {d.get('tender_number')}")
                print(f"  is_winner flag: {b.get('is_winner')}")
                print()

print(f"\nTotal records with 'Awarded' in company name: {awarded_found}")
