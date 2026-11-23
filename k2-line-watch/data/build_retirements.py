"""Build the "power going offline" list: power plants in Texas that have retired since 2023, are retiring, or are
suspending operations, and the substation each one connects to.

Why it matters (Richard, via John, Nov 23, 2026): when a plant shuts down, the grid capacity it used at its
substation can open up for a new project. These are the places where an interconnection may be easier or faster.

Inputs
  data/sources/eia860m-retirements.json  federal EIA-860M: planned retirement dates and units retired since 2023
  data/sources/ercot-nso-2026.json       ERCOT shutdown notices (NSOs) and what happened after them
  data/sources/hifld-tx-substations.json HIFLD substations (location and highest voltage)
  data/sources/osm-tx-substations.json   OpenStreetMap substations (names where HIFLD has none)
  web/data/texas-lines.json              Line Watch lines and stations (planned line work and queued projects nearby)
Outputs
  web/data/retirements.json, web/exports/k2-texas-retirements.csv, web/exports/k2-texas-retirements.geojson
"""
import csv
import datetime as dt
import json
import math
import os
import re
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "sources")
WEB = os.path.join(HERE, "..", "web")
STATE = "TX"
TODAY = dt.date.today()
HORIZON_YEAR = TODAY.year + 5          # Line Watch looks 5 years ahead
MIN_MW = 10                            # smaller plants rarely matter for a transmission-scale project
SEARCH_MI = 3.0                        # look this far from the plant for its substation
BA_NAMES = {"ERCO": "ERCOT", "SWPP": "SPP", "MISO": "MISO", "EPE": "El Paso Electric", "SPA": "SPA"}


def miles(a, b, c, d):
    p = math.pi / 180
    x = (d - b) * p * math.cos((a + c) / 2 * p)
    return 3958.8 * math.hypot(x, (c - a) * p)


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def load(name):
    return json.load(open(os.path.join(SRC, name)))


def ym(year, month):
    y, m = num(year), num(month)
    if not y:
        return ""
    return "%04d-%02d" % (int(y), int(m or 12))


def substation_for(lat, lon, hifld, osm):
    """Pick the substation a plant most likely connects to: within SEARCH_MI, the highest voltage, then the nearest."""
    near = []
    for s in hifld:
        if s.get("lat") is None or (s.get("status") or "").upper() not in ("IN SERVICE", ""):
            continue
        d = miles(lat, lon, s["lat"], s["lon"])
        if d <= SEARCH_MI:
            near.append((d, s))
    if not near:
        return None
    best_kv = max((s.get("max_kv") or 0) for _, s in near)
    d, s = min(((d, s) for d, s in near if (s.get("max_kv") or 0) >= best_kv), key=lambda x: x[0])
    name = s.get("name") or ""
    name_source = "HIFLD"
    if not name or re.match(r"^(UNKNOWN|TAP)\d*", name.upper()):
        named = [(miles(s["lat"], s["lon"], o["lat"], o["lon"]), o) for o in osm if o.get("name")]
        named = [x for x in named if x[0] <= 0.6]
        if named:
            name, name_source = min(named, key=lambda x: x[0])[1]["name"], "OpenStreetMap"
        else:
            name, name_source = "Unnamed substation", ""
    return {"name": name.title() if name.isupper() else name, "name_source": name_source, "kv": s.get("max_kv"),
            "lat": s["lat"], "lon": s["lon"], "miles_from_plant": round(d, 2), "hifld_id": s.get("id"),
            "check": d > 1.0}


