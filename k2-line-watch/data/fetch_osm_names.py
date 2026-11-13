"""Look up named substations on OpenStreetMap one name at a time (small Overpass queries), for states whose whole-state
download times out. Writes sources/osm-miso-lookups.json; build_miso.MisoPlaces reads it.

    python3 data/fetch_osm_names.py names.tsv      # one "name<TAB>state" per line
"""
import datetime
import json
import os
import re
import sys
import time
import urllib.parse

from fetch_substations import OVERPASS, get

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "sources", "osm-miso-lookups.json")


def lookup(name, st):
    words = re.sub(r"(?i)\b(substation|station|switching|sub|ss|kv|\d+kv)\b", " ", name)
    words = re.sub(r"[^A-Za-z0-9 ]", " ", words).strip()
    if len(words) < 3:
        return []
    rx = ".*".join(re.escape(w) for w in words.split())
    q = (f'[out:json][timeout:60];area["ISO3166-2"="US-{st}"]->.a;'
         f'(node["power"="substation"]["name"~"{rx}",i](area.a);way["power"="substation"]["name"~"{rx}",i](area.a););out center tags;')
    for url in OVERPASS:
        try:
            d = get(url, urllib.parse.urlencode({"data": q}).encode(), timeout=90)
            break
        except Exception:
            time.sleep(2)
    else:
        return None
    out = []
    for el in d["elements"]:
        t, c = el.get("tags", {}), el.get("center") or el
        if c.get("lat") is None:
            continue
        out.append({"name": t["name"], "state": st, "lat": round(c["lat"], 5), "lon": round(c["lon"], 5), "voltage": t.get("voltage", ""),
                    "operator": t.get("operator", ""), "osm": f"{el['type']}/{el['id']}", "query": name})
    return out


if __name__ == "__main__":
    have = json.load(open(OUT)) if os.path.exists(OUT) else {"substations": [], "asked": []}
    asked = {tuple(a) for a in have["asked"]}
    for line in open(sys.argv[1]):
        if not line.strip():
            continue
        name, st = line.rstrip("\n").split("\t")
        if (name, st) in asked:
            continue
        hits = lookup(name, st)
        if hits is None:
            print("no mirror answered:", name, st)
            continue
        have["substations"] += hits
        have["asked"].append([name, st])
        print(name, st, len(hits))
        time.sleep(1)
    have["source"] = f"OpenStreetMap power=substation, looked up by name (via an Overpass mirror), {datetime.date.today():%b %-d, %Y}. Data (c) OpenStreetMap contributors, ODbL."
    json.dump(have, open(OUT, "w"), separators=(",", ":"))
    print(len(have["substations"]), "points")
