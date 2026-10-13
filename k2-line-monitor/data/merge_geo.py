"""Merge researched substation locations into data/geo.json and check them.

  python3 merge_geo.py OUT1.json [OUT2.json ...]

Each input is a list of {"id", "endpoints": [{name, lat, lon, county, state, confidence,
basis, source}], "counties": [{name, state}], "counties_basis", "notes"}. Checks that every
pin sits inside the county it names (using web/counties.json) and that every county name
matches an outline. Writes data/geo.json keyed by project id.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
COUNTIES = json.load(open(os.path.join(HERE, "..", "web", "counties.json"), encoding="utf-8"))
STATE_ABBR = {"texas": "TX", "virginia": "VA", "west virginia": "WV", "maryland": "MD"}


def county_key(name, state):
    """'De Witt', 'TX' -> 'TX|DeWitt' when that outline exists, else None."""
    st = STATE_ABBR.get(str(state).strip().lower(), str(state).strip().upper())
    base = str(name).strip()
    for suffix in (" County", " county"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
    for cand in (base, base.replace(" ", ""), base.title()):
        if "%s|%s" % (st, cand) in COUNTIES:
            return "%s|%s" % (st, cand)
    low = {k.lower().replace(" ", ""): k for k in COUNTIES}
    return low.get(("%s|%s" % (st, base)).lower().replace(" ", ""))


def inside(lon, lat, ring):
    hit = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
        if (y1 > lat) != (y2 > lat) and lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1:
            hit = not hit
    return hit


def county_at(lon, lat):
    for key, rings in COUNTIES.items():
        if any(inside(lon, lat, r) for r in rings):
            return key
    return None


def main(paths):
    geo, problems = {}, []
    for path in paths:
        for item in json.load(open(path, encoding="utf-8")):
            pid, ends, keys = item["id"], [], []
            for e in item.get("endpoints") or []:
                try:
                    lat, lon = float(e["lat"]), float(e["lon"])
                except (KeyError, TypeError, ValueError):
                    problems.append("%s: %s has no usable coordinates" % (pid, e.get("name")))
                    continue
                at = county_at(lon, lat)
                said = county_key(e.get("county", ""), e.get("state", "TX"))
                if at is None:
                    problems.append("%s: %s (%.4f, %.4f) is outside every mapped county" % (pid, e["name"], lat, lon))
                elif said and at != said:
                    problems.append("%s: %s is said to be in %s but the pin falls in %s" % (pid, e["name"], said, at))
                ends.append({k: e.get(k) for k in ("name", "confidence", "basis", "source")} | {"lat": round(lat, 5), "lon": round(lon, 5), "county": at or said})
            for c in item.get("counties") or []:
                key = county_key(c.get("name", ""), c.get("state", "TX"))
                if key:
                    keys.append(key)
                else:
                    problems.append("%s: county %r not found" % (pid, c))
            for e in ends:  # the end substations' own counties are always shaded
                if e["county"] and e["county"] not in keys:
                    keys.append(e["county"])
            geo[pid] = {"endpoints": ends, "counties": keys, "counties_basis": item.get("counties_basis", ""),
                        "notes": item.get("notes", "")}
    with open(os.path.join(HERE, "geo.json"), "w", encoding="utf-8") as fh:
        json.dump(geo, fh, indent=1, ensure_ascii=False)
    print("%d projects with map data" % len(geo))
    for p in problems:
        print("! " + p)


if __name__ == "__main__":
    main(sys.argv[1:])