def main():
    eia = load("eia860m-retirements.json")
    nso = load("ercot-nso-2026.json")
    hifld = load("hifld-tx-substations.json")["substations"]
    osm = load("osm-tx-substations.json")["substations"]
    lw = json.load(open(os.path.join(WEB, "data", "texas-lines.json")))
    plants_idx = eia["plants"]

    plants = {}

    def plant(pid, d=None):
        key = str(pid)
        if key not in plants:
            p = plants_idx.get(key) or {}
            src = d or {}
            plants[key] = {
                "id": "eia-%s" % key, "eia_plant": int(key), "plant": p.get("name") or src.get("Plant Name"),
                "owner": p.get("owner") or src.get("Entity Name"), "county": p.get("county") or src.get("County"),
                "market": BA_NAMES.get(p.get("ba") or src.get("Balancing Authority Code"), p.get("ba") or ""),
                "lat": p.get("lat") or num(src.get("Latitude")), "lon": p.get("lon") or num(src.get("Longitude")),
                "plant_mw": round(sum((p.get("mw") or {}).get(s, 0) for s in ("Operating", "Retired")), 1),
                "units": []}
        return plants[key]

    # 1. EIA: units already retired since 2023, and operating units with a planned retirement date
    for d in eia["retired"]:
        if d.get("Plant State") != STATE:
            continue
        plant(d["Plant ID"], d)["units"].append({
            "unit": str(d.get("Generator ID")), "mw": num(d.get("Nameplate Capacity (MW)")) or 0,
            "tech": d.get("Technology"), "status": "retired", "date": ym(d.get("Retirement Year"), d.get("Retirement Month")),
            "source": "EIA-860M (%s), Retired" % eia["as_of"]})
    for d in eia["planned"]:
        if d.get("Plant State") != STATE:
            continue
        plant(d["Plant ID"], d)["units"].append({
            "unit": str(d.get("Generator ID")), "mw": num(d.get("Nameplate Capacity (MW)")) or 0,
            "tech": d.get("Technology"), "status": "retiring",
            "date": ym(d.get("Planned Retirement Year"), d.get("Planned Retirement Month")),
            "source": "EIA-860M (%s), planned retirement" % eia["as_of"]})

    # 2. ERCOT shutdown notices: newer and more exact than EIA, so they lead when both cover a plant
    for n in nso["notices"]:
        p = plant(n["eia_plant"])
        p.setdefault("ercot", []).append(n)

    # 3. Roll units up per plant, place each plant at its substation, and link nearby Line Watch work
    stations = lw.get("stations") or []
    out = []
    for p in plants.values():
        notices = p.get("ercot", [])
        units = p["units"]
        if notices:
            going = [{"what": n["units"], "mw": n["mw"], "status": n["action"], "date": n["effective"],
                      "detail": n["status"], "source": "ERCOT notice %s (%s)" % (n["notice"], n["date"]),
                      "links": n["sources"]} for n in notices]
        else:
            by = defaultdict(lambda: {"mw": 0.0, "units": [], "tech": set()})
            for u in units:
                k = (u["status"], u["date"])
                by[k]["mw"] += u["mw"]
                by[k]["units"].append(u["unit"])
                by[k]["tech"].add(u["tech"] or "")
            going = [{"what": "%s (unit%s %s)" % (", ".join(sorted(t for t in v["tech"] if t)),
                                                  "s" if len(v["units"]) > 1 else "", ", ".join(v["units"])),
                      "mw": round(v["mw"], 1), "status": k[0], "date": k[1], "detail": "",
                      "source": units[0]["source"].split(",")[0] + (", Retired" if k[0] == "retired" else ", planned retirement"),
                      "links": [eia["url"]]} for k, v in sorted(by.items(), key=lambda kv: kv[0][1])]
        # keep the 3-down / 5-up window; temporary and mothballed units stay (they may free capacity)
        going = [g for g in going if not g["date"] or g["status"] in ("temporary", "mothball")
                 or int(g["date"][:4]) <= HORIZON_YEAR]
        mw = round(sum(g["mw"] for g in going), 1)
        if not going or mw < MIN_MW or p["lat"] is None:
            continue
        first = min((g["date"] for g in going if g["date"]), default="")
        if any(g["status"] == "retired" for g in going):
            group = "offline now"
        elif all(g["status"] in ("temporary", "mothball") for g in going):
            group = "paused (may return)"
        elif first and first <= "%d-12" % (TODAY.year + 1):
            group = "retiring by end of %d" % (TODAY.year + 1)
        else:
            group = "retiring %d to %d" % (TODAY.year + 2, HORIZON_YEAR)
        sub = substation_for(p["lat"], p["lon"], hifld, osm)
        near = []
        if sub:
            for st in stations:
                if st.get("lat") is None:
                    continue
                d = miles(sub["lat"], sub["lon"], st["lat"], st["lon"])
                if d <= 1.5:
                    near.append({"station": st["name"], "miles": round(d, 2), "lines": st.get("lines", []),
                                 "queued_projects": len(st.get("projects") or []),
                                 "queued_mw": round(sum(x.get("mw") or 0 for x in st.get("projects") or []), 1)})
        out.append({**{k: v for k, v in p.items() if k not in ("units", "ercot")},
                    "group": group, "mw_going": mw, "first_date": first, "going": going,
                    "substation": sub, "line_watch": near})

    order = ["offline now", "retiring by end of %d" % (TODAY.year + 1), "retiring %d to %d" % (TODAY.year + 2, HORIZON_YEAR),
             "paused (may return)"]
    out.sort(key=lambda r: (order.index(r["group"]) if r["group"] in order else 9, -r["mw_going"]))
    doc = {"built": TODAY.isoformat(), "state": STATE, "window": "retired since %d through retiring by %d" % (eia["retired_since"], HORIZON_YEAR),
           "min_mw": MIN_MW, "groups": order, "count": len(out), "mw_total": round(sum(r["mw_going"] for r in out)),
           "sources": [{"name": "EIA-860M Monthly Generator Inventory, %s" % eia["as_of"], "url": eia["url"]},
                       {"name": "ERCOT shutdown notices (NSO), checked %s" % nso["checked"], "url": nso["archive"]},
                       {"name": "HIFLD Electric Substations (location and voltage)", "url": "https://hifld-geoplatform.hub.arcgis.com/"},
                       {"name": "OpenStreetMap substations (names)", "url": "https://www.openstreetmap.org/"}],
           "how": "Each plant is placed at the highest-voltage substation within %.0f miles of it (the nearest one if several tie). "
                  "Rows marked 'check' are more than a mile from the plant, so the match is less certain." % SEARCH_MI,
           "plants": out}
    json.dump(doc, open(os.path.join(WEB, "data", "retirements.json"), "w"), indent=1)

    cols = ["group", "plant", "owner", "county", "market", "mw_going", "first_date", "what", "substation", "substation_kv",
            "substation_miles", "check_match", "line_watch_nearby", "queued_mw_nearby", "plant_lat", "plant_lon", "source"]
    with open(os.path.join(WEB, "exports", "k2-texas-retirements.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in out:
            s = r["substation"] or {}
            w.writerow([r["group"], r["plant"], r["owner"], r["county"], r["market"], r["mw_going"], r["first_date"],
                        "; ".join("%s: %s MW, %s %s" % (g["what"], g["mw"], g["status"], g["date"]) for g in r["going"]),
                        s.get("name", ""), s.get("kv", ""), s.get("miles_from_plant", ""), "yes" if s.get("check") else "",
                        "; ".join(n["station"] for n in r["line_watch"]), sum(n["queued_mw"] for n in r["line_watch"]) or "",
                        r["lat"], r["lon"], "; ".join(sorted({g["source"] for g in r["going"]}))])
    feats = []
    for r in out:
        s = r["substation"] or {}
        lat, lon = (s["lat"], s["lon"]) if s else (r["lat"], r["lon"])
        feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]},
                      "properties": {"plant": r["plant"], "group": r["group"], "mw_going": r["mw_going"],
                                     "first_date": r["first_date"], "substation": s.get("name"), "kv": s.get("kv"),
                                     "owner": r["owner"], "county": r["county"]}})
    json.dump({"type": "FeatureCollection", "features": feats},
              open(os.path.join(WEB, "exports", "k2-texas-retirements.geojson"), "w"))
    by = defaultdict(lambda: [0, 0])
    for r in out:
        by[r["group"]][0] += 1
        by[r["group"]][1] += r["mw_going"]
    print("%d plants, %d MW going offline in %s" % (len(out), doc["mw_total"], STATE))
    for g in order:
        print("  %-22s %3d plants %7.0f MW" % (g, by[g][0], by[g][1]))
    print("  substation match more than 1 mile away: %d" % sum(1 for r in out if (r["substation"] or {}).get("check")))
    print("  no substation within %.0f miles: %d" % (SEARCH_MI, sum(1 for r in out if not r["substation"])))


if __name__ == "__main__":
    main()
