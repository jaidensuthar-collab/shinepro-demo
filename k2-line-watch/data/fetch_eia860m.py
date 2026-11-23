"""Download the newest EIA-860M (monthly generator inventory) and keep only what the retirements list needs.

EIA-860M is the federal list of every U.S. power plant unit over 1 MW, updated monthly. Its "Operating" sheet gives
each unit's planned retirement month and year, and its "Retired" sheet lists units that have already retired.

Writes data/sources/eia860m-retirements.json with:
  - planned: operating units that have a planned retirement date (all states)
  - retired: units retired since 2023 (all states), the "3 years back" side of Line Watch's window
  - plants:  one entry per plant in the states listed in PLANT_STATES (name, owner, county, balancing area,
             location, MW by sheet), so ERCOT shutdown notices can be placed on the map

Usage: python3 data/fetch_eia860m.py [path/to/month_generatorYYYY.xlsx]
"""
import datetime as dt
import json
import os
import re
import sys
import urllib.request

import openpyxl

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "sources", "eia860m-retirements.json")
INDEX = "https://www.eia.gov/electricity/data/eia860m/"
UA = {"User-Agent": "K2-Line-Watch/1.0"}
RETIRED_SINCE = 2023
PLANT_STATES = {"TX", "OK"}


def latest_workbook(tmp_dir):
    page = urllib.request.urlopen(urllib.request.Request(INDEX, headers=UA), timeout=60).read().decode("utf-8", "ignore")
    links = re.findall(r'href="(/electricity/data/eia860m/(?:archive/)?xls/[a-z]+_generator\d{4}\.xlsx)"', page)
    for link in links:  # newest first on the page; some links are placeholders that redirect to a web page
        path = os.path.join(tmp_dir, os.path.basename(link))
        data = urllib.request.urlopen(urllib.request.Request("https://www.eia.gov" + link, headers=UA), timeout=300).read()
        if data[:2] == b"PK":
            open(path, "wb").write(data)
            return path, "https://www.eia.gov" + link
    raise RuntimeError("no EIA-860M workbook found on " + INDEX)


def rows(ws):
    it = ws.iter_rows(values_only=True)
    for r in it:
        if r and r[0] == "Entity ID":
            hdr = [str(h).strip() for h in r]
            break
    else:
        return
    for r in it:
        if not r or r[0] in (None, ""):
            continue
        yield {k: (v.strip() if isinstance(v, str) else v) for k, v in zip(hdr, r) if k not in ("Google Map", "Bing Map")}


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def main():
    tmp = os.path.join(HERE, "..", ".cache")
    os.makedirs(tmp, exist_ok=True)
    if len(sys.argv) > 1:
        path, url = sys.argv[1], INDEX
    else:
        path, url = latest_workbook(tmp)
    wb = openpyxl.load_workbook(path, read_only=True)
    title = next(wb["Operating"].iter_rows(values_only=True))[0] or ""
    as_of = re.sub(r"^.*as of\s+", "", str(title)).strip()
    planned, retired, plants = [], [], {}
    for sheet in ("Operating", "Retired", "Planned"):
        for d in rows(wb[sheet]):
            st = d.get("Plant State")
            if sheet == "Operating" and num(d.get("Planned Retirement Year")):
                planned.append(d)
            if sheet == "Retired" and (num(d.get("Retirement Year")) or 0) >= RETIRED_SINCE:
                retired.append(d)
            if st in PLANT_STATES:
                p = plants.setdefault(str(d["Plant ID"]), {
                    "id": d["Plant ID"], "name": d["Plant Name"], "owner": d["Entity Name"], "state": st,
                    "county": d["County"], "ba": d["Balancing Authority Code"],
                    "lat": num(d.get("Latitude")), "lon": num(d.get("Longitude")), "mw": {}})
                p["mw"][sheet] = round(p["mw"].get(sheet, 0) + (num(d.get("Nameplate Capacity (MW)")) or 0), 1)
                if p["lat"] is None and num(d.get("Latitude")) is not None:
                    p["lat"], p["lon"] = num(d.get("Latitude")), num(d.get("Longitude"))
    out = {"source": "EIA-860M Monthly Generator Inventory", "url": url, "as_of": as_of,
           "fetched": dt.date.today().isoformat(), "retired_since": RETIRED_SINCE,
           "planned": planned, "retired": retired, "plants": plants}
    json.dump(out, open(OUT, "w"), separators=(",", ":"), default=str)
    print("%s: %d planned retirements, %d retired since %d, %d plants in %s -> %s"
          % (as_of, len(planned), len(retired), RETIRED_SINCE, len(plants), "/".join(sorted(PLANT_STATES)), OUT))


if __name__ == "__main__":
    main()
