"""Fetch public substation points for a state: HIFLD (sources/hifld-<st>-substations.json) and named
OpenStreetMap substations (sources/osm-<st>-substations.json). Line Watch places end substations with these
and checks new vs already mapped against them.

    python3 data/fetch_substations.py OK            # both sources
    python3 data/fetch_substations.py OK --osm      # OpenStreetMap only
"""
import datetime
import json
import os
import sys
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
UA = {"User-Agent": "K2-Line-Watch/1.0"}
HIFLD = "https://services5.arcgis.com/HDRa0B57OVrv2E1q/ArcGIS/rest/services/Electric_Substations/FeatureServer/0/query"
# overpass-api.de drops connections from this network; these mirrors serve the same OpenStreetMap data.
OVERPASS = ["https://maps.mail.ru/osm/tools/overpass/api/interpreter", "https://overpass-api.de/api/interpreter",
            "https://overpass.kumi.systems/api/interpreter"]


def get(url, data=None, timeout=180):
    req = urllib.request.Request(url, data=data, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def hifld(st):
    out, offset = [], 0
    while True:
        q = urllib.parse.urlencode({"where": f"STATE='{st}'", "outFields": "ID,NAME,COUNTY,STATUS,MAX_VOLT,MIN_VOLT,LATITUDE,LONGITUDE",
                                    "resultOffset": offset, "resultRecordCount": 2000, "orderByFields": "OBJECTID", "f": "json"})
        d = get(f"{HIFLD}?{q}")
        for f in d["features"]:
            a = f["attributes"]
            out.append({"id": a["ID"], "name": a["NAME"], "county": a["COUNTY"], "status": a["STATUS"], "max_kv": a["MAX_VOLT"],
                        "min_kv": a["MIN_VOLT"], "lat": round(a["LATITUDE"], 5), "lon": round(a["LONGITUDE"], 5)})
        if not d.get("exceededTransferLimit"):
            break
        offset += len(d["features"])
    return {"source": HIFLD, "fetched": datetime.date.today().isoformat(), "state": st, "count": len(out), "substations": out}


def osm(st):
    q = (f'[out:json][timeout:170];area["ISO3166-2"="US-{st}"]->.a;'
         '(node["power"="substation"]["name"](area.a);way["power"="substation"]["name"](area.a);'
         'relation["power"="substation"]["name"](area.a););out center tags;')
    err = None
    for url in OVERPASS:
        try:
            d = get(url, urllib.parse.urlencode({"data": q}).encode())
            break
        except Exception as e:   # try the next mirror
            err = e
            time.sleep(2)
    else:
        raise SystemExit(f"OpenStreetMap: no Overpass mirror answered ({err})")
    out = []
    for el in d["elements"]:
        t, c = el.get("tags", {}), el.get("center") or el
        if c.get("lat") is None:
            continue
        out.append({"name": t["name"], "lat": round(c["lat"], 5), "lon": round(c["lon"], 5), "voltage": t.get("voltage", ""),
                    "operator": t.get("operator", ""), "kind": t.get("substation", ""), "osm": f"{el['type']}/{el['id']}"})
    when = datetime.date.today().strftime("%b %-d, %Y")
    return {"source": f"OpenStreetMap power=substation in {st} (via an Overpass mirror), {when}. Data (c) OpenStreetMap contributors, ODbL.",
            "count": len(out), "substations": out}


def save(name, d):
    path = os.path.join(HERE, "sources", name)
    json.dump(d, open(path, "w"), separators=(",", ":"))
    print(name, d["count"])


if __name__ == "__main__":
    st = sys.argv[1].upper()
    only = set(a.lstrip("-") for a in sys.argv[2:])
    if not only or "hifld" in only:
        save(f"hifld-{st.lower()}-substations.json", hifld(st))
    if not only or "osm" in only:
        save(f"osm-{st.lower()}-substations.json", osm(st))
