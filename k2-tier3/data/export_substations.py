"""Build substations.json for the Tier 3 workflow from K2 Line Watch project cards.

One row per substation (the same substation shows up in several projects), with the
projects that end there. The n8n workflow reads this file from GitHub.

    python3 export_substations.py ../../k2-line-monitor/data/projects.json
    python3 export_substations.py <dir of project JSON files from the Line Watch database>
"""
import glob
import json
import os
import re
import sys

CONF_RANK = {"exact": 0, "approx": 1, "town": 2, "county": 3}
STAGE_LABELS = {2: "ERCOT review", 3: "Open houses", 4: "Docket request",
                5: "Route case", 6: "Route approved", 7: "Construction"}


def load_projects(src):
    if os.path.isdir(src):
        out = []
        for f in sorted(glob.glob(os.path.join(src, "*.json"))):
            d = json.load(open(f))
            out.append(d.get("data", d))
        return out
    return json.load(open(src))


def base_name(name):
    """'Howard (Howard Road) Station (CPS Energy)' -> 'howard'."""
    n = re.sub(r"\(.*?\)", "", name).lower()
    n = re.sub(r"\b(substation|switch|station|switching|poi)\b", "", n)
    return re.sub(r"[^a-z0-9]+", " ", n).strip()


def main(src, out_path):
    subs = {}
    for p in load_projects(src):
        for e in (p.get("geo") or {}).get("endpoints") or []:
            if e.get("lat") is None or e.get("lon") is None:
                continue
            state, _, county = (e.get("county") or "|").partition("|")
            key = (base_name(e["name"]), state, county)
            s = subs.get(key)
            if s is None or CONF_RANK.get(e.get("confidence"), 9) < CONF_RANK.get(s["confidence"], 9):
                projects = s["projects"] if s else []
                s = subs[key] = {
                    "name": e["name"], "state": state, "county": county,
                    "lat": e["lat"], "lon": e["lon"],
                    "confidence": e.get("confidence", ""),
                    "basis": e.get("basis", ""), "source": e.get("source", ""),
                    "projects": projects,
                }
            s["projects"].append({
                "id": p["id"], "name": p["name"], "kv": p.get("kv", ""),
                "stage": p.get("stage"), "stage_label": p.get("stage_label") or STAGE_LABELS.get(p.get("stage"), ""),
                "importance": p.get("importance", ""), "window": p.get("window", ""),
                "region": p.get("region", ""),
            })
    rows = sorted(subs.values(), key=lambda s: (s["state"], s["county"], s["name"]))
    for s in rows:
        # Stable id: adding a substation later never renumbers the others.
        s["id"] = "-".join(re.sub(r"[^a-z0-9]+", "-", x.lower()).strip("-") for x in (s["state"], s["county"], base_name(s["name"])))
    with open(out_path, "w") as f:
        json.dump({"source": "K2 Line Watch project cards", "count": len(rows), "substations": rows}, f, indent=1)
    print("%d substations from %s -> %s" % (len(rows), src, out_path))


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, "..", "..", "k2-line-monitor", "data", "projects.json"),
         os.path.join(here, "substations.json"))
