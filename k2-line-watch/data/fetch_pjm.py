"""Fetch PJM's full transmission upgrade list (the data behind PJM's Project Construction page: every baseline,
supplemental and network upgrade with status, voltage, location and dates) and keep the rows Line Watch can use:
138 kV and up (by the voltage field or the description), not cancelled or withdrawn, and in service from 2023 on or
not yet in service. Writes sources/pjm-upgrades.json. The full XML is about 25 MB, so it is not kept.

    python3 data/fetch_pjm.py
"""
import datetime
import json
import os
import re
import urllib.request
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
URL = "https://www.pjm.com/pjmfiles/media/planning/projectConstruction-data/projectCostUpgrades.xml"
PAGE = "https://www.pjm.com/planning/m/project-construction"
OUT = os.path.join(HERE, "sources", "pjm-upgrades.json")
KEEP = ["UpgradeId", "SubRegion", "Description", "ProjectType", "Voltage", "TransmissionOwner", "State", "Location", "Equipment",
        "Status", "Driver", "ProjectedInServiceDate", "ActualInServiceDate", "RevisedInServiceDate", "RequiredDate",
        "ISAInServiceDate", "PJMBoardApprovalDate", "PercentComplete", "LastUpdated", "CostEstimate"]


def kv_of(r):
    nums = [int(n) for n in re.findall(r"\d+", r.get("Voltage") or "")] + \
           [int(n) for n in re.findall(r"(\d{2,3})\s*-?\s*kV", r.get("Description") or "", re.I)]
    return max(nums, default=0)


def date_of(s):
    try:
        return datetime.datetime.strptime(s, "%m/%d/%Y").date()
    except (TypeError, ValueError):
        return None


def main():
    req = urllib.request.Request(URL, headers={"User-Agent": "K2-Line-Watch/1.0"})
    root = ET.fromstring(urllib.request.urlopen(req, timeout=300).read())
    rows = []
    for u in root:
        r = {c.tag: (c.text or "").strip() for c in u}
        if r.get("Status") in ("Cancelled", "W") or kv_of(r) < 138:
            continue
        done = date_of(r.get("ActualInServiceDate"))
        if r.get("Status") == "IS" and (not done or done < datetime.date(2023, 1, 1)):
            continue
        rows.append({k: r.get(k, "") for k in KEEP})
    json.dump({"source": URL, "page": PAGE, "fetched": datetime.date.today().isoformat(), "count": len(rows), "upgrades": rows},
              open(OUT, "w"), separators=(",", ":"))
    print(len(rows), "PJM upgrades ->", OUT)


if __name__ == "__main__":
    main()
