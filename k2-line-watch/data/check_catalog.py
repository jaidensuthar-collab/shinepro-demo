"""Check the Texas line catalog against its sources before it is published.

    python3 check_catalog.py            # prints the report, exits 1 if any check fails

What it checks (errors fail the run, warnings are listed for a person to look at):
  1. Every ERCOT line matches its row in the ERCOT TPIT edition it came from: voltage, in-service date, and a stage
     that agrees with ERCOT's status.
  2. The time window: built lines have an actual in-service date in the last 3 years; nothing else is due after the
     5-year horizon.
  3. Locations: every point is in Texas, and every exact or approximate substation point is in (or next to) the
     county ERCOT lists for it.
  4. Substation status agrees between the lines and the substation table (there now, work, stage).
  5. The downloads agree with the page data: line and substation counts, every field present, the KML opens.
  6. Every project on Oncor's CCN Public Viewer is in the list.
The summary is written into web/data/texas-lines.json ("checks") so the page shows when it was last checked.
"""
import csv
import datetime
import json
import math
import os
import sys
import xml.etree.ElementTree as ET

import build_catalog as B

WEB = B.WEB
TX_BOX = (-106.7, 25.8, -93.5, 36.6)


def miles(a, b):
    dy = (a[1] - b[1]) * 69.0
    dx = (a[0] - b[0]) * 69.0 * math.cos(math.radians((a[1] + b[1]) / 2))
    return math.hypot(dx, dy)


class Report:
    def __init__(self):
        self.checks = []

    def add(self, name, errors, warnings=(), checked=0):
        self.checks.append({"check": name, "checked": checked, "errors": list(errors), "warnings": list(warnings)})


def check_tpit(lines, r):
    rows = {}
    for fname, label in [("ercot-tpit-2026-10.xlsx", "October 1, 2026")] + B.HISTORY:
        path = os.path.join(B.HERE, "sources", fname)
        for row in B.read_tpit(path) if os.path.exists(path) else []:
            rows.setdefault(label, {})[str(row["id"]).strip()] = row
    errs, warns, n = [], [], 0
    expect = {"in-service": {"built"}, "under construction": {"in construction"}, "conceptual": {"proposed"},
              "planned": {"approved", "planned", "in construction"}}
    for x in lines:
        if not x["id"].startswith("tpit-"):
            continue
        label = next((k for k in rows if k in x["source"]), None)
        row = rows.get(label, {}).get(x["ercot_project"])
        if not row:
            errs.append(f"{x['id']} {x['name']}: not found in the ERCOT TPIT edition it cites")
            continue
        n += 1
        if int(B.num(row["kv"])) != x["kv"]:
            errs.append(f"{x['id']} {x['name']}: {x['kv']} kV here, {row['kv']} kV in ERCOT's report")
        when = B.ym(row["actual"]) or B.ym(row["isd"])
        if when != x["in_service"]:
            errs.append(f"{x['id']} {x['name']}: in service {x['in_service'] or 'blank'} here, {when or 'blank'} in ERCOT's report")
        status = str(row["status"] or "").lower() or ("in-service" if row["tab"] == "Completed" else "")
        ok = expect.get(status)
        if row["tab"] == "Completed":
            ok = {"built"}
        if row["actual"] and x["lifecycle"] == "built" and status != "in-service" and row["tab"] != "Completed":
            warns.append(f"{x['id']} {x['name']}: ERCOT gives an actual in-service date ({B.ym(row['actual'])}) but its status still says "
                         f"'{row['status']}'; counted as built")
            continue
        if ok and x["lifecycle"] not in ok and not x["lifecycle_basis"].startswith(("estimated", "PUC approved", "Line Watch card")):
            errs.append(f"{x['id']} {x['name']}: stage '{x['lifecycle']}' but ERCOT says '{row['status']}'")
        if x["lifecycle_basis"].startswith("estimated"):
            warns.append(f"{x['id']} {x['name']}: stage '{x['lifecycle']}' is estimated ({x['lifecycle_basis']})")
    r.add("Lines match ERCOT's report (voltage, in-service date, stage)", errs, warns, n)


def check_window(lines, meta, r):
    errs = []
    cutoff, horizon = meta["cutoff"][:7], meta["horizon"]
    for x in lines:
        if x["lifecycle"] not in B.STAGES:
            errs.append(f"{x['id']}: unknown stage '{x['lifecycle']}'")
        if x["lifecycle"] == "built" and (not x["in_service"] or x["in_service"] < cutoff):
            errs.append(f"{x['id']} {x['name']}: built {x['in_service'] or 'with no date'}, before {cutoff}")
        if x["in_service"] and x["in_service"][:7] > horizon:
            errs.append(f"{x['id']} {x['name']}: due {x['in_service']}, after the 5-year horizon {horizon}")
    ids = [x["id"] for x in lines]
    errs += [f"duplicate id {i}" for i in sorted({i for i in ids if ids.count(i) > 1})]
    r.add(f"Time window ({cutoff} built to {horizon} due) and stage names", errs, checked=len(lines))


def check_locations(lines, sites, places, r):
    errs, warns, n = [], [], 0
    for st in sites:
        if st["lat"] is None:
            continue
        n += 1
        pt = {"lon": st["lon"], "lat": st["lat"]}
        if not (TX_BOX[0] <= st["lon"] <= TX_BOX[2] and TX_BOX[1] <= st["lat"] <= TX_BOX[3]):
            errs.append(f"substation {st['name']}: point {st['lat']}, {st['lon']} is outside Texas")
            continue
        key = "TX|" + (st["county"] or "")
        if st["confidence"] not in ("exact", "approx") or key not in places.rings:
            continue
        if B.in_county(places, key, pt):
            continue
        d = min(miles((pt["lon"], pt["lat"]), xy) for ring in places.rings[key] for xy in ring)
        msg = f"substation {st['name']}: point is {d:.0f} miles outside {st['county']} County, the county ERCOT lists"
        (errs if d > 40 else warns if d > 3 else []).append(msg)
    unplaced = [x["id"] for x in lines if not any(e.get("lat") is not None for e in x["endpoints"])]
    if unplaced:
        warns.append(f"{len(unplaced)} lines have no placeable substation (ERCOT gives no county): " + ", ".join(unplaced[:8]))
    r.add("Substation points are in Texas and in the county ERCOT lists", errs, warns, n)


