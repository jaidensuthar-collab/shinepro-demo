"""Check the Texas line catalog against its sources before it is published.

    python3 check_catalog.py            # prints the report, exits 1 if any check fails

What it checks (errors fail the run, warnings are listed for a person to look at):
  1. Every ERCOT line matches its row in the ERCOT TPIT edition it came from: voltage, in-service date, and a stage
     that agrees with ERCOT's status.
  2. The time window: built lines have an actual in-service date in the last 3 years; nothing else is due after the
     5-year horizon.
  3. Locations: every point is in Texas, and every exact or approximate substation point is in (or next to) the
     county the source lists for it.
  4. Substation status agrees between the lines and the substation table (there now, work, stage).
  5. The downloads agree with the page data: line and substation counts, every field present, the KML opens.
  6. Every project on Oncor's CCN Public Viewer is in the list.
  7. Every SPP line matches its rows in SPP's STEP project list: voltage, in-service date, and a stage that agrees
     with SPP's status. Substations SPP's project calls new but with a mapped substation within 0.2 mi are
     listed for a person to look at.
  9. Every PJM upgrade Line Watch keeps (lines 138 kV+, new substations 230 kV+) is in the list with PJM's
     voltage, in-service date and status.
  8. Every MISO line matches its source (Entergy Texas's PUC report and project pages, MISO's MTEP25 Appendix A,
     MISO's Tranche 1 dashboard):
     every in-window project is in the list once, with its voltage, in-service date and stage.
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
import build_spp as SPP
import build_miso as MISO
import build_pjm as PJM

WEB = B.WEB
TX_BOX = (-106.7, 25.8, -93.5, 36.6)
BOXES = {**SPP.STATE_BOX, "AR": (-94.7, 33.0, -89.6, 36.5), "KS": (-102.1, 36.9, -94.6, 40.0), "MO": (-95.8, 35.9, -89.1, 40.6),
         "NM": (-109.1, 31.3, -103.0, 37.0)}
def _state_boxes():
    """Bounding box of each state's counties (web/counties.json), for states the hand-set boxes above don't cover."""
    rings = json.load(open(os.path.join(WEB, "counties.json")))
    out = {}
    for k, v in rings.items():
        xs, ys = [x for r in v for x, _ in r], [y for r in v for _, y in r]
        b = out.get(k[:2])
        out[k[:2]] = (min(xs), min(ys), max(xs), max(ys)) if not b else (min(b[0], min(xs)), min(b[1], min(ys)), max(b[2], max(xs)), max(b[3], max(ys)))
    return out


for _st, _b in _state_boxes().items():
    if _st in ("ND", "SD", "MN", "WI", "IA", "IL", "IN", "MI", "LA", "MS", "KY") + PJM.PJM_STATES:
        BOXES.setdefault(_st, tuple(round(v + d, 2) for v, d in zip(_b, (-0.1, -0.1, 0.1, 0.1))))
ALL_BOX = (min(b[0] for b in BOXES.values()), min(b[1] for b in BOXES.values()), max(b[2] for b in BOXES.values()), max(b[3] for b in BOXES.values()))


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
        box = BOXES.get(st.get("state", "TX"), TX_BOX)
        if not (box[0] <= st["lon"] <= box[2] and box[1] <= st["lat"] <= box[3]):
            errs.append(f"substation {st['name']}: point {st['lat']}, {st['lon']} is outside {st.get('state', 'TX')}")
            continue
        if st.get("state", "TX") != "TX" and st.get("state") not in ("OK",) + MISO.MISO_STATES + PJM.PJM_STATES:
            warns.append(f"substation {st['name']}: placed in {st['state']}, outside the regions this list covers (the line crosses the state line)")
        key = f"{st.get('state', 'TX')}|" + (st["county"] or "")
        if st["confidence"] not in ("exact", "approx") or key not in places.rings:
            continue
        if B.in_county(places, key, pt):
            continue
        d = min(miles((pt["lon"], pt["lat"]), xy) for ring in places.rings[key] for xy in ring)
        msg = f"substation {st['name']}: point is {d:.0f} miles outside {st['county']} County, the county ERCOT lists"
        (errs if d > 40 else warns if d > 3 else []).append(msg)
    unplaced = [x["id"] for x in lines if not any(e.get("lat") is not None for e in x["endpoints"])]
    if unplaced:
        warns.append(f"{len(unplaced)} lines have no placeable substation (no county given, and not on public maps by name): " + ", ".join(unplaced[:8]))
    r.add("Substation points are in their state and in the county the source lists", errs, warns, n)


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
    rows = list(csv.DictReader(open(os.path.join(ex, "k2-all-lines.csv"))))
    if len(rows) != len(lines):
        errs.append(f"lines CSV has {len(rows)} rows, page data has {len(lines)} lines")
    missing = [c for c in B.LINE_COLS if rows and c not in rows[0]]
    if missing:
        errs.append("lines CSV is missing columns: " + ", ".join(missing))
    srows = list(csv.DictReader(open(os.path.join(ex, "k2-all-substations.csv"))))
    if len(srows) != len(sites):
        errs.append(f"substations CSV has {len(srows)} rows, page data has {len(sites)} substations")
    layer = json.load(open(os.path.join(ex, "k2-all-layer.geojson")))["features"]
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
        if any(not (ALL_BOX[0] <= lon <= ALL_BOX[2] and ALL_BOX[1] <= lat <= ALL_BOX[3]) for lon, lat in pts):
            errs.append(f"GIS feature {f['properties']['id']} has a point outside the states Line Watch covers")
    for key, (title, test) in B.REGIONS.items():
        want = sum(1 for x in lines if test(x) and any(e.get("lat") is not None for e in x["endpoints"])) + \
            sum(1 for s in sites if test(s) and s["lat"] is not None)
        got = len(json.load(open(os.path.join(ex, f"k2-{key}-layer.geojson")))["features"])
        if got != want:
            errs.append(f"{title} layer has {got} features, expected {want}")
    for key in ["all"] + list(B.REGIONS):
        try:
            ET.parse(os.path.join(ex, f"k2-{key}-layer.kml.xml"))
        except ET.ParseError as err:
            errs.append(f"k2-{key}-layer.kml does not open: {err}")
    for key, (title, test) in [("all", ("All regions", lambda x: True))] + list(B.REGIONS.items()):
        new = json.load(open(os.path.join(ex, f"k2-{key}-new-only.geojson")))["features"]
        want = sum(1 for x in lines if test(x) and x["lifecycle"] != "built" and any(e.get("lat") is not None for e in x["endpoints"])) + \
            sum(1 for s in sites if test(s) and s["lat"] is not None and B.new_only_reason(s))
        if len(new) != want:
            errs.append(f"{title} new-only layer has {len(new)} features, expected {want}")
        for f in new:
            p = f["properties"]
            if p["feature_type"] == "line" and p["stage"] == "built":
                errs.append(f"new-only layer {key} has built line {p['id']}")
            if p["feature_type"] == "substation" and (not p.get("new_only_reason") or (p.get("on_public_map") == "yes" and p["status"] != "existing, expanding")):
                errs.append(f"new-only layer {key} has substation {p['id']} that is already on the map and not changing")
        try:
            ET.parse(os.path.join(ex, f"k2-{key}-new-only.kml.xml"))
        except ET.ParseError as err:
            errs.append(f"k2-{key}-new-only.kml does not open: {err}")
    r.add("Downloads match the page (CSV, GeoJSON, KML, new-only layers)", errs, checked=len(rows) + len(srows) + len(layer))


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


MISO_DROP = json.load(open(MISO.CORRECTIONS_FILE))["drop"] if os.path.exists(MISO.CORRECTIONS_FILE) else {}


def check_miso(lines, r):
    """MISO lines against their sources: every in-window project is in the list once, with its voltage, in-service
    date and the stage rule (Entergy: status and dates; Tranche 1: MISO's construction column)."""
    errs, warns = [], []
    got = {x["id"]: x for x in lines if x.get("market") == "MISO"}
    etr, lrtp = json.load(open(MISO.ETR_FILE)), json.load(open(MISO.LRTP_FILE))
    want = 0
    for p in etr["projects"]:
        if p["in_service"] and (p["in_service"] > B.HORIZON or p["in_service"] < B.CUTOFF.strftime("%Y-%m")):
            continue
        want += 1
        x = got.get("etr-" + p["key"])
        if not x:
            errs.append(f"Entergy Texas project {p['name']} is missing")
            continue
        if x["kv"] != p["kv"] or x["in_service"] != p["in_service"]:
            errs.append(f"{x['id']}: {x['kv']} kV / {x['in_service']} but the source says {p['kv']} kV / {p['in_service']}")
        if p["status"] == "built" and x["lifecycle"] != "built":
            errs.append(f"{x['id']}: energized per Entergy, but stage is {x['lifecycle']}")
        if x["lifecycle_basis"].startswith("estimated"):
            warns.append(f"{x['id']} {x['name']}: stage '{x['lifecycle']}' is estimated ({x['lifecycle_basis'][:120]})")
    for p in lrtp["projects"]:
        if p["in_service"] > B.HORIZON:
            continue
        want += 1
        x = got.get(f"miso-lrtp-{p['id']}")
        if not x:
            errs.append(f"MISO Tranche 1 project {p['id']} {p['name']} is missing")
            continue
        if x["kv"] != 345 or x["in_service"] != p["in_service"]:
            errs.append(f"{x['id']}: {x['kv']} kV / {x['in_service']} but MISO says 345 kV / {p['in_service']}")
        if (x["lifecycle"] == "in construction") != bool(p["construction"]):
            errs.append(f"{x['id']}: stage {x['lifecycle']} but MISO's construction column says '{p['construction']}'")
    for f in MISO.mtep_rows():
        if str(f["State"] or "").strip()[:2] not in MISO.MISO_STATES or not (f["From Sub"] or f["To Sub"]):
            continue
        x = got.get(f"mtep25-{f['Facility ID']}")
        if not x and f"mtep25-{f['Facility ID']}" in MISO_DROP:
            continue   # withdrawn or cancelled since MTEP25 (sources/miso-corrections-2026.json)
        if not x:
            names = {B.base(n) for n in (str(f["From Sub"] or "").strip(), str(f["To Sub"] or "").strip()) if n}
            if not any(names <= {B.base(e["name"]) for e in y["endpoints"]} for y in got.values() if y["id"].startswith("etr-")):
                errs.append(f"MTEP25 facility {f['Facility ID']} ({f['From Sub']} - {f['To Sub']}) is missing")
            continue
        want += 1
        if x["kv"] != f["kv"] or x["in_service"] != f["isd"]:
            errs.append(f"{x['id']}: {x['kv']} kV / {x['in_service']} but MTEP25 says {f['kv']} kV / {f['isd']}")
        if str(f["Plan Status"]).startswith("M4") != (x["lifecycle"] == "built"):
            errs.append(f"{x['id']}: stage {x['lifecycle']} but MISO's status is {f['Plan Status']}")
    for x in got.values():
        if x["id"].startswith("misor-"):
            want += 1
            if not x["source"] or not x["lifecycle_basis"]:
                errs.append(f"{x['id']}: a researched project needs a source and a reason for its stage")
            if x["lifecycle"] == "built" and not x["in_service"]:
                warns.append(f"{x['id']} {x['name']}: built, but the source gives no in-service month")
    for x in got.values():
        for e in x["endpoints"]:
            if e.get("lat") is None:
                warns.append(f"{x['id']} {x['name']}: {e['name']} has no public location yet")
    if len(got) != want:
        errs.append(f"{len(got)} MISO lines in the list, {want} in the sources' window")
    r.add("MISO lines match their sources (Entergy Texas report, MISO MTEP25 Appendix A, Tranche 1 dashboard, researched utility and state filings)", errs, warns, checked=len(got))


def check_pjm(lines, r):
    """PJM lines against PJM's Project Construction data: every kept upgrade is in the list once, with its voltage,
    in-service date and the stage PJM's status gives."""
    errs, warns = [], []
    got = {x["id"]: x for x in lines if x.get("market") == "PJM" and x["id"].startswith("pjm-")}
    for x in lines:
        if x["id"].startswith("pjmr-") and (not x["source"] or not x["lifecycle_basis"]):
            errs.append(f"{x['id']}: a researched project needs a source and a reason for its stage")
    want = PJM.pjm_rows()
    for w in want:
        x = got.get("pjm-" + w["UpgradeId"])
        if not x:
            errs.append(f"PJM upgrade {w['UpgradeId']} ({w['Location']}) is missing")
            continue
        if x["kv"] != w["kv"] or x["in_service"] != w["isd"] or x["lifecycle"] != w["life"]:
            errs.append(f"{x['id']}: {x['kv']} kV / {x['in_service']} / {x['lifecycle']} but PJM gives {w['kv']} kV / {w['isd']} / {w['life']}")
        if w["basis"].startswith("estimated"):
            warns.append(f"{x['id']} {x['name']}: stage '{x['lifecycle']}' is estimated ({w['basis']})")
    if len(got) != len(want):
        errs.append(f"{len(got)} PJM lines in the list, {len(want)} kept from PJM's data")
    unplaced = sum(1 for x in got.values() if not any(e.get("lat") is not None for e in x["endpoints"]))
    if unplaced:
        warns.append(f"{unplaced} PJM lines have no end substation on public maps yet (they are in the tables, not on the map)")
    r.add("PJM lines match PJM's project data (voltage, in-service date, stage)", errs, warns, checked=len(got))


def check_spp(lines, sites, r):
    rows = {str(d.get("Upgrade ID")): d for d in SPP.read_step()}
    errs, warns, n = [], [], 0
    expect = {"built": SPP.BUILT, "proposed": SPP.EARLY}
    for x in lines:
        if not x["id"].startswith("spp-"):
            continue
        n += 1
        got = [rows.get(u) for u in x["spp_upgrades"]]
        if not all(got):
            errs.append(f"{x['id']} {x['name']}: upgrade {', '.join(u for u, g in zip(x['spp_upgrades'], got) if not g)} not in SPP's list")
            continue
        if x["kv"] not in {SPP.kv_of(d) for d in got}:
            errs.append(f"{x['id']} {x['name']}: {x['kv']} kV here, {sorted({SPP.kv_of(d) for d in got})} kV in SPP's list")
        dates = {B.ym(d.get("Project Owner Indicated In-Service Date")) for d in got} - {""}
        if (x["in_service"] or "") != max(dates, default=""):
            errs.append(f"{x['id']} {x['name']}: in service {x['in_service'] or 'blank'} here, {max(dates, default='blank')} in SPP's list")
        statuses = {SPP.norm(d.get("Project Status")).lower() for d in got}
        want = expect.get(x["lifecycle"])
        if want and not statuses & want:
            errs.append(f"{x['id']} {x['name']}: stage '{x['lifecycle']}' but SPP says {', '.join(sorted(statuses))}")
        if x["lifecycle"] not in ("built", "proposed") and statuses <= (SPP.BUILT | SPP.EARLY):
            errs.append(f"{x['id']} {x['name']}: stage '{x['lifecycle']}' but SPP says {', '.join(sorted(statuses))}")
        if x["lifecycle_basis"].startswith("estimated"):
            warns.append(f"{x['id']} {x['name']}: stage '{x['lifecycle']}' is estimated ({x['lifecycle_basis']})")
    for st in sites:
        if st["status"] == "new" and st.get("on_public_map") == "yes":
            warns.append(f"substation {st['name']} ({st.get('state', 'TX')}): marked new, but {st['nearest_mapped']} is "
                         f"{st['nearest_mapped_miles']} miles away on a public map; it may be built already or sit beside an existing station")
    r.add("SPP lines match SPP's project list (voltage, in-service date, stage)", errs, warns, n)


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
    check_spp(lines, sites, r)
    check_miso(lines, r)
    check_pjm(lines, r)
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
