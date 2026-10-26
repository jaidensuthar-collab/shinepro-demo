"""Fetch Oncor's CCN Public Viewer: every Oncor line project from open houses (study area) to filed routes,
with its end stations as exact points. It shows projects months before ERCOT's TPIT report lists them.

    python3 fetch_oncor_ccn.py        # writes sources/oncor-ccn.json

build_catalog.py adds the projects it doesn't already have and uses the station points; monitor.py alerts
on new project ids; check_catalog.py checks the catalog against it.
"""
import datetime
import json
import os
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
VIEWER = "https://services6.arcgis.com/4U8AckBJXzVfzxBF/arcgis/rest/services/CCN_Data_AGOL/FeatureServer"
OUT = os.path.join(HERE, "sources", "oncor-ccn.json")


def query(layer, geometry):
    q = urllib.parse.urlencode({"where": "1=1", "outFields": "*", "returnGeometry": str(geometry).lower(), "outSR": 4326, "f": "json"})
    with urllib.request.urlopen(urllib.request.Request(f"{VIEWER}/{layer}/query?{q}", headers={"User-Agent": "K2LineWatch"}), timeout=60) as r:
        d = json.load(r)
    if "error" in d:
        raise RuntimeError(d["error"])
    return d["features"]


def fetch():
    projects = {}
    for f in query(0, False):   # study areas: one per project (a project can have two rows when it was refiled)
        a = f["attributes"]
        p = projects.setdefault(a["project_id"], {"project_id": a["project_id"], "name": " ".join(a["name"].split()), "status": a["status"], "stations": []})
        if a["status"] == "Filed":
            p["status"] = "Filed"
    for f in query(3, True):    # station endpoints with the project's voltage
        a, g = f["attributes"], f.get("geometry") or {}
        p = projects.setdefault(a["project_id"], {"project_id": a["project_id"], "name": "", "status": a.get("route_status") or "", "stations": []})
        p["kv"] = int("".join(c for c in (a.get("project_voltage") or "") if c.isdigit()) or 0)
        if g.get("x") is not None:
            p["stations"].append({"name": " ".join(a["name"].split()), "lat": round(g["y"], 5), "lon": round(g["x"], 5)})
    return {"fetched": datetime.date.today().isoformat(), "source": VIEWER, "projects": sorted(projects.values(), key=lambda p: p["project_id"])}


if __name__ == "__main__":
    d = fetch()
    json.dump(d, open(OUT, "w"), indent=1)
    print(len(d["projects"]), "Oncor CCN projects ->", OUT)
