import json
from pathlib import Path

f = Path("scraped_data/galfar_financials_structured.json")
data = json.loads(f.read_text())

for period in ["2024_Annual", "2024_Q1", "2024_Q2"]:
    if "analysis" in data["periods"][period]:
        del data["periods"][period]["analysis"]
        print(f"Cleared {period}")

f.write_text(json.dumps(data, indent=2))
print("Done")