def check_substations(lines, sites, r):
    errs, by = [], {s["id"]: s for s in sites}
    for x in lines:
        for e in x["endpoints"]:
            st = by.get(e.get("site_id"))
            if not st:
                continue
            for k_line, k_site in (("station_status", "status"), ("there_now", "there_now"), ("work", "work"), ("work_stage", "work_stage")):
                if e.get(k_line) != st[k_site]:
                    errs.append(f"{x['id']} {e['name']}: {k_line} '{e.get(k_line)}' on the line, '{st[k_site]}' in the substation table")
    for st in sites:
        want = {"new": "no", "unconfirmed": "unknown"}.get(st["status"], "yes")
        if st["there_now"] != want:
            errs.append(f"substation {st['name']}: status '{st['status']}' but there_now '{st['there_now']}'")
        if st["status"] == "new" and st["work_stage"] == "built":
            errs.append(f"substation {st['name']}: marked new (not there yet) but its work is built")
    r.add("Substation status agrees between lines and substations", errs, checked=len(sites))


def check_exports(lines, sites, r):
    ex, errs = os.path.join(WEB, "exports"), []
    rows = list(csv.DictReader(open(os.path.join(ex, "k2-texas-lines.csv"))))
    if len(rows) != len(lines):
        errs.append(f"lines CSV has {len(rows)} rows, page data has {len(lines)} lines")
    missing = [c for c in B.LINE_COLS if rows and c not in rows[0]]
    if missing:
        errs.append("lines CSV is missing columns: " + ", ".join(missing))
    srows = list(csv.DictReader(open(os.path.join(ex, "k2-texas-substations.csv"))))
    if len(srows) != len(sites):
        errs.append(f"substations CSV has {len(srows)} rows, page data has {len(sites)} substations")
    layer = json.load(open(os.path.join(ex, "k2-texas-layer.geojson")))["features"]
    placed = sum(1 for x in lines if any(e.get("lat") is not None for e in x["endpoints"]))
    nl = sum(f["properties"]["feature_type"] == "line" for f in layer)
    ns = sum(f["properties"]["feature_type"] == "substation" for f in layer)
    if nl != placed:
        errs.append(f"GIS layer has {nl} lines, expected {placed} (lines with a placeable substation)")
    if ns != sum(s["lat"] is not None for s in sites):
        errs.append(f"GIS layer has {ns} substations, expected {sum(s['lat'] is not None for s in sites)}")
    for f in layer:
        c = f["geometry"]["coordinates"]
        pts = c if f["geometry"]["type"] == "LineString" else [c]
        if any(not (TX_BOX[0] <= lon <= TX_BOX[2] and TX_BOX[1] <= lat <= TX_BOX[3]) for lon, lat in pts):
            errs.append(f"GIS feature {f['properties']['id']} has a point outside Texas")
    try:
        ET.parse(os.path.join(ex, "k2-texas-layer.kml"))
    except ET.ParseError as err:
        errs.append(f"KML does not open: {err}")
    r.add("Downloads match the page (CSV, GeoJSON, KML)", errs, checked=len(rows) + len(srows) + len(layer))


def check_oncor(lines, r):
    have = [{B.station_key(e["name"]) for e in x["endpoints"]} for x in lines]
    errs, n = [], 0
    for pr in B.oncor_projects():
        keys = {B.station_key(s["name"]) for s in pr["stations"]}
        if len(keys) < 2:
            continue
        n += 1
        if not any(len(keys & h) >= 2 for h in have):
            errs.append(f"Oncor CCN project {pr['project_id']} {pr['name']} is not in the list")
    r.add("Every project on Oncor's CCN Public Viewer is in the list", errs, checked=n)


def main():
    path = os.path.join(WEB, "data", "texas-lines.json")
    d = json.load(open(path))
    lines, sites = d["lines"], d["sites"]
    places = B.Places([])
    r = Report()
    check_tpit(lines, r)
    check_window(lines, d, r)
    check_locations(lines, sites, places, r)
    check_substations(lines, sites, r)
    check_exports(lines, sites, r)
    check_oncor(lines, r)
    failed = [c for c in r.checks if c["errors"]]
    nwarn = sum(len(c["warnings"]) for c in r.checks)
    for c in r.checks:
        print(("FAIL " if c["errors"] else "ok   ") + f"{c['check']} ({c['checked']} checked, {len(c['warnings'])} to review)")
        for e in c["errors"][:15]:
            print("     error:", e)
        for w in c["warnings"][:5]:
            print("     review:", w)
    summary = {"date": datetime.date.today().isoformat(), "passed": len(r.checks) - len(failed), "total": len(r.checks),
               "review": nwarn, "checks": [{"check": c["check"], "checked": c["checked"], "errors": len(c["errors"]),
                                            "review": len(c["warnings"]), "examples": (c["errors"] + c["warnings"])[:3]} for c in r.checks]}
    d["checks"] = summary
    json.dump(d, open(path, "w"), separators=(",", ":"))
    json.dump(r.checks, open(os.path.join(B.HERE, "check-report.json"), "w"), indent=1)
    print(f"{summary['passed']} of {summary['total']} checks passed, {nwarn} items to review")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
